"""Durable state for bin/heartbeat; reasoning remains in Headlong."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from .state import atomic_json


def state_path() -> Path:
    if os.environ.get("MILK_MAN_HEARTBEAT_FILE"):
        return Path(os.environ["MILK_MAN_HEARTBEAT_FILE"])
    root = Path(os.environ.get("MILK_MAN_STATE_DIR", str(Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "milk-man")))
    current = json.loads((root / "current.json").read_text())
    return Path(current["trajectory_file"] + ".heartbeat.json")


def read(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def preserve(source: Path, target: Path) -> None:
    if source == target:
        return
    data = source.read_bytes()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@contextmanager
def edit(path: Path):
    with path.with_suffix(".edit.lock").open("a") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        value = read(path)
        yield value
        atomic_json(path, value)


def alive(value: dict) -> bool:
    pid = value.get("pid")
    if not isinstance(pid, int) or pid <= 1 or value.get("state") == "stopped":
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def wake(value: dict) -> None:
    if alive(value):
        try:
            os.kill(value["pid"], signal.SIGUSR1)
        except ProcessLookupError:
            pass


def enqueue(path: Path, prompt: str) -> None:
    with edit(path) as value:
        if value.get("pending"):
            raise RuntimeError("one instruction is already pending")
        value["pending"] = prompt
    wake(value)


def observe(command: list[str]) -> dict:
    # Status commands are task-owned read-only scripts; keep logs out of context.
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                    timeout=30, check=False)
            output.seek(0, 2)
            size = output.tell()
            output.seek(max(0, size - 16384))
            text = output.read().decode("utf-8", "replace")
            try:
                data = json.loads(text)
            except ValueError:
                data = text
            return {"exit": result.returncode, "result": data}
        except (OSError, subprocess.TimeoutExpired) as error:
            return {"error": type(error).__name__}


def main() -> None:
    action, *args = sys.argv[1:]
    path = state_path()
    if action == "own":
        lock = os.open(str(path) + ".owner.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Milk Man already owns this task or its child is still running")
        os.set_inheritable(lock, True)
        new_task = os.environ.get("MILK_HEARTBEAT_NEW_TASK") == "1"
        stable_system = path.with_suffix(".system")
        stable_prompt = path.with_suffix(".prompt")
        preserve(Path(os.environ["MILK_HEARTBEAT_SYSTEM_FILE"]), stable_system)
        if new_task or not stable_prompt.exists():
            preserve(Path(os.environ["MILK_HEARTBEAT_PROMPT_FILE"]), stable_prompt)
        os.environ["MILK_HEARTBEAT_SYSTEM_FILE"] = str(stable_system)
        os.environ["MILK_HEARTBEAT_PROMPT_FILE"] = str(stable_prompt)
        try:
            os.setsid()
        except PermissionError:
            pass
        os.environ["MILK_HEARTBEAT_OWNER"] = str(os.getpid())
        os.execv(args[0], args)
    if action == "status":
        value = read(path)
        print(json.dumps({**value, "alive": alive(value)}, separators=(",", ":")))
        return
    if action == "stop":
        value = read(path)
        if alive(value):
            os.kill(value["pid"], signal.SIGTERM)
        return
    if action == "wait":
        delay = None
        if args[:1] == ["--seconds"]:
            delay = float(args[1])
            if delay <= 0:
                raise ValueError("wait seconds must be positive")
            args = args[2:]
        if args[:1] == ["--"]:
            args = args[1:]
        if not args and delay is None:
            raise ValueError("wait needs --seconds or -- followed by a read-only status command")
        observation = observe(args) if args else None
        with edit(path) as value:
            value["watch"] = {"command": args, "last": observation,
                              "due": time.time() + delay if delay else None}
            if value.get("state") in ("idle", "failed"):
                value.update(state="waiting", next_wake=time.time())
        wake(value)
        print(json.dumps({"waiting": True, "observation": observation}))
        return
    stamp = time.time()
    base = float(os.environ.get("MILK_HEARTBEAT_SECONDS", "30"))
    maximum = float(os.environ.get("MILK_HEARTBEAT_MAX_SECONDS", "300"))
    if not 0 < base <= maximum:
        raise ValueError("heartbeat intervals must satisfy 0 < seconds <= max seconds")
    if action == "init":
        with edit(path) as value:
            interrupted = value.get("state") == "running"
            prompt = Path(os.environ["MILK_HEARTBEAT_PROMPT_FILE"]).read_text().strip()
            value.update(pid=os.getppid(), state="waiting" if value.get("watch") else "idle", interval=base, next_wake=stamp)
            if os.environ.get("MILK_HEARTBEAT_NEW_TASK") == "1":
                if not prompt:
                    raise ValueError("a new heartbeat task cannot be empty")
                value["pending"] = prompt
                value.pop("recover", None)
            elif interrupted:
                value["recover"] = True
        return
    if action == "tick":
        previous = read(path)
        observed_watch = previous.get("watch") or {}
        observation = None
        if previous.get("state") == "waiting" and observed_watch.get("command") and stamp >= previous.get("next_wake", 0):
            observation = observe(observed_watch["command"])
        with edit(path) as value:
            value["checked_at"] = stamp
            if value.get("state") == "stopped":
                print("stop")
                return
            watch = value.get("watch") or {}
            changed = watch == observed_watch and observation is not None and observation != watch.get("last")
            due = watch.get("due") is not None and stamp >= watch["due"]
            recovering = value.pop("recover", False)
            pending = None if recovering else value.pop("pending", None)
            prompt = pending
            if recovering:
                prompt = "Resume the interrupted task: " + value.get("task", "") + "\nInspect saved outputs and existing resources first; do not duplicate completed work."
            if not prompt and value.get("state") != "paused" and (changed or due):
                prompt = "Continue the saved task: " + value.get("task", "") + "\n"
                prompt += "Scheduled review is due." if due else "Status changed: " + json.dumps(observation, separators=(",", ":"))
            if prompt:
                if pending:
                    value["task"] = prompt
                value.pop("watch", None)
                value.update(state="running", interval=base, next_wake=None)
                value["turns"] = value.get("turns", 0) + 1
                Path(os.environ["MILK_HEARTBEAT_PROMPT_FILE"]).write_text(prompt)
                print("run")
            else:
                interval = value.get("interval", base)
                if stamp >= (value.get("next_wake") or 0):
                    value["polls"] = value.get("polls", 0) + 1
                    value["next_wake"] = stamp + interval
                    value["interval"] = min(maximum, interval * 2)
                if watch.get("due") and value.get("state") != "paused":
                    value["next_wake"] = min(value["next_wake"], watch["due"])
                print(max(0.1, value["next_wake"] - stamp))
        return
    with edit(path) as value:
        if action == "finish":
            code = int(args[0])
            value.update(last_exit_code=code, state="failed" if code else "waiting" if value.get("watch") else "idle",
                         next_wake=stamp + base, interval=base)
        elif action in ("pause", "resume", "stopped"):
            value["state"] = {"pause": "paused", "resume": "waiting" if value.get("watch") else "idle", "stopped": "stopped"}[action]
            value["next_wake"] = stamp
        else:
            raise ValueError("heartbeat commands: status, wait, pause, resume")
    if action in ("pause", "resume"):
        wake(value)


if __name__ == "__main__":
    main()
