from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlsplit

from . import config, heartbeat
from .state import SCHEMA as MAN_STATE_SCHEMA, validate_trajectory, workspace_set
from .summary import thresholds
from .store import open_store, settings_from_environment


ROOT = Path(__file__).resolve().parents[1]
RUN_LOCK = threading.Lock()
RUN_PROCESS: subprocess.Popen | None = None
PENDING_PROMPT: str | None = None
PROCESS_LOG: deque[dict] = deque(maxlen=80)
PROCESS_LOG_LOCK = threading.Lock()
LAST_EXIT_CODE: int | None = None
MONITOR_INTERVAL_SECONDS = 30
MONITOR_LOCK = threading.Lock()
MONITOR_REFRESH_LOCK = threading.Lock()
MONITOR_STOP = threading.Event()
MONITOR_STATE: dict | None = None
LAST_EXACT_CAPTURE: tuple[str, int] | None = None

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:authorization|password|token|api[_-]?key|secret(?:[_-]?access[_-]?key)?)\b[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;]+)"
)
AUTHORIZATION = re.compile(r"(?i)\b(Bearer|Api-Key)\s+[^\s,;]+")


WEB_ROOT = ROOT / "milk_v2" / "web"
ASSETS = {
    "/": ("text/html; charset=utf-8", WEB_ROOT / "dashboard.html"),
    "/milk.css": ("text/css; charset=utf-8", WEB_ROOT / "milk.css"),
    "/dashboard.js": ("text/javascript; charset=utf-8", WEB_ROOT / "dashboard.js"),
    "/milk-carton.png": ("image/png", WEB_ROOT / "milk-carton.png"),
}


def _redact(value: object) -> str:
    text = ANSI.sub("", str(value or ""))
    for name, secret in os.environ.items():
        if secret and len(secret) >= 8 and any(word in name.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            text = text.replace(secret, "[redacted]")
    text = AUTHORIZATION.sub(r"\1 [redacted]", text)
    return SECRET_ASSIGNMENT.sub(r"\1[redacted]", text)


def _tail(path: Path, limit: int) -> list[dict]:
    try:
        with path.open() as source:
            lines = deque(source, maxlen=limit)
    except OSError:
        return []
    values = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def _git(path: str, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", path, *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.decode("utf-8", "replace").strip() if result.returncode == 0 else ""


def _within(root: Path, value: object) -> Path | None:
    if not isinstance(value, str):
        return None
    path = Path(value).resolve()
    return path if path == root or root in path.parents else None


def _process_state(trajectory: Path | None) -> tuple[bool, list[dict]]:
    try:
        result = subprocess.run(
            ["ps", "-axo", "command="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, []
    if result.returncode != 0:
        return False, []
    lines = result.stdout.decode("utf-8", "replace").splitlines()
    target = str(trajectory) if trajectory else ""
    active = bool(target) and any(target in line and "shellm" in line for line in lines)
    counts: dict[str, int] = {}
    pattern = re.compile(r"^(?:\S*/)?python(?:\d+(?:\.\d+)*)?\s+-m\s+milk_v2\.runner\s+run\s+([a-z0-9_-]+)(?:\s|$)", re.I)
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            name = match.group(1)
            counts[name] = counts.get(name, 0) + 1
    return active, [{"name": name, "count": counts[name]} for name in sorted(counts)]


def _current_state() -> tuple[dict, Path, Path]:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    root = Path(os.environ.get("MILK_MAN_STATE_DIR", state_home / "milk-man")).resolve()
    current = json.loads((root / "current.json").read_text())
    if not isinstance(current, dict) or current.get("schema_version") != MAN_STATE_SCHEMA:
        raise ValueError("invalid Milk Man state")
    requested = []
    for value in current.get("workspaces", []):
        if not isinstance(value, dict):
            raise ValueError("invalid Milk Man workspace")
        requested.append(f"{value.get('name', '')}={value.get('path', '')}")
    workspaces, digest = workspace_set(requested)
    if digest != current.get("workspace_digest"):
        raise ValueError("Milk Man workspace identity differs")
    trajectory = _within(root, current.get("trajectory_file"))
    memory = _within(root, current.get("memory_file"))
    trajectory_id = current.get("trajectory_id")
    if trajectory is None or memory is None or not isinstance(trajectory_id, str):
        raise ValueError("invalid Milk Man paths")
    validate_trajectory(trajectory, trajectory_id, digest)
    return {**current, "workspaces": workspaces}, trajectory, memory


def _driver_state() -> dict:
    hostname = (urlsplit(os.environ.get("LLM_API_URL", "")).hostname or "").lower()
    if hostname == "inference.baseten.co":
        provider = "baseten"
    elif hostname.endswith((".modal.direct", ".modal.run")):
        provider = "modal"
    elif hostname == "api.openai.com":
        provider = "openai"
    else:
        provider = "custom"
    return {
        "provider": provider,
        "model": os.environ.get("LLM_MODEL", ""),
        "api_mode": os.environ.get("LLM_API_MODE", ""),
        "reasoning_effort": os.environ.get("LLM_REASONING_EFFORT", ""),
    }


def _man_state(include_metadata: bool = True) -> dict:
    try:
        current, trajectory, memory = _current_state()
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "online": True,
            "active": False,
            "state": "setup",
            "connection": "missing",
            "queued": False,
            "last_exit_code": LAST_EXIT_CODE,
            "trajectory_id": None,
            "driver": _driver_state(),
            "local_jobs": [],
            "workspaces": [],
            "memory": [],
            "activity": [],
        }
    with RUN_LOCK:
        attached = RUN_PROCESS is not None and RUN_PROCESS.poll() is None
        queued = PENDING_PROMPT is not None
        last_exit_code = LAST_EXIT_CODE
    pulse = heartbeat.read(Path(str(trajectory) + ".heartbeat.json"))
    pulse_alive = heartbeat.alive(pulse)
    if pulse_alive:
        queued = bool(pulse.get("pending"))
        last_exit_code = pulse.get("last_exit_code")
    discovered, local_jobs = _process_state(trajectory)
    active = pulse.get("state") == "running" if pulse_alive else attached or discovered
    state = ("working" if active else pulse.get("state", "idle")) if pulse_alive else "working" if active else "queued" if queued else "failed" if last_exit_code not in (None, 0) else "idle"
    if pulse and not pulse_alive and not active:
        state = "stopped"
    workspaces, memories = None, None
    if include_metadata:
        workspaces = []
        for value in current.get("workspaces", []):
            if not isinstance(value, dict) or not isinstance(value.get("path"), str):
                continue
            path = value["path"]
            workspaces.append({
                "name": str(value.get("name", "workspace"))[:64],
                "path": path,
                "head": _git(path, "rev-parse", "--short=9", "HEAD"),
                "changes": _git(path, "status", "--short").splitlines()[:24],
            })
        memories = [
            {"ts": str(value.get("ts", ""))[:32], "content": _redact(value.get("content"))[:1000]}
            for value in (_tail(memory, 12) if memory else [])
            if value.get("type") == "memory"
        ]
    events = _tail(trajectory, 200) if trajectory else []
    latest_prompt = next(
        (index for index in range(len(events) - 1, -1, -1) if events[index].get("type") == "prompt"),
        0,
    )
    activity = []
    for value in events[latest_prompt:]:
        kind = str(value.get("type", "event"))[:32]
        if kind == "trajectory":
            continue
        content = _redact(value.get("content"))
        if kind == "shell-output":
            command = "\n".join(_redact(value.get("command")).splitlines()[:6])
            content = f"$ {command}\n{content[-1800:]}\nexit {value.get('exit', '?')}"
        activity.append({"type": kind, "ts": str(value.get("ts", ""))[11:19], "content": content[:2400]})
    with PROCESS_LOG_LOCK:
        activity.extend(PROCESS_LOG)
    try:
        with Path(str(trajectory) + ".run.log").open("rb") as log:
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 16384))
            lines = log.read().decode("utf-8", "replace").splitlines()[-80:]
        starts = [
            index for index, line in enumerate(lines)
            if line.startswith(("milk-man: starting trajectory ", "milk-man: resuming trajectory "))
        ]
        if starts:
            lines = lines[starts[-1]:]
        activity.extend({"type": "process-output", "ts": "", "content": _redact(line)[:2400]} for line in lines if line)
    except FileNotFoundError:
        pass
    return {
        "online": pulse_alive or active or not pulse,
        "active": active,
        "state": state,
        "connection": "heartbeat" if pulse_alive else "attached" if attached else "discovered" if discovered else "idle",
        "heartbeat": {key: pulse.get(key) for key in ("state", "checked_at", "next_wake", "turns", "polls")},
        "queued": queued,
        "last_exit_code": last_exit_code,
        "trajectory_id": current.get("trajectory_id"),
        "driver": _driver_state(),
        "local_jobs": local_jobs,
        "workspaces": workspaces,
        "memory": memories,
        "activity": activity,
    }


def _spawn(current: dict, prompt: str) -> None:
    global LAST_EXIT_CODE, RUN_PROCESS
    mode = "run"
    task = prompt
    if prompt == "/bootstrap" or prompt.startswith("/bootstrap "):
        mode = "bootstrap"
        task = prompt[len("/bootstrap"):].strip()
        if not task:
            raise ValueError("/bootstrap requires a task")
    command = [str(ROOT / "bin/man"), mode, "--resume"]
    for workspace in current["workspaces"]:
        command.extend(["--workspace", f"{workspace['name']}={workspace['path']}"])
    command.extend(["--", task])
    with PROCESS_LOG_LOCK:
        PROCESS_LOG.clear()
    LAST_EXIT_CODE = None
    if mode == "run":
        log_path = Path(current["trajectory_file"] + ".run.log")
        environment = {**os.environ, "MILK_MAN_RUN_LOG_EXTERNAL": "1"}
        with log_path.open("a") as log:
            os.chmod(log_path, 0o600)
            RUN_PROCESS = subprocess.Popen(command, cwd=ROOT, env=environment,
                                           stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT,
                                           start_new_session=True, close_fds=True)
        return
    RUN_PROCESS = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        close_fds=True,
    )
    threading.Thread(target=_read_process, args=(RUN_PROCESS,), daemon=True).start()


def _read_process(process: subprocess.Popen) -> None:
    global LAST_EXIT_CODE
    if process.stdout is None:
        return
    for line in process.stdout:
        content = _redact(line).rstrip()
        if content:
            with RUN_LOCK:
                current = RUN_PROCESS is process
            if not current:
                continue
            with PROCESS_LOG_LOCK:
                PROCESS_LOG.append({
                    "type": "process-output",
                    "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "content": content[:2400],
                })
    process.stdout.close()
    code = process.wait()
    with RUN_LOCK:
        if RUN_PROCESS is not process:
            return
        LAST_EXIT_CODE = code
    with PROCESS_LOG_LOCK:
        PROCESS_LOG.append({
            "type": "process-output",
            "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "content": f"Milk Man exited {code}",
        })


def _drain_prompt() -> None:
    global PENDING_PROMPT
    while True:
        time.sleep(0.5)
        with RUN_LOCK:
            current, trajectory, _ = _current_state()
            process_active = RUN_PROCESS is not None and RUN_PROCESS.poll() is None
            discovered, _ = _process_state(trajectory)
            if process_active or discovered:
                continue
            prompt, PENDING_PROMPT = PENDING_PROMPT, None
            if prompt is not None:
                _spawn(current, prompt)
            return


def _run(prompt: str) -> str:
    global PENDING_PROMPT
    if prompt == "/bootstrap":
        raise ValueError("/bootstrap requires a task")
    with RUN_LOCK:
        current, trajectory, _ = _current_state()
        pulse_path = Path(str(trajectory) + ".heartbeat.json")
        pulse = heartbeat.read(pulse_path)
        if heartbeat.alive(pulse):
            heartbeat.enqueue(pulse_path, prompt)
            return "queued" if pulse.get("state") == "running" else "started"
        process_active = RUN_PROCESS is not None and RUN_PROCESS.poll() is None
        discovered, _ = _process_state(trajectory)
        if process_active or discovered:
            if PENDING_PROMPT is not None:
                raise RuntimeError("one prompt is already queued")
            PENDING_PROMPT = prompt
            threading.Thread(target=_drain_prompt, daemon=True).start()
            return "queued"
        _spawn(current, prompt)
        return "started"


def _capture_count(store, prefix: str) -> int:
    count, cursor = 0, None
    for _ in range(10_000):
        page = store.list(prefix, cursor)
        count += len(page.keys)
        if page.next_cursor is None:
            return count
        cursor = page.next_cursor
    raise ValueError("capture listing is too large")


def _counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key)[:64]: item
        for key, item in value.items()
        if isinstance(item, int) and item >= 0
    }


def _series_view(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        name: item
        for name in ("count", "min", "mean_milli", "p50", "p95", "p99", "max")
        if isinstance((item := value.get(name)), int) and not isinstance(item, bool) and item >= 0
    }


def _summary_view(value: dict) -> dict:
    structural = value.get("structural") if isinstance(value.get("structural"), dict) else {}
    counters = structural.get("counters") if isinstance(structural.get("counters"), dict) else {}
    quality = structural.get("quality") if isinstance(structural.get("quality"), dict) else {}
    distributions = structural.get("distributions") if isinstance(structural.get("distributions"), dict) else {}
    series = structural.get("series") if isinstance(structural.get("series"), dict) else {}
    semantic_root = value.get("semantic") if isinstance(value.get("semantic"), dict) else {}
    semantic = semantic_root.get("cumulative") if isinstance(semantic_root.get("cumulative"), dict) else {}
    return {
        "uuid": value.get("summary_uuid"),
        "created_at": value.get("created_at") if isinstance(value.get("created_at"), str) else None,
        "capture_count": value.get("capture_count", 0),
        "quality": {
            "parse_bps": quality.get("parse_basis_points", 0),
            "success_bps": quality.get("success_basis_points", 0),
            "duplicate_bps": quality.get("duplicate_basis_points", 0),
            "capture_gap": quality.get("capture_gap") is True,
        },
        "counters": {
            name: counters.get(name, 0)
            for name in (
                "captures", "complete", "parsed", "successful", "refusals",
                "unique_contents", "duplicates", "max_concurrency",
                "tool_argument_total", "tool_argument_valid",
            )
        },
        "traffic": {
            name: _counts(distributions.get(name))
            for name in (
                "endpoint", "model", "status_class", "streaming", "route_target",
                "fallback_reason", "modalities", "structured_output",
                "reasoning_effort", "outcome", "hour_utc",
            )
        },
        "semantic": {
            "classified": semantic.get("classified", 0),
            "abstained": semantic.get("abstained", 0),
            **{
                name: _counts(semantic.get(name))
                for name in ("operation", "domain", "capability", "oracle", "sentiment", "outcome", "language")
            },
        },
        "series": {
            name: _series_view(series.get(name))
            for name in ("total_ms", "ttft_ms", "tps_milli", "input_tokens", "output_tokens", "message_count", "tool_calls")
        },
    }


def _summary_chain(store, settings, pointer: object, limit: int) -> list[dict]:
    if not isinstance(pointer, dict):
        return []
    key, expected, seen, values = pointer.get("key"), pointer.get("sha256"), set(), []
    for _ in range(limit):
        if not isinstance(key, str) or not key.startswith(settings.scope_prefix + "s/") or key in seen:
            break
        seen.add(key)
        item = store.get(key)
        if not isinstance(expected, str) or hashlib.sha256(item.body).hexdigest() != expected:
            raise ValueError("summary digest differs")
        value = json.loads(item.body)
        if not isinstance(value, dict) or value.get("schema_version") != "milk.summary.v2" or value.get("scope_id") != settings.scope_id:
            raise ValueError("summary identity differs")
        values.append(_summary_view(value))
        key, expected = value.get("parent_summary_key"), value.get("parent_summary_sha256")
        if key is None:
            break
    return sorted(values, key=lambda value: value["capture_count"])


def _job_contract() -> dict:
    try:
        runtime = config.load()
    except config.ConfigError:
        return {"jobs": [], "operate_order": [], "error": "job configuration unavailable"}
    order = (*runtime.operate_order, *(name for name in runtime.jobs if name not in runtime.operate_order))
    jobs = []
    for name in order:
        job = runtime.job(name)
        required = list(job.environment_required)
        optional = list(job.environment_optional)
        for binding in job.bindings:
            required.extend(config.BINDING_ENVIRONMENTS[binding]["required"])
            optional.extend(config.BINDING_ENVIRONMENTS[binding]["optional"])
        optional.extend((job.trigger.get("values_env"), job.timeout_env))
        required = list(dict.fromkeys(required))
        optional = list(dict.fromkeys(value for value in optional if value and value not in required))
        jobs.append({
            "name": name,
            "description": job.description,
            "trigger": job.trigger["kind"],
            "command": f"bin/milk run {name}",
            "automatic": name in runtime.operate_order,
            "bindings": list(job.bindings),
            "inputs": list(job.input_prefixes),
            "outputs": list(job.output_prefixes),
            "prompt": job.system_prompt,
            "timeout": job.timeout_env,
            "required": [{"name": value, "set": bool(os.environ.get(value))} for value in required],
            "optional": [{"name": value, "set": bool(os.environ.get(value))} for value in optional],
        })
    return {"jobs": jobs, "operate_order": list(runtime.operate_order), "error": None}


def _gateway_health() -> dict:
    raw = os.environ.get("MILK_PARLOR_BASE_URL", "")
    if not raw:
        return {"state": "", "observed": 0, "persisted": 0, "dropped": 0}
    try:
        parsed = urlsplit(raw)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") not in {"", "/v1"}
            or parsed.scheme not in ({"http", "https"} if local else {"https"})
            or not parsed.netloc
        ):
            raise ValueError("invalid Parlor URL")
        request = urllib.request.Request(
            f"{parsed.scheme}://{parsed.netloc}/healthz",
            headers={"Accept": "application/json", "User-Agent": "milk-man-dashboard/1"},
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            body = response.read(65_537)
            if response.status != 200 or len(body) > 65_536:
                raise ValueError("invalid health response")
        value = json.loads(body)
        capture = value.get("capture") if isinstance(value, dict) else None
        if not isinstance(capture, dict):
            raise ValueError("invalid health response")
        state = "up" if value.get("status") == "ok" and capture.get("writer_alive") is True else "degraded"
        return {
            "state": state,
            "observed": capture.get("observed", 0),
            "persisted": capture.get("persisted", 0),
            "dropped": capture.get("dropped", 0),
        }
    except Exception:
        return {"state": "down", "observed": 0, "persisted": 0, "dropped": 0}


def _milk_status(exact_inventory: bool) -> dict:
    required = ["MILK_SCOPE_ID", "MILK_STORE_KIND"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return {"status": None, "progress": {}, "missing": missing, "error": None}
    try:
        settings = settings_from_environment()
        store = open_store(settings)
        points = thresholds(settings.profile)
        captured = _capture_count(store, settings.scope_prefix + "c/") if exact_inventory else 0
        item = store.get(settings.scope_prefix + "status/current.json")
        value = json.loads(item.body)
        if not isinstance(value, dict) or value.get("schema_version") != "milk.status.v2":
            raise ValueError("invalid status")
        processed = value.get("processed_count", 0)
        if not exact_inventory:
            stored_capture_count = value.get("capture_count", processed)
            captured = stored_capture_count if type(stored_capture_count) is int and stored_capture_count >= 0 else processed
        value = {**value, "capture_count": captured}
        return {
            "status": value,
            "progress": {
                "capture_count": captured,
                "processed_count": processed,
                "thresholds": points,
                "next_threshold": next((point for point in points if point > processed), None),
                "checkpoints": _summary_chain(store, settings, value.get("summary"), len(points) + 2),
            },
            "missing": [],
            "error": None,
        }
    except FileNotFoundError:
        return {
            "status": {
                "scope_id": settings.scope_id,
                "profile": settings.profile,
                "capture_count": captured,
                "processed_count": 0,
                "next_action": "summary",
            },
            "progress": {
                "capture_count": captured,
                "processed_count": 0,
                "thresholds": points,
                "next_threshold": points[0] if points else None,
                "checkpoints": [],
            },
            "missing": [],
            "error": None,
        }
    except Exception:
        return {"status": None, "progress": {}, "missing": [], "error": "object store unavailable"}


def _refresh_monitor(exact_inventory: bool = False) -> dict:
    global LAST_EXACT_CAPTURE, MONITOR_STATE
    with MONITOR_REFRESH_LOCK:
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        errors = []
        try:
            milk = _milk_status(exact_inventory)
            status = milk.get("status") if isinstance(milk.get("status"), dict) else {}
            progress = milk.get("progress") if isinstance(milk.get("progress"), dict) else {}
            scope_id = status.get("scope_id")
            capture_count = progress.get("capture_count")
            if isinstance(scope_id, str) and type(capture_count) is int and capture_count >= 0:
                if exact_inventory:
                    LAST_EXACT_CAPTURE = (scope_id, capture_count)
                elif LAST_EXACT_CAPTURE and LAST_EXACT_CAPTURE[0] == scope_id and LAST_EXACT_CAPTURE[1] > capture_count:
                    capture_count = LAST_EXACT_CAPTURE[1]
                    milk = {
                        **milk,
                        "status": {**status, "capture_count": capture_count},
                        "progress": {**progress, "capture_count": capture_count},
                    }
        except Exception:
            errors.append("object-store status")
            milk = {"status": None, "progress": {}, "missing": [], "error": "status check failed"}
        try:
            gateway = _gateway_health()
        except Exception:
            errors.append("gateway status")
            gateway = {"state": "down", "observed": 0, "persisted": 0, "dropped": 0}
        try:
            contract = _job_contract()
        except Exception:
            errors.append("job configuration")
            contract = {"jobs": [], "operate_order": [], "error": "status check failed"}
        snapshot = {
            "schema_version": "milk.dashboard.v1",
            "now": checked_at,
            "monitor": {
                "checked_at": checked_at,
                "interval_seconds": MONITOR_INTERVAL_SECONDS,
                "exact_inventory": exact_inventory,
                "error": ", ".join(errors) if errors else None,
            },
            "milk": milk,
            "gateway": gateway,
            "contract": contract,
        }
        with MONITOR_LOCK:
            MONITOR_STATE = snapshot
        return snapshot


def _monitor_state(refresh: bool = False) -> dict:
    if refresh:
        return _refresh_monitor(True)
    with MONITOR_LOCK:
        snapshot = MONITOR_STATE
    return snapshot if snapshot is not None else _refresh_monitor()


def _monitor() -> None:
    while not MONITOR_STOP.is_set():
        _refresh_monitor()
        MONITOR_STOP.wait(MONITOR_INTERVAL_SECONDS)


class Handler(BaseHTTPRequestHandler):
    def _local(self) -> bool:
        expected = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        return self.headers.get("Host") == expected and (origin is None or origin == f"http://{expected}")

    def do_GET(self) -> None:
        if not self._local():
            self._send(403, "text/plain; charset=utf-8", b"forbidden\n")
            return
        requested = urlsplit(self.path)
        path = requested.path
        if path in ASSETS:
            content_type, source = ASSETS[path]
            try:
                body = source.read_bytes()
            except OSError:
                self._send(500, "text/plain; charset=utf-8", b"dashboard asset unavailable\n")
                return
            self._send(200, content_type, body)
            return
        if path == "/api/local":
            body = json.dumps(
                {"schema_version": "milk.dashboard-local.v1", "man": _man_state(False)},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self._send(200, "application/json", body)
            return
        if path == "/api/state":
            snapshot = _monitor_state(requested.query == "refresh=1")
            body = json.dumps(
                {**snapshot, "man": _man_state()},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self._send(200, "application/json", body)
            return
        self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def do_POST(self) -> None:
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if not self._local() or self.headers.get("Origin") != expected_origin:
            self._send(403, "application/json", b'{"error":"forbidden"}')
            return
        if urlsplit(self.path).path != "/api/run":
            self._send(404, "application/json", b'{"error":"not found"}')
            return
        if self.headers.get_content_type() != "application/json":
            self._send(415, "application/json", b'{"error":"expected JSON"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 1 <= length <= 17_000:
            self._send(413, "application/json", b'{"error":"prompt is too large"}')
            return
        try:
            value = json.loads(self.rfile.read(length))
            prompt = value.get("prompt", "").strip() if isinstance(value, dict) else ""
            if not prompt or len(prompt.encode()) > 16_384:
                raise ValueError("prompt must contain 1 to 16384 bytes")
            state = _run(prompt)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            body = json.dumps({"error": str(error)}, separators=(",", ":")).encode()
            self._send(400, "application/json", body)
            return
        except (OSError, RuntimeError) as error:
            body = json.dumps({"error": str(error)}, separators=(",", ":")).encode()
            self._send(409, "application/json", body)
            return
        body = json.dumps({"state": state}, separators=(",", ":")).encode()
        self._send(202, "application/json", body)

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, unused_format: str, *unused_arguments: object) -> None:
        return


def main() -> None:
    global MONITOR_INTERVAL_SECONDS
    try:
        port = int(os.environ.get("MILK_DASHBOARD_PORT", "8765"))
        MONITOR_INTERVAL_SECONDS = int(os.environ.get("MILK_DASHBOARD_REFRESH_SECONDS", "30"))
    except ValueError as error:
        raise SystemExit("milk-man: dashboard port and refresh interval must be integers") from error
    if not 1024 <= port <= 65535:
        raise SystemExit("milk-man: MILK_DASHBOARD_PORT must be in 1024..65535")
    if not 5 <= MONITOR_INTERVAL_SECONDS <= 3600:
        raise SystemExit("milk-man: MILK_DASHBOARD_REFRESH_SECONDS must be in 5..3600")
    threading.Thread(target=_monitor, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"milk-man dashboard: http://127.0.0.1:{port} (watching every {MONITOR_INTERVAL_SECONDS}s)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        MONITOR_STOP.set()
        server.server_close()


if __name__ == "__main__":
    main()
