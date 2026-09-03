from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlsplit

from .state import SCHEMA as MAN_STATE_SCHEMA, validate_trajectory, workspace_set
from .summary import thresholds
from .store import open_store, settings_from_environment


ROOT = Path(__file__).resolve().parents[1]
RUN_LOCK = threading.Lock()
RUN_PROCESS: subprocess.Popen | None = None
PENDING_PROMPT: str | None = None


WEB_ROOT = ROOT / "milk_v2" / "web"
ASSETS = {
    "/": ("text/html; charset=utf-8", WEB_ROOT / "dashboard.html"),
    "/milk.css": ("text/css; charset=utf-8", WEB_ROOT / "milk.css"),
    "/dashboard.js": ("text/javascript; charset=utf-8", WEB_ROOT / "dashboard.js"),
    "/milk-carton.png": ("image/png", WEB_ROOT / "milk-carton.png"),
}


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


def _active(trajectory: Path | None) -> bool:
    if trajectory is None:
        return False
    try:
        result = subprocess.run(
            ["ps", "-axo", "command="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    target = str(trajectory).encode()
    return result.returncode == 0 and any(target in line and b"shellm" in line for line in result.stdout.splitlines())


def _current_state() -> tuple[dict, Path, Path]:
    root = Path(os.environ.get("MILK_MAN_STATE_DIR", Path.home() / ".local/state/milk-man")).resolve()
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


def _man_state() -> dict:
    try:
        current, trajectory, memory = _current_state()
    except (OSError, ValueError, json.JSONDecodeError):
        return {"active": False, "connection": "missing", "trajectory_id": None, "workspaces": [], "memory": [], "activity": []}
    attached = RUN_PROCESS is not None and RUN_PROCESS.poll() is None
    discovered = _active(trajectory)
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
        {"ts": str(value.get("ts", ""))[:32], "content": str(value.get("content", ""))[:1000]}
        for value in (_tail(memory, 12) if memory else [])
        if value.get("type") == "memory"
    ]
    activity = []
    for value in _tail(trajectory, 60) if trajectory else []:
        kind = str(value.get("type", "event"))[:32]
        if kind == "trajectory":
            continue
        content = str(value.get("content", ""))
        if kind == "shell-output":
            command = "\n".join(str(value.get("command", "")).splitlines()[:6])
            content = f"$ {command}\n{content[-1800:]}\nexit {value.get('exit', '?')}"
        activity.append({"type": kind, "ts": str(value.get("ts", ""))[11:19], "content": content[:2400]})
    return {
        "active": attached or discovered,
        "connection": "attached" if attached else "discovered" if discovered else "detached",
        "trajectory_id": current.get("trajectory_id"),
        "workspaces": workspaces,
        "memory": memories,
        "activity": activity,
    }


def _spawn(current: dict, prompt: str) -> None:
    global RUN_PROCESS
    command = [str(ROOT / "bin/man"), "develop", "--resume"]
    for workspace in current["workspaces"]:
        command.extend(["--workspace", f"{workspace['name']}={workspace['path']}"])
    command.extend(["--", prompt])
    RUN_PROCESS = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        close_fds=True,
    )


def _drain_prompt() -> None:
    global PENDING_PROMPT
    while True:
        time.sleep(0.5)
        with RUN_LOCK:
            current, trajectory, _ = _current_state()
            process_active = RUN_PROCESS is not None and RUN_PROCESS.poll() is None
            if process_active or _active(trajectory):
                continue
            prompt, PENDING_PROMPT = PENDING_PROMPT, None
            if prompt is not None:
                _spawn(current, prompt)
            return


def _run(prompt: str) -> str:
    global PENDING_PROMPT
    with RUN_LOCK:
        current, trajectory, _ = _current_state()
        process_active = RUN_PROCESS is not None and RUN_PROCESS.poll() is None
        if process_active or _active(trajectory):
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


def _summary_view(value: dict) -> dict:
    structural = value.get("structural") if isinstance(value.get("structural"), dict) else {}
    counters = structural.get("counters") if isinstance(structural.get("counters"), dict) else {}
    quality = structural.get("quality") if isinstance(structural.get("quality"), dict) else {}
    series = structural.get("series") if isinstance(structural.get("series"), dict) else {}
    semantic_root = value.get("semantic") if isinstance(value.get("semantic"), dict) else {}
    semantic = semantic_root.get("cumulative") if isinstance(semantic_root.get("cumulative"), dict) else {}
    total = series.get("total_ms") if isinstance(series.get("total_ms"), dict) else {}
    tps = series.get("tps_milli") if isinstance(series.get("tps_milli"), dict) else {}
    return {
        "uuid": value.get("summary_uuid"),
        "capture_count": value.get("capture_count", 0),
        "parse_bps": quality.get("parse_basis_points", 0),
        "success_bps": quality.get("success_basis_points", 0),
        "unique_count": counters.get("unique_contents", 0),
        "classified_count": semantic.get("classified", 0),
        "p95_total_ms": total.get("p95", 0),
        "p50_tps_milli": tps.get("p50", 0),
        "domain": _counts(semantic.get("domain")),
        "operation": _counts(semantic.get("operation")),
        "sentiment": _counts(semantic.get("sentiment")),
        "capability": _counts(semantic.get("capability")),
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


def _milk_status() -> dict:
    required = ["MILK_SCOPE_ID", "MILK_STORE_KIND"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        return {"status": None, "progress": {}, "missing": missing, "error": None}
    try:
        settings = settings_from_environment()
        store = open_store(settings)
        points = thresholds(settings.profile)
        captured = _capture_count(store, settings.scope_prefix + "c/")
        item = store.get(settings.scope_prefix + "status/current.json")
        value = json.loads(item.body)
        if not isinstance(value, dict) or value.get("schema_version") != "milk.status.v2":
            raise ValueError("invalid status")
        processed = value.get("processed_count", 0)
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


class Handler(BaseHTTPRequestHandler):
    def _local(self) -> bool:
        expected = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        return self.headers.get("Host") == expected and (origin is None or origin == f"http://{expected}")

    def do_GET(self) -> None:
        if not self._local():
            self._send(403, "text/plain; charset=utf-8", b"forbidden\n")
            return
        path = urlsplit(self.path).path
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
                {"schema_version": "milk.dashboard-local.v1", "man": _man_state()},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self._send(200, "application/json", body)
            return
        if path == "/api/state":
            body = json.dumps(
                {
                    "schema_version": "milk.dashboard.v1",
                    "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "man": _man_state(),
                    "milk": _milk_status(),
                    "gateway": _gateway_health(),
                },
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
    try:
        port = int(os.environ.get("MILK_DASHBOARD_PORT", "8765"))
    except ValueError as error:
        raise SystemExit("milk-man: MILK_DASHBOARD_PORT must be an integer") from error
    if not 1024 <= port <= 65535:
        raise SystemExit("milk-man: MILK_DASHBOARD_PORT must be in 1024..65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"milk-man dashboard: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
