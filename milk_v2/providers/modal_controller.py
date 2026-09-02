"""One fixed Modal controller: plan, reconcile, create, observe, and stop."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


MODEL_REPO = "zai-org/GLM-4.5-Air-FP8"
MODEL_REVISION = "f9a9c5acf5e543cd24d659a056c5dbcda78ffcfc"
SERVED_MODEL = "glm-4.5-air-fp8"
SGLANG_IMAGE = "lmsysorg/sglang@sha256:34d728fd77f57ae62f5bf236239ed48774f1e96f8a293adf2e1e29bfe5949bbb"
GPU = "H200"
GPU_COUNT = 1
VOLUME_SUBPATH = f"glm-4.5-air-fp8/{MODEL_REVISION}"
MARKER_PATH = f"/{VOLUME_SUBPATH}/.milk-model.json"
APP_FILE = Path(__file__).resolve().parents[2] / "images/controller/app.py"
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ControllerError(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def state_root() -> Path:
    raw = os.environ.get(
        "MILK_MAN_STATE_DIR",
        str(Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "milk-man"),
    )
    path = Path(raw).expanduser().resolve()
    if not path.is_absolute() or path in (Path("/"), Path.home()):
        raise ControllerError("MILK_MAN_STATE_DIR must be an absolute dedicated directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def plan() -> dict:
    environment = os.environ.get("MODAL_ENVIRONMENT", "main")
    app_prefix = os.environ.get("MILK_MODAL_CONTROLLER_APP_PREFIX", "milk-man-controller")
    volume = os.environ.get(
        "MILK_MODAL_CONTROLLER_VOLUME",
        f"milk-man-glm-45-air-fp8-{MODEL_REVISION[:8]}",
    )
    routing_region = os.environ.get("MILK_MODAL_ROUTING_REGION", "us-west")
    api_key_env = os.environ.get("MILK_MODAL_CONTROLLER_API_KEY_ENV", "MILK_CONTROLLER_API_KEY")
    if not NAME.fullmatch(app_prefix) or not NAME.fullmatch(volume):
        raise ControllerError("Modal controller app prefix or volume name is invalid")
    if routing_region not in {"us-east", "us-west", "ca-central", "eu-west", "ap-south"}:
        raise ControllerError("MILK_MODAL_ROUTING_REGION is invalid")
    if not environment or len(environment) > 128 or not ENV_NAME.fullmatch(api_key_env):
        raise ControllerError("Modal environment or controller API-key environment name is invalid")
    base = {
        "schema_version": "milk.modal-controller-plan.v2",
        "provider": "modal",
        "environment": environment,
        "app_prefix": app_prefix,
        "volume_name": volume,
        "volume_subpath": VOLUME_SUBPATH,
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "served_model": SERVED_MODEL,
        "server_image": SGLANG_IMAGE,
        "gpu": GPU,
        "gpu_count": GPU_COUNT,
        "min_containers": 0,
        "max_containers": 1,
        "scaledown_window_seconds": 60,
        "context_length": 32768,
        "routing_region": routing_region,
        "api_key_env": api_key_env,
        "app_source_sha256": file_digest(APP_FILE),
        "controller_source_sha256": file_digest(Path(__file__)),
    }
    controller_id = digest(base)
    app_name = f"{app_prefix}-{controller_id[:12]}"
    if len(app_name) > 63:
        raise ControllerError("MILK_MODAL_CONTROLLER_APP_PREFIX is too long")
    return {
        **base,
        "controller_id": controller_id,
        "app_name": app_name,
    }


def controller_api_key(controller: dict) -> str:
    value = os.environ.get(controller["api_key_env"], "")
    if not value or "\n" in value or "\r" in value:
        raise ControllerError(f"{controller['api_key_env']} is required and must be one line")
    return value


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ControllerError(f"invalid controller record: {path}")
    return value


def write_once(path: Path, value: dict) -> dict:
    existing = read_json(path)
    if existing is not None:
        if existing.get("controller_id") != value.get("controller_id"):
            raise ControllerError(f"controller record identity mismatch: {path}")
        return existing
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = read_json(path)
        if existing is None or existing.get("controller_id") != value.get("controller_id"):
            raise ControllerError(f"controller record identity mismatch: {path}")
        return existing
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical(value))
        handle.flush()
        os.fsync(handle.fileno())
    return value


def tracked_controller(root: Path) -> dict | None:
    pointer = read_json(root / "controller/current.json") or read_json(root / "controller/pending.json")
    if pointer is None:
        return None
    controller_id = pointer.get("controller_id")
    if not isinstance(controller_id, str):
        raise ControllerError("controller pointer has no identity")
    intent = read_json(root / "controller/runs" / controller_id / "intent.json")
    if intent is None or intent.get("controller_id") != controller_id:
        raise ControllerError("controller pointer has no matching intent")
    return intent


@contextmanager
def operation_lock(root: Path):
    lock = root / "controller/.lock"
    lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def modal_binary() -> str:
    binary = shutil.which(os.environ.get("MILK_MODAL_CLI", "modal"))
    if binary is None:
        raise ControllerError("Modal CLI is not installed")
    return binary


def modal_python() -> str:
    binary = Path(modal_binary()).resolve()
    first = binary.read_text(errors="ignore").splitlines()[0]
    if not first.startswith("#!") or not Path(first[2:]).is_file():
        raise ControllerError("cannot locate the Modal CLI Python runtime")
    return first[2:]


def execute(arguments: list[str], *, environment: str, extra_env: dict[str, str] | None = None, timeout: int = 1800) -> dict:
    child_env = os.environ.copy()
    child_env["MODAL_ENVIRONMENT"] = environment
    child_env.update(extra_env or {})
    try:
        result = subprocess.run(
            arguments,
            cwd=APP_FILE.parents[2],
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "state": "ambiguous",
            "returncode": None,
            "error_class": type(error).__name__,
            "error_sha256": hashlib.sha256(str(error).encode()).hexdigest(),
            "stdout": b"",
            "stderr": b"",
        }
    return {
        "state": "accepted" if result.returncode == 0 else "ambiguous",
        "returncode": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def modal_json(arguments: list[str], environment: str) -> list:
    result = execute([modal_binary(), *arguments], environment=environment, timeout=120)
    if result["state"] != "accepted":
        raise ControllerError(
            f"Modal observation failed ({result.get('returncode')}): {result.get('stderr_sha256', result.get('error_sha256'))}"
        )
    try:
        value = json.loads(result["stdout"])
    except json.JSONDecodeError as error:
        raise ControllerError("Modal observation returned invalid JSON") from error
    if not isinstance(value, list):
        raise ControllerError("Modal observation must return a JSON array")
    return value


def marker_value() -> dict:
    return {
        "schema_version": "milk.modal-model-cache.v2",
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "volume_subpath": VOLUME_SUBPATH,
    }


def observe_marker(controller: dict, volume_exists: bool) -> dict | None:
    if not volume_exists:
        return None
    result = execute(
        [
            modal_binary(), "volume", "get", "-e", controller["environment"],
            controller["volume_name"], MARKER_PATH, "-",
        ],
        environment=controller["environment"],
        timeout=120,
    )
    if result["state"] != "accepted":
        if b"No such file or directory" in result.get("stderr", b""):
            return None
        raise ControllerError("cannot observe the Modal model-cache marker")
    try:
        marker_line = result["stdout"].splitlines()[0]
        value = json.loads(marker_line)
    except (IndexError, json.JSONDecodeError) as error:
        raise ControllerError("Modal model-cache marker is invalid") from error
    if value != marker_value():
        raise ControllerError("Modal model-cache marker differs from the pinned model")
    return value


def provider_observation(controller: dict) -> dict:
    environment = controller["environment"]
    volumes = modal_json(["volume", "list", "-e", environment, "--json"], environment)
    calls = 1
    volume_exists = any(item.get("name") == controller["volume_name"] for item in volumes if isinstance(item, dict))
    marker = observe_marker(controller, volume_exists)
    calls += int(volume_exists)
    apps = modal_json(["app", "list", "-e", environment, "--json"], environment)
    calls += 1
    matches = [item for item in apps if isinstance(item, dict) and item.get("description") == controller["app_name"]]
    active = [item for item in matches if item.get("state") in {"deployed", "running", "initializing"}]
    if len(active) > 1:
        raise ControllerError("multiple active Modal controller apps have the same identity")
    app = active[0] if active else (matches[0] if matches else None)
    containers: list = []
    endpoint_url = None
    if app and app.get("app_id"):
        containers = modal_json(
            ["container", "list", "-e", environment, "--app-id", app["app_id"], "--json"],
            environment,
        )
        calls += 1
        if app.get("state") == "deployed":
            code = (
                "import modal,sys; "
                "url=modal.Server.from_name(sys.argv[1],'Controller',environment_name=sys.argv[2]).get_url(); "
                "print(url or '')"
            )
            result = execute(
                [modal_python(), "-c", code, controller["app_name"], environment],
                environment=environment,
                timeout=120,
            )
            calls += 1
            if result["state"] == "accepted":
                endpoint_url = result["stdout"].decode().strip() or None
    return {
        "app_id": app.get("app_id") if app else None,
        "app_state": app.get("state") if app else "absent",
        "active_containers": len(containers),
        "volume_exists": volume_exists,
        "cache_ready": marker is not None,
        "endpoint_url": endpoint_url,
        "provider_calls": calls,
    }


def receipt_value(controller: dict, operation: str, result: dict) -> dict:
    receipt_id = digest({"controller_id": controller["controller_id"], "operation": operation})
    return {
        "schema_version": "milk.modal-controller-receipt.v2",
        "controller_id": controller["controller_id"],
        "receipt_id": receipt_id,
        "operation": operation,
        "state": result["state"],
        "returncode": result.get("returncode"),
        "stdout_sha256": result.get("stdout_sha256"),
        "stderr_sha256": result.get("stderr_sha256"),
        "error_class": result.get("error_class"),
        "error_sha256": result.get("error_sha256"),
        "observed_at": now(),
    }


def result(controller: dict, command: str, state: str, observation: dict | None, *, provider_calls: int, reason: str | None = None) -> dict:
    value = {
        "schema_version": "milk.modal-controller-result.v2",
        "command": command,
        "state": state,
        "controller_id": controller["controller_id"],
        "provider": "modal",
        "provider_calls": provider_calls,
        "model": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "served_model": SERVED_MODEL,
        "gpu": GPU,
        "gpu_count": GPU_COUNT,
        "app_name": controller["app_name"],
        "volume_name": controller["volume_name"],
        "observation": observation,
    }
    if reason:
        value["reason"] = reason
    return value


def ensure_volume(controller: dict, run_root: Path, observation: dict) -> tuple[dict, int, str | None]:
    if observation["volume_exists"]:
        return observation, 0, None
    receipt_path = run_root / "volume-create.json"
    old = read_json(receipt_path)
    if old:
        observation = provider_observation(controller)
        return observation, observation["provider_calls"], None if observation["volume_exists"] else "ambiguous_volume_create_no_replay"
    command = [modal_binary(), "volume", "create", "-e", controller["environment"], controller["volume_name"]]
    call = execute(command, environment=controller["environment"], timeout=300)
    write_once(receipt_path, receipt_value(controller, "volume-create", call))
    observation = provider_observation(controller)
    if not observation["volume_exists"]:
        return observation, 1 + observation["provider_calls"], "ambiguous_volume_create_no_replay"
    return observation, 1 + observation["provider_calls"], None


def ensure_deployment(controller: dict, run_root: Path, observation: dict) -> tuple[dict, int, str | None]:
    if observation["app_state"] == "deployed":
        return observation, 0, None
    receipt_path = run_root / "deploy.json"
    old = read_json(receipt_path)
    if old:
        observation = provider_observation(controller)
        if observation["app_state"] == "deployed":
            return observation, observation["provider_calls"], None
        return observation, observation["provider_calls"], "ambiguous_deploy_no_replay"
    child = {
        "MILK_MODAL_CONTROLLER_APP_NAME": controller["app_name"],
        "MILK_MODAL_CONTROLLER_VOLUME_NAME": controller["volume_name"],
        "MILK_MODAL_ROUTING_REGION": controller["routing_region"],
        "MILK_CONTROLLER_API_KEY": controller_api_key(controller),
    }
    command = [
        modal_binary(), "deploy", str(APP_FILE), "--name", controller["app_name"],
        "-e", controller["environment"], "--tag", controller["controller_id"][:50],
    ]
    call = execute(command, environment=controller["environment"], extra_env=child, timeout=1800)
    write_once(receipt_path, receipt_value(controller, "deploy", call))
    observation = provider_observation(controller)
    if observation["app_state"] != "deployed":
        return observation, 1 + observation["provider_calls"], "ambiguous_deploy_no_replay"
    return observation, 1 + observation["provider_calls"], None


def hydrate(controller: dict, run_root: Path, observation: dict) -> tuple[dict, int, str | None]:
    if observation["cache_ready"]:
        return observation, 0, None
    receipt_path = run_root / "hydrate.json"
    old = read_json(receipt_path)
    if old:
        observation = provider_observation(controller)
        return observation, observation["provider_calls"], None if observation["cache_ready"] else "ambiguous_hydration_no_replay"
    code = (
        "import json,modal,sys; "
        "f=modal.Function.from_name(sys.argv[1],'hydrate',environment_name=sys.argv[2]); "
        "print(json.dumps(f.remote(),sort_keys=True,separators=(',',':')))"
    )
    call = execute(
        [modal_python(), "-c", code, controller["app_name"], controller["environment"]],
        environment=controller["environment"],
        timeout=6 * 60 * 60,
    )
    write_once(receipt_path, receipt_value(controller, "hydrate", call))
    observation = provider_observation(controller)
    if not observation["cache_ready"]:
        return observation, 1 + observation["provider_calls"], "ambiguous_hydration_no_replay"
    return observation, 1 + observation["provider_calls"], None


def request_until_ready(url: str, key: str, payload: bytes | None, deadline: float) -> tuple[bytes, str | None]:
    last_error = "startup timeout"
    while time.monotonic() < deadline:
        headers = {"Authorization": f"Bearer {key}"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=payload, headers=headers, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request, timeout=120) as opened:
                return opened.read(), None
        except HTTPError as error:
            last_error = f"HTTP {error.code}"
            if error.code != 503:
                return b"", last_error
        except OSError as error:
            last_error = type(error).__name__
        time.sleep(5)
    return b"", last_error


def smoke(controller: dict, run_root: Path, observation: dict) -> tuple[int, str | None]:
    if read_json(run_root / "smoke.json"):
        return 0, None
    endpoint = observation.get("endpoint_url")
    if not endpoint:
        return 0, "endpoint is unavailable"
    key = controller_api_key(controller)
    deadline = time.monotonic() + int(os.environ.get("MILK_MODAL_CONTROLLER_STARTUP_TIMEOUT", "1800"))
    base = endpoint.rstrip("/") + "/v1"
    models_response, error = request_until_ready(base + "/models", key, None, deadline)
    if error:
        return 1, error
    try:
        models = json.loads(models_response)
        if SERVED_MODEL not in {item.get("id") for item in models.get("data", []) if isinstance(item, dict)}:
            raise ControllerError("controller model listing omits the pinned served model")
    except (AttributeError, json.JSONDecodeError) as error:
        return 1, type(error).__name__
    payload = canonical(
        {"model": SERVED_MODEL, "messages": [{"role": "user", "content": "Reply with milk."}], "max_tokens": 8}
    )
    response, error = request_until_ready(base + "/chat/completions", key, payload, deadline)
    if error:
        return 2, error
    try:
        if not json.loads(response).get("choices"):
            raise ControllerError("controller smoke has no choices")
    except (AttributeError, json.JSONDecodeError) as error:
        return 2, type(error).__name__
    write_once(
        run_root / "smoke.json",
        {
            "schema_version": "milk.modal-controller-smoke.v2",
            "controller_id": controller["controller_id"],
            "models_response_sha256": hashlib.sha256(models_response).hexdigest(),
            "request_sha256": hashlib.sha256(payload).hexdigest(),
            "response_sha256": hashlib.sha256(response).hexdigest(),
            "observed_at": now(),
            "state": "accepted",
        },
    )
    return 2, None


def ensure(controller: dict, apply: bool) -> dict:
    root = state_root()
    if apply:
        controller_api_key(controller)
    run_root = root / "controller/runs" / controller["controller_id"]
    intent = {**controller, "schema_version": "milk.modal-controller-intent.v2", "intent_id": controller["controller_id"]}
    write_once(run_root / "intent.json", intent)
    if not apply:
        return result(controller, "ensure", "planned", None, provider_calls=0)
    calls = 0
    with operation_lock(root):
        tracked = tracked_controller(root)
        if tracked and tracked["controller_id"] != controller["controller_id"]:
            return result(
                controller,
                "ensure",
                "blocked",
                None,
                provider_calls=0,
                reason=f"controller {tracked['controller_id']} must be stopped or reconciled first",
            )
        atomic_json(
            root / "controller/pending.json",
            {"schema_version": "milk.modal-controller-pointer.v2", "controller_id": controller["controller_id"]},
        )
        observation = provider_observation(controller)
        calls += observation["provider_calls"]
        observation, added, reason = ensure_volume(controller, run_root, observation)
        calls += added
        if reason:
            return result(controller, "ensure", "ambiguous", observation, provider_calls=calls, reason=reason)
        observation, added, reason = ensure_deployment(controller, run_root, observation)
        calls += added
        if reason:
            return result(controller, "ensure", "ambiguous", observation, provider_calls=calls, reason=reason)
        observation, added, reason = hydrate(controller, run_root, observation)
        calls += added
        if reason:
            return result(controller, "ensure", "ambiguous", observation, provider_calls=calls, reason=reason)
        added, reason = smoke(controller, run_root, observation)
        calls += added
        if reason:
            return result(controller, "ensure", "blocked", observation, provider_calls=calls, reason=reason)
        observation = provider_observation(controller)
        calls += observation["provider_calls"]
        endpoint = observation.get("endpoint_url")
        if not endpoint or observation["app_state"] != "deployed" or not observation["cache_ready"]:
            return result(
                controller,
                "ensure",
                "ambiguous",
                observation,
                provider_calls=calls,
                reason="endpoint_changed_after_smoke",
            )
        endpoint_receipt = {
            "schema_version": "milk.modal-controller-endpoint.v2",
            "controller_id": controller["controller_id"],
            "app_id": observation["app_id"],
            "base_url": endpoint.rstrip("/") + "/v1",
            "model": SERVED_MODEL,
            "api_key_env": controller["api_key_env"],
            "model_revision": MODEL_REVISION,
        }
        endpoint_receipt["endpoint_id"] = digest(endpoint_receipt)
        endpoint_receipt = write_once(run_root / "endpoint.json", endpoint_receipt)
        binding = {
            "schema_version": "milk.modal-controller-binding.v2",
            "provider": "modal",
            "controller_id": controller["controller_id"],
            "endpoint_id": endpoint_receipt["endpoint_id"],
            "app_id": endpoint_receipt["app_id"],
            "base_url": endpoint_receipt["base_url"],
            "model": SERVED_MODEL,
            "model_revision": MODEL_REVISION,
            "api_key_env": controller["api_key_env"],
        }
        binding["binding_id"] = digest(binding)
        atomic_json(root / "controller/current.json", binding)
        write_once(run_root / "result.json", {**binding, "state": "ready", "observed_at": now()})
        pending = root / "controller/pending.json"
        if pending.exists():
            pending.unlink()
        return result(controller, "ensure", "ready", observation, provider_calls=calls)


def status(controller: dict) -> dict:
    observation = provider_observation(controller)
    if observation["app_state"] != "deployed":
        state = "not_deployed"
    elif not observation["cache_ready"] or not observation["endpoint_url"]:
        state = "incomplete"
    elif observation["active_containers"] == 0:
        state = "ready_zero"
    else:
        state = "ready_active"
    return result(controller, "status", state, observation, provider_calls=observation["provider_calls"])


def stop(controller: dict, apply: bool) -> dict:
    root = state_root()
    run_root = root / "controller/runs" / controller["controller_id"]
    if not apply:
        return result(controller, "stop", "planned", None, provider_calls=0)
    with operation_lock(root):
        observation = provider_observation(controller)
        calls = observation["provider_calls"]
        intent = {
            "schema_version": "milk.modal-controller-stop-intent.v2",
            "intent_id": digest({"controller_id": controller["controller_id"], "operation": "stop"}),
            "controller_id": controller["controller_id"],
            "app_id": observation["app_id"],
            "app_name": controller["app_name"],
        }
        write_once(run_root / "stop-intent.json", intent)
        if observation["app_state"] in {"deployed", "running", "initializing"}:
            receipt_path = run_root / "stop.json"
            if read_json(receipt_path) is None:
                call = execute(
                    [modal_binary(), "app", "stop", "-y", "-e", controller["environment"], observation["app_id"]],
                    environment=controller["environment"],
                    timeout=300,
                )
                write_once(receipt_path, receipt_value(controller, "stop", call))
                calls += 1
            deadline = time.monotonic() + int(os.environ.get("MILK_MODAL_STOP_TIMEOUT", "120"))
            while time.monotonic() < deadline:
                observation = provider_observation(controller)
                calls += observation["provider_calls"]
                if observation["active_containers"] == 0 and observation["app_state"] not in {"deployed", "running", "initializing"}:
                    break
                time.sleep(2)
        if observation["active_containers"] != 0:
            return result(controller, "stop", "ambiguous", observation, provider_calls=calls, reason="containers_remain_active")
        zero = {
            "schema_version": "milk.modal-controller-zero.v2",
            "controller_id": controller["controller_id"],
            "app_id": observation["app_id"],
            "active_containers": 0,
            "observed_at": now(),
            "state": "zero",
        }
        write_once(run_root / "zero.json", zero)
        write_once(
            run_root / "termination.json",
            {
                "schema_version": "milk.modal-controller-termination.v2",
                "controller_id": controller["controller_id"],
                "app_id": observation["app_id"],
                "zero_sha256": digest(zero),
                "state": "observed_zero",
            },
        )
        current = root / "controller/current.json"
        if (value := read_json(current)) and value.get("controller_id") == controller["controller_id"]:
            current.unlink()
        pending = root / "controller/pending.json"
        if (value := read_json(pending)) and value.get("controller_id") == controller["controller_id"]:
            pending.unlink()
        return result(controller, "stop", "zero", observation, provider_calls=calls)


def parse(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m milk_v2.providers.modal_controller")
    commands = parser.add_subparsers(dest="command", required=True)
    ensure_parser = commands.add_parser("ensure")
    ensure_parser.add_argument("--apply", action="store_true")
    commands.add_parser("status")
    stop_parser = commands.add_parser("stop")
    stop_parser.add_argument("--apply", action="store_true")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> None:
    try:
        options = parse(list(sys.argv[1:] if arguments is None else arguments))
        controller = plan()
        if options.command in {"status", "stop"}:
            controller = tracked_controller(state_root()) or controller
        if options.command == "ensure":
            value = ensure(controller, options.apply)
        elif options.command == "status":
            value = status(controller)
        else:
            value = stop(controller, options.apply)
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
    except BlockingIOError:
        print("modal-controller: another controller operation is active", file=sys.stderr)
        raise SystemExit(75)
    except (ControllerError, json.JSONDecodeError, OSError, ValueError) as error:
        print(f"modal-controller: {error}", file=sys.stderr)
        raise SystemExit(70) from error


if __name__ == "__main__":
    main()
