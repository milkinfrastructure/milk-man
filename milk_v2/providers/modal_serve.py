#!/usr/bin/env python3
"""Deploy, observe, and stop one environment-selected vLLM server on Modal."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from milk_v2.providers import modal_controller as modal
from milk_v2.state import redact


APP_FILE = Path(__file__).resolve().parents[2] / "images/modal_serve/app.py"
NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,62}\Z")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
REVISION = re.compile(r"[0-9a-f]{40,64}\Z")
GPU = re.compile(r"[A-Za-z0-9][A-Za-z0-9+!.-]{0,31}\Z")
ACTIVE = {"deployed", "running", "initializing", "initializing..."}
OWNED_ARGS = {
    "--api-key", "--host", "--model", "--port", "--revision",
    "--served-model-name", "--tensor-parallel-size",
}
UNKNOWN = {
    "profile_id": "unknown", "app_name": "unknown", "volume_name": "unknown",
    "model": "unknown", "revision": "unknown", "served_model": "unknown",
    "gpu": "unknown", "gpu_count": 0,
}


class ServeError(RuntimeError):
    def __init__(self, message: str, calls: int = 0):
        super().__init__(message)
        self.calls = calls


def accepted(outcome: dict, phase: str, calls: int) -> None:
    if outcome["state"] == "accepted":
        return
    detail = (outcome.get("stdout", b"")[-2000:] + outcome.get("stderr", b"")[-2000:]).decode("utf-8", "replace")
    for name, value in os.environ.items():
        if len(value) >= 8 and any(part in name.upper() for part in ("KEY", "TOKEN", "SECRET")):
            detail = detail.replace(value, "[redacted]")
    if detail:
        print(detail, file=sys.stderr, flush=True)
    raise ServeError(f"Modal {phase} outcome is ambiguous; inspect status before retrying", calls)


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or len(value) > 512 or any(c in value for c in "\r\n"):
        raise ServeError(f"{name} is required and must be one line")
    return value


def integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ServeError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise ServeError(f"{name} must be in {minimum}..{maximum}")
    return value


def api_mode(name: str) -> str:
    value = os.environ.get(name, "chat_completions")
    if value not in {"chat_completions", "responses"}:
        raise ValueError(f"{name} must be chat_completions or responses")
    return value


def vllm_args() -> list[str]:
    try:
        value = json.loads(os.environ.get("MILK_MODAL_SERVE_VLLM_ARGS_JSON", "[]"))
    except json.JSONDecodeError as error:
        raise ServeError("MILK_MODAL_SERVE_VLLM_ARGS_JSON must be a JSON array") from error
    if not isinstance(value, list) or len(value) > 64 or any(
        not isinstance(item, str) or not item or len(item) > 1024 or any(ord(c) < 32 for c in item)
        for item in value
    ):
        raise ServeError("MILK_MODAL_SERVE_VLLM_ARGS_JSON is invalid")
    for item in value:
        if any(item == name or item.startswith(name + "=") for name in OWNED_ARGS):
            raise ServeError(f"{item.split('=', 1)[0]} is owned by the serving job")
    return value


def plan() -> dict:
    model = required("MILK_MODAL_SERVE_MODEL")
    revision = required("MILK_MODAL_SERVE_REVISION")
    image = required("MILK_MODAL_SERVE_IMAGE")
    api_key = required("MILK_MODAL_SERVE_API_KEY")
    environment = os.environ.get("MODAL_ENVIRONMENT", "main")
    prefix = os.environ.get("MILK_MODAL_SERVE_APP_PREFIX", "milk-serve")
    volume = os.environ.get("MILK_MODAL_SERVE_VOLUME", "milk-model-cache")
    served = os.environ.get("MILK_MODAL_SERVE_SERVED_MODEL", model)
    gpu = os.environ.get("MILK_MODAL_SERVE_GPU", "L4")
    count = integer("MILK_MODAL_SERVE_GPU_COUNT", 1, 1, 8)
    region = os.environ.get("MILK_MODAL_ROUTING_REGION", "us-west")
    scaledown = integer("MILK_MODAL_SERVE_SCALEDOWN_SECONDS", 60, 2, 1200)
    minimum = integer("MILK_MODAL_SERVE_MIN_CONTAINERS", 0, 0, 1)
    concurrency = integer("MILK_MODAL_SERVE_TARGET_CONCURRENCY", 8, 1, 256)
    arguments = vllm_args()
    if MODEL.fullmatch(model) is None or REVISION.fullmatch(revision) is None:
        raise ServeError("model must be a Hugging Face repository and revision must be a commit")
    if (
        not environment or len(environment) > 128 or NAME.fullmatch(prefix) is None
        or NAME.fullmatch(volume) is None or GPU.fullmatch(gpu) is None
        or not served or len(served) > 256 or any(ord(c) < 32 for c in served)
        or len(image) > 512 or any(ord(c) <= 32 for c in image)
        or region not in {"us-east", "us-west", "ca-central", "eu-west", "ap-south"}
    ):
        raise ServeError("Modal serving configuration is invalid")
    base = {
        "schema_version": "milk.modal-serve-plan.v1", "provider": "modal",
        "environment": environment, "app_prefix": prefix, "volume_name": volume,
        "model": model, "revision": revision, "served_model": served, "image": image,
        "gpu": gpu, "gpu_count": count, "vllm_arguments": arguments,
        "routing_region": region, "scaledown_seconds": scaledown, "min_containers": minimum,
        "target_concurrency": concurrency, "app_source_sha256": modal.file_digest(APP_FILE),
        "api_key_sha256": modal.digest({"api_key": api_key}),
    }
    cache_id = modal.digest({"model": model, "revision": revision})
    profile_id = modal.digest(base)
    app_name = f"{prefix}-{profile_id[:12]}"
    if len(app_name) > 63:
        raise ServeError("MILK_MODAL_SERVE_APP_PREFIX is too long")
    return {**base, "cache_id": cache_id, "profile_id": profile_id, "app_name": app_name}


def state_root() -> Path:
    path = modal.state_root() / "serve-modal"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


@contextmanager
def locked(path: Path):
    with (path / ".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def tracked(path: Path) -> dict | None:
    value = modal.read_json(path / "current.json")
    if value is None:
        return None
    result = value.get("plan")
    if not isinstance(result, dict) or not isinstance(result.get("profile_id"), str):
        raise ServeError("saved Modal serving profile is invalid")
    return result


def deploy_environment(value: dict) -> dict[str, str]:
    return {
        "MILK_MODAL_SERVE_APP_NAME": value["app_name"],
        "MILK_MODAL_SERVE_PROFILE_ID": value["profile_id"],
        "MILK_MODAL_SERVE_CACHE_ID": value["cache_id"],
        "MILK_MODAL_SERVE_VOLUME": value["volume_name"],
        "MILK_MODAL_SERVE_MODEL": value["model"],
        "MILK_MODAL_SERVE_REVISION": value["revision"],
        "MILK_MODAL_SERVE_SERVED_MODEL": value["served_model"],
        "MILK_MODAL_SERVE_IMAGE": value["image"],
        "MILK_MODAL_SERVE_GPU": value["gpu"],
        "MILK_MODAL_SERVE_GPU_COUNT": str(value["gpu_count"]),
        "MILK_MODAL_SERVE_VLLM_ARGS_JSON": json.dumps(value["vllm_arguments"], separators=(",", ":")),
        "MILK_MODAL_ROUTING_REGION": value["routing_region"],
        "MILK_MODAL_SERVE_SCALEDOWN_SECONDS": str(value["scaledown_seconds"]),
        "MILK_MODAL_SERVE_TARGET_CONCURRENCY": str(value["target_concurrency"]),
        "MILK_MODAL_SERVE_API_KEY": required("MILK_MODAL_SERVE_API_KEY"),
    }


def observe(value: dict) -> dict:
    environment = value["environment"]
    apps = modal.modal_json(["app", "list", "-e", environment, "--json"], environment)
    matches = [item for item in apps if isinstance(item, dict) and item.get("description") == value["app_name"]]
    active = [item for item in matches if item.get("state") in ACTIVE]
    if len(active) > 1:
        raise ServeError("multiple active Modal apps have the same profile", 1)
    app = active[0] if active else (matches[0] if matches else None)
    containers, endpoint, calls = [], None, 1
    if app and app.get("app_id"):
        containers = modal.modal_json(
            ["container", "list", "-e", environment, "--app-id", app["app_id"], "--json"],
            environment,
        )
        calls += 1
        if app.get("state") == "deployed":
            code = (
                "import modal,sys;"
                "u=modal.Server.from_name(sys.argv[1],'Model',environment_name=sys.argv[2]).get_url();"
                "print(u or '')"
            )
            observed = modal.execute(
                [modal.modal_python(), "-c", code, value["app_name"], environment],
                environment=environment, timeout=120,
            )
            calls += 1
            if observed["state"] == "accepted":
                endpoint = observed["stdout"].decode().strip() or None
    return {
        "app_id": app.get("app_id") if app else None,
        "app_state": app.get("state") if app else "absent",
        "active_containers": len(containers), "endpoint_url": endpoint,
        "provider_calls": calls,
    }


def result(value: dict, state: str, observed: dict | None, calls: int, error: str | None = None, *, include_driver: bool = True) -> dict:
    details = {
        "provider": "modal", "app_name": value["app_name"],
        "volume_name": value["volume_name"], "cache_id": value.get("cache_id"), "model": value["model"],
        "revision": value["revision"], "served_model": value["served_model"],
        "gpu": value["gpu"], "gpu_count": value["gpu_count"], "observation": observed,
        "min_containers": value.get("min_containers", 0),
    }
    if include_driver and observed and observed.get("endpoint_url"):
        mode = api_mode("MILK_MODAL_SERVE_API_MODE")
        endpoint = "/v1/responses" if mode == "responses" else "/v1/chat/completions"
        details["driver"] = {
            "api_url": observed["endpoint_url"].rstrip("/") + endpoint,
            "api_mode": mode, "model": value["served_model"],
            "api_key_env": "MILK_MODAL_SERVE_API_KEY",
        }
    output = {"state": state, "identity": value["profile_id"], "provider_calls": calls, "details": details}
    if error:
        output["error"] = error
    return output


def ensure(value: dict, path: Path) -> tuple[dict, int]:
    started = time.monotonic()
    modal.atomic_json(path / "current.json", {"state": "pending", "plan": value})
    observed = observe(value)
    calls = observed["provider_calls"]
    deployment_reused = observed["app_state"] == "deployed"
    if not deployment_reused:
        print(f"milk: deploying {value['app_name']} ({value['gpu']} x {value['gpu_count']})", file=sys.stderr, flush=True)
        deployed = modal.execute(
            [modal.modal_binary(), "deploy", str(APP_FILE), "--name", value["app_name"],
             "-e", value["environment"], "--tag", value["profile_id"][:50]],
            environment=value["environment"], extra_env=deploy_environment(value), timeout=1800,
        )
        calls += 1
        accepted(deployed, "deploy", calls)
    deployed_at = time.monotonic()
    hydrate_code = (
        "import json,modal,sys;"
        "f=modal.Function.from_name(sys.argv[1],'hydrate',environment_name=sys.argv[2]);"
        "print(json.dumps(f.remote(),sort_keys=True,separators=(',',':')))"
    )
    print(f"milk: loading cached weights for {value['model']}", file=sys.stderr, flush=True)
    hydrated = modal.execute(
        [modal.modal_python(), "-c", hydrate_code, value["app_name"], value["environment"]],
        environment=value["environment"], timeout=6 * 60 * 60,
    )
    calls += 1
    accepted(hydrated, "model hydration", calls)
    hydrated_at = time.monotonic()
    if value["min_containers"]:
        # Only start the warm pool after hydration; the decorator stays at zero.
        warm = modal.execute(
            [modal.modal_python(), "-c",
             "import modal,sys;modal.Server.from_name(sys.argv[1],'Model',environment_name=sys.argv[2]).update_autoscaler(min_containers=int(sys.argv[3]))",
             value["app_name"], value["environment"], str(value["min_containers"])],
            environment=value["environment"], timeout=120,
        )
        calls += 1
        accepted(warm, "warm session", calls)
    observed = observe(value)
    calls += observed["provider_calls"]
    endpoint = observed.get("endpoint_url")
    if observed["app_state"] != "deployed" or not endpoint:
        raise ServeError("Modal serving endpoint is unavailable", calls)
    print("milk: waiting for the inference endpoint", file=sys.stderr, flush=True)
    body, error = modal.request_until_ready(
        endpoint.rstrip("/") + "/v1/models", required("MILK_MODAL_SERVE_API_KEY"), None,
        time.monotonic() + integer("MILK_MODAL_SERVE_STARTUP_TIMEOUT", 1800, 30, 7200),
    )
    calls += 1
    if error:
        raise ServeError(f"Modal serving endpoint did not become ready: {error}", calls)
    try:
        models = json.loads(body)
    except json.JSONDecodeError as parse_error:
        raise ServeError("Modal serving endpoint returned invalid JSON", calls) from parse_error
    if value["served_model"] not in {item.get("id") for item in models.get("data", []) if isinstance(item, dict)}:
        raise ServeError("Modal serving endpoint omitted the configured model", calls)
    observed = observe(value)
    calls += observed["provider_calls"]
    ready_at = time.monotonic()
    observed["startup"] = {
        "deployment_reused": deployment_reused,
        "deploy_seconds": round(deployed_at - started, 3),
        "weight_load_seconds": round(hydrated_at - deployed_at, 3),
        "readiness_seconds": round(ready_at - hydrated_at, 3),
        "total_seconds": round(ready_at - started, 3),
        "basis": "client-observed phases including provider checks; cache may be warm; not GPU-only time or billed duration",
    }
    modal.atomic_json(path / "current.json", {"state": "ready", "plan": value, "startup": observed["startup"]})
    return observed, calls


def stop(value: dict, path: Path) -> tuple[dict, int]:
    observed = observe(value)
    calls = observed["provider_calls"]
    if observed["app_id"] and observed["app_state"] in ACTIVE:
        print(f"milk: stopping {observed['app_id']}", file=sys.stderr, flush=True)
        stopped = modal.execute(
            [modal.modal_binary(), "app", "stop", "-y", "-e", value["environment"], observed["app_id"]],
            environment=value["environment"], timeout=300,
        )
        calls += 1
        accepted(stopped, "stop", calls)
    deadline = time.monotonic() + integer("MILK_MODAL_SERVE_STOP_TIMEOUT", 180, 10, 1800)
    while time.monotonic() < deadline:
        observed = observe(value)
        calls += observed["provider_calls"]
        if observed["app_state"] in {"stopped", "absent"} and observed["active_containers"] == 0:
            (path / "current.json").unlink(missing_ok=True)
            return observed, calls
        time.sleep(3)
    raise ServeError("Modal serving app did not stop", calls)


def main() -> None:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    value = None
    try:
        if action not in {"run", "status", "stop"}:
            raise ServeError("action must be run, status, or stop")
        if action != "stop":
            api_mode("MILK_MODAL_SERVE_API_MODE")
        log_lines = integer("MILK_MODAL_SERVE_LOG_LINES", 0, 0, 100) if action == "status" else 0
        path = state_root()
        value = tracked(path) if action in {"status", "stop"} else None
        value = value or plan()
        with nullcontext() if action == "status" else locked(path):
            if action == "run":
                current = tracked(path)
                if current and current["profile_id"] != value["profile_id"]:
                    print(json.dumps(result(value, "blocked", None, 0, f"stop {current['app_name']} before changing profiles")))
                    raise SystemExit(75)
                try:
                    observed, calls = ensure(value, path)
                except (ServeError, modal.ControllerError, OSError, ValueError) as error:
                    modal.atomic_json(
                        path / "current.json",
                        {"state": "failed", "plan": value, "error": str(error)[:512]},
                    )
                    raise
                output = result(value, "complete", observed, calls)
            elif action == "status":
                observed = observe(value)
                record = modal.read_json(path / "current.json") or {}
                if record.get("plan", {}).get("profile_id") != value["profile_id"]:
                    record = {}
                if record.get("startup") is not None:
                    observed["startup"] = record["startup"]
                failed = record.get("state") == "failed"
                if failed:
                    state = "failed"
                elif record.get("state") == "ready" and observed["app_state"] == "deployed" and observed["endpoint_url"]:
                    state = "complete" if observed["active_containers"] else "idle"
                elif record.get("state") == "pending" or observed["app_state"] in ACTIVE:
                    state = "active"
                else:
                    state = "idle"
                error = record.get("error") if failed and isinstance(record.get("error"), str) else None
                output = result(value, state, observed, observed["provider_calls"], error)
                if log_lines and observed.get("app_id"):
                    fetched = modal.execute(
                        [modal.modal_binary(), "app", "logs", observed["app_id"], "--tail", str(log_lines),
                         "--timestamps", "-e", value["environment"]],
                        environment=value["environment"], timeout=30,
                    )
                    output["provider_calls"] += 1
                    if fetched["state"] == "accepted":
                        text = redact(fetched["stdout"].decode("utf-8", "replace"))
                        lines = re.sub(r"https?://\S+", "[url]", text).splitlines()
                        output["details"]["logs"] = [line[:384] for line in lines[-log_lines:]]
                        output["details"]["logs_truncated"] = len(lines) > log_lines or any(len(line) > 384 for line in lines)
                    else:
                        output["details"]["logs_error"] = "Modal log fetch failed; resource status is unchanged"
                elif log_lines:
                    output["details"]["logs_error"] = "No matching Modal app; nothing was started"
            else:
                observed, calls = stop(value, path)
                output = result(value, "complete", observed, calls, include_driver=False)
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        if output["state"] in {"failed", "blocked"}:
            raise SystemExit(70 if output["state"] == "failed" else 75)
    except BlockingIOError:
        print(json.dumps(result(value or UNKNOWN, "blocked", None, 0, "another Modal serving operation is active")))
        raise SystemExit(75)
    except (ServeError, modal.ControllerError, OSError, ValueError) as error:
        calls = error.calls if isinstance(error, ServeError) else 0
        print(json.dumps(result(value or UNKNOWN, "failed", None, calls, str(error)), sort_keys=True, separators=(",", ":")))
        raise SystemExit(70) from error


if __name__ == "__main__":
    main()
