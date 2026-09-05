"""Durable state for bin/heartbeat; reasoning remains in Headlong."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "milk_v2"

from .state import atomic_json, redact


ITERATION_EXHAUSTED = 76


def driver_state() -> dict:
    hostname = (urlsplit(os.environ.get("LLM_API_URL", "")).hostname or "").lower()
    if os.environ.get("LLM_MILK_TRAJECTORY_HEADER") == "1":
        provider = "milk-parlor"
    elif hostname == "inference.baseten.co":
        provider = "baseten"
    elif hostname.endswith((".modal.direct", ".modal.run")):
        provider = "modal"
    elif hostname == "api.openai.com":
        provider = "openai"
    else:
        provider = "custom"
    return {"provider": provider, **{
        field: redact(os.environ.get(name, ""))[:256]
        for field, name in (("model", "LLM_MODEL"), ("api_mode", "LLM_API_MODE"),
                            ("reasoning_effort", "LLM_REASONING_EFFORT"))
    }}


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
        value["pending"] = {"prompt": prompt, "new_task": value.get("state") == "idle"}
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


def objective(value: dict) -> str:
    task = str(value.get("task", "")).strip()
    brief = str(value.get("brief", "")).strip()
    return task + ("\nLatest operator instruction: " + brief if brief else "")


def terminal(observation) -> bool:
    if not isinstance(observation, dict) or observation.get("exit") != 0:
        return False
    result = observation.get("result")
    if not isinstance(result, dict):
        return False
    details = result.get("details")
    return result.get("terminal") is True or (isinstance(details, dict) and details.get("terminal") is True)


def summary_tick(path: Path, previous: dict, stamp: float) -> dict:
    """Count without reasoning; run the existing summary job at a crossed milestone."""
    enabled = os.environ.get("MILK_AUTO_SUMMARY", "0") == "1"
    state = {"enabled": enabled, "state": "disabled", "checked_at": stamp}
    prior = previous.get("summary") or {}
    if not enabled:
        state.update({key: prior[key] for key in ("run_dir", "threshold") if key in prior})
        return state
    try:
        from .store import settings_from_environment

        if not os.environ.get("MILK_SUMMARY_THRESHOLDS"):
            raise ValueError("summary_thresholds_required")
        settings = settings_from_environment()
        observation = observe([sys.executable, str(Path(__file__).resolve()), "_summary-probe"])
        if observation.get("exit") != 0 or not isinstance(observation.get("result"), dict):
            raise ValueError("summary_probe_failed")
        probe = observation["result"]
        state.update(state="waiting" if probe["next_threshold"] else "complete",
                     threshold=probe["next_threshold"], processed_count=probe["processed_count"])
        root = Path(__file__).resolve().parents[1]
        if prior.get("run_dir"):
            observed = observe([str(root / "bin/background"), prior["run_dir"], "status"])
            result = observed.get("result", {})
            if observed.get("exit") != 0 or not isinstance(result, dict):
                raise ValueError("summary_status_failed")
            if result.get("state") in {"active", "orphaned"}:
                state.update(state="running", threshold=prior["threshold"], run_dir=prior["run_dir"])
                return state
            if result.get("state") != "absent" and probe["processed_count"] < prior["threshold"]:
                state.update(state="failed", threshold=prior["threshold"], run_dir=prior["run_dir"],
                             error="summary_exit_" + str(result.get("exit_code", "unknown")) if result.get("state") != "complete" else "summary_pointer_not_advanced")
                return state
        if not probe["crossed"]:
            return state
        binding = [settings.kind, settings.root, settings.endpoint, settings.region,
                   settings.bucket, settings.scope_id, settings.profile]
        identity = hashlib.sha256(json.dumps(binding, separators=(",", ":")).encode()).hexdigest()
        run = path.parent / "summary-jobs" / identity / str(probe["next_threshold"])
        state.update(state="running", run_dir=str(run))
        with edit(path) as value:
            if value.get("state") in {"paused", "stopped"}:
                state.update(state="waiting")
                state.pop("run_dir", None)
                return state
            value["summary"] = state
        observed = observe([str(root / "bin/background"), str(run), "--", str(root / "bin/milk"), "run", "summary"])
        result = observed.get("result", {})
        if observed.get("exit") != 0 or not isinstance(result, dict):
            raise ValueError("summary_launch_failed")
        # A completed process is not a saved checkpoint; the next probe verifies it.
        if result.get("state") in {"active", "orphaned", "complete"}:
            state["state"] = "running"
        else:
            state.update(state="failed", error="summary_exit_" + str(result.get("exit_code", "unknown")))
    except (OSError, ValueError, KeyError, TypeError) as error:
        if "run_dir" not in state and prior.get("run_dir"):
            state.update(run_dir=prior["run_dir"], threshold=prior["threshold"])
        state.update(state="failed", error=str(error) if isinstance(error, ValueError) and str(error).startswith("summary_") else type(error).__name__)
    return state


def main() -> None:
    arguments = sys.argv[1:]
    if not arguments or arguments[0] in {"-h", "--help", "help"} or (
        len(arguments) == 2 and arguments[1] in {"-h", "--help"}
    ):
        print("Usage: man heartbeat status|pause|resume|stop\n"
              "       man heartbeat wait [--seconds N] [-- READ_ONLY_COMMAND ...]\n"
              "Wait for a changed status, a deadline, or both. Register the wait and return; idle checks use no model calls.")
        return
    action, *args = arguments
    if action == "_summary-probe":
        from .store import open_store, settings_from_environment
        from .summary import threshold_probe

        settings = settings_from_environment()
        print(json.dumps(threshold_probe(open_store(settings), settings), separators=(",", ":")))
        return
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
        if isinstance(observation, dict) and observation.get("error"):
            print(
                "milk-man: heartbeat status command could not start "
                f"({observation['error']}); pass the executable and its arguments separately after -- "
                "or use /bin/bash -lc for shell syntax",
                file=sys.stderr,
            )
            raise SystemExit(64)
        with edit(path) as value:
            value["watch"] = {"command": args, "last": observation,
                              "due": time.time() if terminal(observation) else time.time() + delay if delay else None}
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
            value.update(pid=os.getppid(), state="waiting" if value.get("watch") else "idle", interval=base, next_wake=stamp, driver=driver_state())
            if os.environ.get("MILK_HEARTBEAT_NEW_TASK") == "1":
                if not prompt:
                    raise ValueError("a new heartbeat task cannot be empty")
                value["pending"] = {"prompt": prompt, "new_task": True}
                value.pop("recover", None)
            elif interrupted:
                value["recover"] = True
        return
    if action == "tick":
        previous = read(path)
        automatic_summary = None
        if previous.get("state") not in {"paused", "stopped", "running"} and stamp >= (previous.get("next_wake") or 0):
            automatic_summary = summary_tick(path, previous, stamp)
        observed_watch = previous.get("watch") or {}
        observation = None
        if previous.get("state") == "waiting" and observed_watch.get("command") and stamp >= previous.get("next_wake", 0):
            observation = observe(observed_watch["command"])
        with edit(path) as value:
            value["checked_at"] = stamp
            if automatic_summary is not None:
                value["summary"] = automatic_summary
            if value.get("state") == "stopped":
                print("stop")
                return
            watch = value.get("watch") or {}
            changed = watch == observed_watch and observation is not None and (observation != watch.get("last") or terminal(observation))
            due = watch.get("due") is not None and stamp >= watch["due"]
            recovering = value.pop("recover", False)
            pending_value = None if recovering else value.pop("pending", None)
            pending = None
            new_task = False
            if isinstance(pending_value, dict):
                pending = pending_value.get("prompt")
                new_task = pending_value.get("new_task") is True
            elif isinstance(pending_value, str):
                pending = pending_value
                new_task = value.get("state") == "idle" or not value.get("task")
            prompt = None
            if recovering:
                prompt = "Resume the interrupted task: " + objective(value) + "\nInspect saved outputs and existing resources first; do not duplicate completed work."
            elif isinstance(pending, str) and pending.strip():
                pending = pending.strip()
                if new_task or not value.get("task"):
                    value["task"] = pending
                    value.pop("brief", None)
                    prompt = pending
                else:
                    value["brief"] = pending
                    prompt = "Continue the saved task: " + objective(value)
            if not prompt and value.get("state") != "paused" and (changed or due):
                prompt = "Continue the saved task: " + objective(value) + "\n"
                prompt += "Scheduled review is due." if due else "Status changed: " + json.dumps(observation, separators=(",", ":"))
            if prompt:
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
            if code == ITERATION_EXHAUSTED:
                if not value.get("watch"):
                    value["watch"] = {"command": [], "last": None, "due": stamp + base}
                state = "waiting"
            else:
                state = "failed" if code else "waiting" if value.get("watch") else "idle"
            value.update(last_exit_code=code, state=state, next_wake=stamp + base, interval=base)
            if code == 0 and not value.get("watch"):
                value.pop("brief", None)
        elif action in ("pause", "resume", "stopped"):
            value["state"] = {"pause": "paused", "resume": "waiting" if value.get("watch") else "idle", "stopped": "stopped"}[action]
            value["next_wake"] = stamp
        else:
            raise ValueError("heartbeat commands: status, wait, pause, resume")
    if action in ("pause", "resume"):
        wake(value)


if __name__ == "__main__":
    main()
