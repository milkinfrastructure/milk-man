#!/usr/bin/env python3
"""Private local state for the Milk Man development harness."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from uuid import UUID, uuid4


NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SCHEMA = "milk.man-state.v2"
SECRET_ENV_NAME = re.compile(r"(?:^|_)(?:API_?KEY|(?:ACCESS|SIGNING|PRIVATE|OPERATOR)_KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?)(?:_|$)", re.I)
SECRET_ENV_SELECTOR = re.compile(r"_(?:ENV|NAME|FILE|PATH)$", re.I)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?P<label>(?<![A-Z0-9_-])[\"']?(?P<name>(?:[A-Z0-9]+[_-])*"
    r"(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?)"
    r"(?:[_-][A-Z0-9]+)*)(?![A-Z0-9_-])[\"']?\s*[:=]\s*)"
    r"(?P<value>\"(?:\\.|[^\"\r\n])*\"|'(?:\\.|[^'\r\n])*'|[^\s,;]+)"
)
AUTHORIZATION = re.compile(r"(?i)\b(Bearer|Api-Key)\s+[^\s,;]+")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def redact_assignment(match: re.Match[str]) -> str:
    if SECRET_ENV_SELECTOR.search(match["name"]):
        return match.group(0)
    value = match["value"]
    quote = value[0] if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"} else ""
    return f"{match['label']}{quote}[redacted]{quote}"


def redact(text: str) -> str:
    for secret in sorted(
        {
            value
            for name, value in os.environ.items()
            if value and SECRET_ENV_NAME.search(name) and not SECRET_ENV_SELECTOR.search(name)
        },
        key=len,
        reverse=True,
    ):
        if len(secret) >= 4:
            text = text.replace(secret, "[redacted]")
        else:
            text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])", "[redacted]", text)
    text = AUTHORIZATION.sub(r"\1 [redacted]", text)
    return SECRET_ASSIGNMENT.sub(redact_assignment, text)


def redact_message(value: object, key: str = "") -> object:
    if isinstance(value, dict):
        return {name: redact_message(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [redact_message(item) for item in value]
    if isinstance(value, str):
        if key in {"id", "tool_call_id", "name", "role", "type"}:
            return value
        if key == "arguments":
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return redact(value)
            return json.dumps(redact_message(parsed), ensure_ascii=False, separators=(",", ":"))
        return redact(value)
    return value


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def append_json(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("a") as handle:
        os.chmod(path, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def workspace_set(values: list[str]) -> tuple[list[dict], str]:
    workspaces: list[dict] = []
    names: set[str] = set()
    paths: set[str] = set()
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not NAME.fullmatch(name):
            raise ValueError(f"invalid workspace {value!r}; expected name=/absolute/path")
        path = Path(raw_path)
        if not path.is_absolute() or not path.is_dir():
            raise ValueError(f"workspace {name!r} must be an existing absolute directory")
        resolved = str(path.resolve())
        if name in names or resolved in paths:
            raise ValueError(f"duplicate workspace name or path: {value!r}")
        names.add(name)
        paths.add(resolved)
        workspaces.append({"name": name, "path": resolved})
    if not workspaces:
        raise ValueError("at least one --workspace is required")
    canonical = sorted(workspaces, key=lambda item: item["name"])
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return canonical, hashlib.sha256(encoded).hexdigest()


def git_snapshot(path: str) -> dict:
    def git(*arguments: str) -> bytes | None:
        result = subprocess.run(
            ["git", "-C", path, *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.stdout if result.returncode == 0 else None

    head = git("rev-parse", "HEAD")
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    content = hashlib.sha256()
    content.update(head or b"")
    content.update(git("diff", "--no-ext-diff", "--binary", "HEAD") or b"")
    for name in sorted((git("ls-files", "--others", "--exclude-standard", "-z") or b"").split(b"\0")):
        if not name:
            continue
        file = Path(path) / os.fsdecode(name)
        value = hashlib.sha256()
        if file.is_symlink():
            value.update(os.fsencode(os.readlink(file)))
        else:
            with file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    value.update(chunk)
        content.update(name + b"\0" + value.digest())
    return {
        "head": head.decode().strip() if head else None,
        "dirty_sha256": hashlib.sha256(status or b"").hexdigest(),
        "content_sha256": content.hexdigest() if head is not None else None,
        "dirty": bool(status),
    }


def validate_trajectory(path: Path, trajectory_id: str, digest: str) -> None:
    try:
        UUID(trajectory_id)
    except ValueError as error:
        raise ValueError("--traj must be an exact trajectory UUID") from error
    try:
        first = json.loads(path.open().readline())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid trajectory {trajectory_id}: {error}") from error
    if (
        first.get("type") != "trajectory"
        or first.get("step_id") != trajectory_id
        or first.get("workspace_digest") != digest
    ):
        raise ValueError("trajectory does not belong to the exact workspace set")


def prepare(arguments: argparse.Namespace) -> None:
    state = Path(arguments.state_root).resolve()
    workspaces, digest = workspace_set(arguments.workspace)
    trajectory_dir = state / "trajectories" / digest
    current_file = state / "workspaces" / f"{digest}.json"
    trajectory_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    (state / "memories").mkdir(mode=0o700, parents=True, exist_ok=True)

    if arguments.resume:
        if not current_file.is_file():
            raise ValueError("no trajectory exists for this exact workspace set")
        trajectory_id = str(read_json(current_file).get("trajectory_id", ""))
    elif arguments.traj:
        trajectory_id = arguments.traj
    else:
        trajectory_id = str(uuid4())

    trajectory = trajectory_dir / f"{trajectory_id}.jsonl"
    if arguments.resume or arguments.traj:
        validate_trajectory(trajectory, trajectory_id, digest)
    else:
        header = {
            "schema_version": SCHEMA,
            "type": "trajectory",
            "step_id": trajectory_id,
            "ts": now(),
            "workspace_digest": digest,
            "workspaces": workspaces,
        }
        append_json(trajectory, header)

    snapshots = [item | git_snapshot(item["path"]) for item in workspaces]
    record = {
        "schema_version": SCHEMA,
        "workspace_digest": digest,
        "workspaces": snapshots,
        "trajectory_id": trajectory_id,
        "trajectory_file": str(trajectory),
        "memory_file": str(state / "memories" / f"{digest}.jsonl"),
        "updated_at": now(),
    }
    atomic_json(current_file, record)
    atomic_json(state / "current.json", record)

    output = Path(arguments.env_file)
    variables = {
        "MILK_MAN_TRAJECTORY_ID": trajectory_id,
        "MILK_MAN_TRAJECTORY": str(trajectory),
        "MILK_MAN_WORKSPACE_DIGEST": digest,
        "MILK_MAN_WORKSPACE_RECORD": str(current_file),
        "MILK_MAN_MEMORY_FILE": record["memory_file"],
        "MILK_MAN_PRIMARY_WORKSPACE": workspaces[0]["path"],
    }
    output.write_text("".join(f"{key}={shlex.quote(value)}\n" for key, value in variables.items()))
    os.chmod(output, 0o600)


def token_usage(value: dict) -> dict:
    """Keep only observed counts; missing or malformed provider fields stay unknown."""
    result = {}
    for field, alternatives in {
        "input_tokens": (("input_tokens",), ("prompt_tokens",)),
        "output_tokens": (("output_tokens",), ("completion_tokens",)),
        "cached_tokens": (("input_tokens_details", "cached_tokens"), ("prompt_tokens_details", "cached_tokens")),
        "reasoning_tokens": (("output_tokens_details", "reasoning_tokens"), ("completion_tokens_details", "reasoning_tokens")),
    }.items():
        result[field] = None
        for path in alternatives:
            count = value
            for key in path:
                count = count.get(key) if isinstance(count, dict) else None
            if type(count) is int and count >= 0:
                result[field] = count
                break
    return result


def append_step(arguments: argparse.Namespace) -> None:
    trajectory = Path(arguments.trajectory)
    content = redact(Path(arguments.content_file).read_text() if arguments.content_file else "")
    record: dict = {
        "schema_version": SCHEMA,
        "type": arguments.type,
        "step_id": str(uuid4()),
        "ts": now(),
        "content": content,
    }
    if arguments.command_file:
        record["command"] = redact(Path(arguments.command_file).read_text())
    if arguments.message_file:
        record["message"] = redact_message(read_json(Path(arguments.message_file)))
    if arguments.usage_file:
        record["usage"] = token_usage(read_json(Path(arguments.usage_file)))
    if arguments.exit_code is not None:
        record["exit"] = arguments.exit_code
    append_json(trajectory, record)


def records(path: Path) -> list[dict]:
    result: list[dict] = []
    try:
        lines = path.read_text().splitlines()
    except OSError as error:
        raise ValueError(f"cannot read trajectory: {error}") from error
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def context(arguments: argparse.Namespace) -> None:
    if arguments.max_bytes <= 0:
        raise ValueError("context byte limit must be positive")
    messages: list[dict] = []
    prompt_indexes: list[int] = []
    shell_indexes: list[int] = []
    native_indexes: set[int] = set()
    pairs: list[tuple[int, int]] = []
    pending: tuple[int, str] | None = None
    message_limit = max(1024, min(8192, arguments.max_bytes // 3))
    for record in records(Path(arguments.trajectory)):
        kind = record.get("type")
        content = redact(str(record.get("content", "")))
        if kind == "prompt":
            pending = None
            prompt_indexes.append(len(messages))
            messages.append({"role": "user", "content": content})
        elif kind == "reasoning":
            pending = None
            message = redact_message(record.get("message"))
            calls = message.get("tool_calls") if isinstance(message, dict) else None
            if (
                isinstance(message, dict)
                and message.get("role") == "assistant"
                and isinstance(calls, list)
                and len(calls) == 1
                and isinstance(calls[0], dict)
                and isinstance(calls[0].get("id"), str)
                and bool(calls[0]["id"])
            ):
                pending = (len(messages), calls[0]["id"])
                native_indexes.add(len(messages))
                messages.append(message)
            else:
                messages.append({"role": "assistant", "content": content})
        elif kind == "shell-output":
            command = redact(str(record.get("command", "")))
            exit_code = record.get("exit")
            if pending:
                # The tool call already contains the command. Retain both ends
                # of its result and keep the exit status outside truncation.
                raw = content.encode()
                if len(raw) > message_limit:
                    half = message_limit // 2
                    content = (
                        raw[:half].decode(errors="replace")
                        + "\n[shell output middle truncated]\n"
                        + raw[-half:].decode(errors="replace")
                    )
                observation = f"Exit: {exit_code}\nOutput:\n{content}"
                messages.append({"role": "tool", "tool_call_id": pending[1], "content": observation})
                pairs.append((pending[0], len(messages) - 1))
                pending = None
            else:
                shell_indexes.append(len(messages))
                observation = f"Command:\n{command}\nExit: {exit_code}\nOutput:\n{content}"
                messages.append({"role": "user", "content": observation})
        elif kind == "final":
            pending = None
            messages.append({"role": "assistant", "content": content})

    # Shell output can be much larger than the task that produced it. Keep the
    # durable trajectory intact, but bound each rendered observation so the
    # active task cannot fall out of the model context.
    for index in shell_indexes:
        message = messages[index]
        raw = message["content"].encode()
        if len(raw) > message_limit:
            message["content"] = (
                "[shell output truncated; tail follows]\n"
                + raw[-message_limit:].decode(errors="replace")
            )
    required = set(prompt_indexes[-2:])
    paired_native = {assistant_index for assistant_index, _ in pairs}
    unpaired_native = native_indexes - paired_native
    for index in required:
        message = messages[index]
        raw = message["content"].encode()
        if len(raw) > message_limit:
            half = message_limit // 2
            message["content"] = (
                raw[:half].decode(errors="replace")
                + "\n[task middle truncated]\n"
                + raw[-half:].decode(errors="replace")
            )
    kept_indexes = set(required)
    used = 2 + sum(
        len(json.dumps(messages[index], ensure_ascii=False, separators=(",", ":")).encode()) + 1
        for index in required
    )
    for index in reversed(range(len(messages))):
        if index in required or index in unpaired_native:
            continue
        message = messages[index]
        size = len(json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode()) + 1
        if used + size > arguments.max_bytes:
            continue
        kept_indexes.add(index)
        used += size
    for assistant_index, tool_index in pairs:
        if assistant_index not in kept_indexes or tool_index not in kept_indexes:
            kept_indexes.discard(assistant_index)
            kept_indexes.discard(tool_index)
    json.dump(
        [message for index, message in enumerate(messages) if index in kept_indexes],
        sys.stdout,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def memory_add(arguments: argparse.Namespace) -> None:
    if arguments.max_entry_bytes <= 0:
        raise ValueError("memory entry byte limit must be positive")
    text = redact(sys.stdin.read().strip())
    if not text:
        raise ValueError("memory entry is empty")
    encoded = text.encode()
    if len(encoded) > arguments.max_entry_bytes:
        raise ValueError(f"memory entry exceeds {arguments.max_entry_bytes} bytes")
    append_json(
        Path(arguments.memory_file),
        {"schema_version": SCHEMA, "type": "memory", "step_id": str(uuid4()), "ts": now(), "content": text},
    )


def memory_render(arguments: argparse.Namespace) -> None:
    if arguments.max_bytes <= 0:
        raise ValueError("memory byte limit must be positive")
    path = Path(arguments.memory_file)
    if not path.exists():
        return
    entries = [redact(str(item.get("content", ""))) for item in records(path) if item.get("type") == "memory"]
    kept: list[str] = []
    used = 0
    for entry in reversed(entries):
        size = len(entry.encode()) + 3
        if kept and used + size > arguments.max_bytes:
            break
        kept.append(entry[-arguments.max_bytes :] if size > arguments.max_bytes else entry)
        used += min(size, arguments.max_bytes)
    for entry in reversed(kept):
        print(f"- {entry}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)

    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--state-root", required=True)
    prepare_parser.add_argument("--workspace", action="append", default=[], required=True)
    selection = prepare_parser.add_mutually_exclusive_group()
    selection.add_argument("--resume", action="store_true")
    selection.add_argument("--traj")
    prepare_parser.add_argument("--env-file", required=True)
    prepare_parser.set_defaults(run=prepare)

    append_parser = commands.add_parser("append")
    append_parser.add_argument("--trajectory", required=True)
    append_parser.add_argument("--type", choices=("prompt", "reasoning", "shell-output", "final"), required=True)
    append_parser.add_argument("--content-file")
    append_parser.add_argument("--command-file")
    append_parser.add_argument("--message-file")
    append_parser.add_argument("--usage-file")
    append_parser.add_argument("--exit-code", type=int)
    append_parser.set_defaults(run=append_step)

    context_parser = commands.add_parser("context")
    context_parser.add_argument("--trajectory", required=True)
    context_parser.add_argument("--max-bytes", type=int, default=131072)
    context_parser.set_defaults(run=context)

    add_parser = commands.add_parser("memory-add")
    add_parser.add_argument("--memory-file", required=True)
    add_parser.add_argument("--max-entry-bytes", type=int, default=8192)
    add_parser.set_defaults(run=memory_add)

    render_parser = commands.add_parser("memory-render")
    render_parser.add_argument("--memory-file", required=True)
    render_parser.add_argument("--max-bytes", type=int, default=16384)
    render_parser.set_defaults(run=memory_render)

    redact_parser = commands.add_parser("redact")
    redact_parser.set_defaults(run=lambda _arguments: redact_stream())
    return root


def redact_stream() -> None:
    for line in sys.stdin:
        sys.stdout.write(redact(line))
        sys.stdout.flush()


def main() -> None:
    try:
        arguments = parser().parse_args()
        arguments.run(arguments)
    except ValueError as error:
        print(f"milk-man: {error}", file=sys.stderr)
        raise SystemExit(65) from error


if __name__ == "__main__":
    main()
