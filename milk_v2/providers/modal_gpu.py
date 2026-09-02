"""Explicit Modal fallback for the one sealed Milk candidate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from .. import summary


APP_FILE = Path(__file__).resolve().parents[2] / "images/serve/modal_app.py"
NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,62}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
ACTIVE = {"deployed", "running", "initializing"}


class ProviderError(RuntimeError):
    def __init__(self, message: str, provider_calls: int, *, ambiguous: bool = False):
        super().__init__(message)
        self.provider_calls = provider_calls
        self.ambiguous = ambiguous


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or "\n" in value or "\r" in value:
        raise ProviderError(f"{name} is required and must be one line", 0)
    return value


def _binary() -> str:
    binary = shutil.which(os.environ.get("MILK_MODAL_CLI", "modal"))
    if binary is None:
        raise ProviderError("Modal CLI is not installed", 0)
    return binary


def _python() -> str:
    binary = Path(_binary()).resolve()
    first = binary.read_text(errors="ignore").splitlines()[0]
    if not first.startswith("#!") or not Path(first[2:]).is_file():
        raise ProviderError("cannot locate the Modal CLI Python runtime", 0)
    return first[2:]


def plan(identity: dict, artifact_sha256: str) -> dict:
    environment = os.environ.get("MODAL_ENVIRONMENT", "main")
    app_prefix = os.environ.get("MILK_MODAL_CANDIDATE_APP_PREFIX", "milk-candidate")
    volume_prefix = os.environ.get("MILK_MODAL_CANDIDATE_VOLUME_PREFIX", "milk-candidate")
    routing_region = os.environ.get("MILK_MODAL_ROUTING_REGION", "us-west")
    app_name = f"{app_prefix}-{artifact_sha256[:20]}"
    volume_name = f"{volume_prefix}-{artifact_sha256[:20]}"
    if (
        SHA256.fullmatch(artifact_sha256) is None
        or not environment
        or len(environment) > 128
        or NAME.fullmatch(app_name) is None
        or NAME.fullmatch(volume_name) is None
        or routing_region not in {"us-east", "us-west", "ca-central", "eu-west", "ap-south"}
    ):
        raise ProviderError("Modal candidate configuration is invalid", 0)
    _required("MODAL_TOKEN_ID")
    _required("MODAL_TOKEN_SECRET")
    return {
        "schema_version": "milk.modal-candidate-plan.v2",
        "artifact_sha256": artifact_sha256,
        "app_name": app_name,
        "volume_name": volume_name,
        "environment": environment,
        "routing_region": routing_region,
        "serve_image": identity["serve_image"],
        "accelerator": identity["accelerator"],
        "activation_scale": identity["server"]["quantization"]["activation_scale"],
        "linear_count": identity["server"]["quantization"]["quantized_linear_count"],
        "app_source_sha256": hashlib.sha256(APP_FILE.read_bytes()).hexdigest(),
    }


def _environment(plan: dict, extra: dict[str, str] | None = None) -> dict[str, str]:
    environment = {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "MODAL_ENVIRONMENT": plan["environment"],
        "MODAL_TOKEN_ID": _required("MODAL_TOKEN_ID"),
        "MODAL_TOKEN_SECRET": _required("MODAL_TOKEN_SECRET"),
    }
    environment.update(extra or {})
    return environment


def _execute(plan: dict, arguments: list[str], *, extra: dict[str, str] | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            arguments,
            cwd=APP_FILE.parents[2],
            env=_environment(plan, extra),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProviderError(
            f"Modal operation outcome is ambiguous: {type(error).__name__}", 1, ambiguous=True
        ) from error


def _json(plan: dict, arguments: list[str]) -> list[dict]:
    result = _execute(plan, [_binary(), *arguments], timeout=120)
    if result.returncode != 0:
        raise ProviderError("Modal observation failed", 1, ambiguous=True)
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ProviderError("Modal observation returned invalid JSON", 1) from error
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ProviderError("Modal observation returned a non-array", 1)
    return value


def _manifest(model: dict) -> dict:
    files = model.get("output", {}).get("files")
    if not isinstance(files, list) or not files:
        raise ProviderError("trained model has no checkpoint inventory", 0)
    expected = []
    for item in files:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not item["path"]
            or type(item.get("bytes")) is not int
            or item["bytes"] < 1
            or not isinstance(item.get("sha256"), str)
            or SHA256.fullmatch(item["sha256"]) is None
        ):
            raise ProviderError("trained checkpoint inventory is invalid", 0)
        expected.append({key: item[key] for key in ("path", "bytes", "sha256")})
    expected.sort(key=lambda item: item["path"])
    identity = {
        "schema_version": "milk.modal-candidate-cache.v2",
        "artifact_sha256": model["candidate_artifact_sha256"],
        "files": expected,
    }
    return {**identity, "manifest_sha256": summary.digest(identity)}


def _marker(plan: dict, manifest: dict, volume_exists: bool) -> tuple[bool, int]:
    if not volume_exists:
        return False, 0
    result = _execute(
        plan,
        [
            _binary(), "volume", "get", "-e", plan["environment"], plan["volume_name"],
            f"/{plan['artifact_sha256']}/.milk-checkpoint.json", "-",
        ],
        timeout=120,
    )
    if result.returncode != 0:
        if b"No such file or directory" in result.stderr:
            return False, 1
        raise ProviderError("cannot observe the Modal candidate cache", 1, ambiguous=True)
    try:
        value = json.loads(result.stdout.splitlines()[0])
    except (IndexError, json.JSONDecodeError) as error:
        raise ProviderError("Modal candidate cache marker is invalid", 1) from error
    if value != manifest:
        raise ProviderError("Modal candidate cache marker differs", 1)
    return True, 1


def observe(plan: dict, manifest: dict) -> dict:
    volumes = _json(plan, ["volume", "list", "-e", plan["environment"], "--json"])
    calls = 1
    volume_exists = any(item.get("name") == plan["volume_name"] for item in volumes)
    cache_ready, marker_calls = _marker(plan, manifest, volume_exists)
    calls += marker_calls
    apps = _json(plan, ["app", "list", "-e", plan["environment"], "--json"])
    calls += 1
    matches = [item for item in apps if item.get("description") == plan["app_name"]]
    active = [item for item in matches if item.get("state") in ACTIVE]
    if len(active) > 1:
        raise ProviderError("multiple active Modal candidate apps share one identity", calls, ambiguous=True)
    app = active[0] if active else (matches[0] if matches else None)
    containers = []
    endpoint = None
    if app and app.get("app_id"):
        containers = _json(
            plan,
            ["container", "list", "-e", plan["environment"], "--app-id", app["app_id"], "--json"],
        )
        calls += 1
        if app.get("state") == "deployed":
            code = (
                "import modal,sys;"
                "u=modal.Server.from_name(sys.argv[1],'Candidate',environment_name=sys.argv[2]).get_url();"
                "print(u or '')"
            )
            result = _execute(plan, [_python(), "-c", code, plan["app_name"], plan["environment"]], timeout=120)
            calls += 1
            if result.returncode == 0:
                endpoint = result.stdout.decode().strip() or None
    return {
        "app_id": app.get("app_id") if app else None,
        "app_state": app.get("state") if app else "absent",
        "active_containers": len(containers),
        "volume_exists": volume_exists,
        "cache_ready": cache_ready,
        "endpoint_url": endpoint,
        "provider_calls": calls,
    }


def _checkpoint_files(model: dict, provider_files: list[dict]) -> list[dict]:
    expected = model["output"]["files"]
    result = []
    for item in expected:
        relative = "merged/" + item["path"]
        matches = [value for value in provider_files if value.get("relative_file_name") == relative]
        if len(matches) != 1 or not isinstance(matches[0].get("url"), str):
            raise ProviderError(f"Baseten checkpoint is missing {relative}", 0)
        if matches[0].get("size_bytes") != item["bytes"]:
            raise ProviderError(f"Baseten checkpoint size differs for {relative}", 0)
        result.append({**item, "url": matches[0]["url"]})
    return result


def _mutate(plan: dict, arguments: list[str], manifest: dict, *, extra: dict[str, str] | None = None, timeout: int = 1800) -> tuple[dict, int]:
    _execute(plan, arguments, extra=extra, timeout=timeout)
    after = observe(plan, manifest)
    calls = 1 + after["provider_calls"]
    return after, calls


def ensure(identity: dict, artifact_sha256: str, model: dict, baseten_client) -> dict:
    _required("MILK_CANDIDATE_API_KEY")
    plan_value = plan(identity, artifact_sha256)
    model = {**model, "candidate_artifact_sha256": artifact_sha256}
    manifest = _manifest(model)
    observation = observe(plan_value, manifest)
    calls = observation["provider_calls"]

    if not observation["volume_exists"]:
        observation, used = _mutate(
            plan_value,
            [_binary(), "volume", "create", "-e", plan_value["environment"], plan_value["volume_name"]],
            manifest,
            timeout=300,
        )
        calls += used
        if not observation["volume_exists"]:
            raise ProviderError("Modal volume create is unresolved", calls, ambiguous=True)

    if observation["app_state"] != "deployed":
        extra = {
            "MILK_MODAL_CANDIDATE_APP_NAME": plan_value["app_name"],
            "MILK_MODAL_CANDIDATE_VOLUME_NAME": plan_value["volume_name"],
            "MILK_MODAL_ROUTING_REGION": plan_value["routing_region"],
            "MILK_SERVE_IMAGE": plan_value["serve_image"],
            "MILK_CANDIDATE_ARTIFACT_SHA256": artifact_sha256,
            "MILK_CANDIDATE_ACTIVATION_SCALE": str(plan_value["activation_scale"]),
            "MILK_CANDIDATE_LINEAR_COUNT": str(plan_value["linear_count"]),
            "MILK_CANDIDATE_ACCELERATOR": plan_value["accelerator"],
            "MILK_CANDIDATE_API_KEY": _required("MILK_CANDIDATE_API_KEY"),
        }
        observation, used = _mutate(
            plan_value,
            [
                _binary(), "deploy", str(APP_FILE), "--name", plan_value["app_name"],
                "-e", plan_value["environment"], "--tag", artifact_sha256[:50],
            ],
            manifest,
            extra=extra,
            timeout=1800,
        )
        calls += used
        if observation["app_state"] != "deployed":
            raise ProviderError("Modal candidate deploy is unresolved", calls, ambiguous=True)

    if not observation["cache_ready"]:
        project_id = identity["training_provider"].get("project_id")
        job_id = identity["training_provider"]["job_id"]
        if not isinstance(project_id, str) or not project_id:
            raise ProviderError("candidate has no Baseten training project", calls)
        provider_files = baseten_client.checkpoint_files(project_id, job_id)
        files = _checkpoint_files(model, provider_files)
        with tempfile.NamedTemporaryFile(mode="w", prefix="milk-modal-checkpoint-", suffix=".json", delete=False) as handle:
            json.dump(files, handle, sort_keys=True, separators=(",", ":"))
            input_path = handle.name
        os.chmod(input_path, 0o600)
        try:
            code = (
                "import json,modal,sys;"
                "x=json.load(open(sys.argv[3]));"
                "f=modal.Function.from_name(sys.argv[1],'hydrate',environment_name=sys.argv[2]);"
                "print(json.dumps(f.remote(x),sort_keys=True,separators=(',',':')))"
            )
            result = _execute(
                plan_value,
                [_python(), "-c", code, plan_value["app_name"], plan_value["environment"], input_path],
                timeout=60 * 60,
            )
        finally:
            os.unlink(input_path)
        calls += 1
        observation = observe(plan_value, manifest)
        calls += observation["provider_calls"]
        if not observation["cache_ready"]:
            raise ProviderError("Modal candidate hydration is unresolved", calls, ambiguous=True)

    if not observation.get("endpoint_url"):
        observation = observe(plan_value, manifest)
        calls += observation["provider_calls"]
    if observation["app_state"] != "deployed" or not observation.get("endpoint_url"):
        return {"state": "active", "plan": plan_value, "observation": observation, "provider_calls": calls}
    return {"state": "ready", "plan": plan_value, "observation": observation, "provider_calls": calls}


def stop_candidate(identity: dict, artifact_sha256: str, model: dict, timeout: int = 180) -> dict:
    plan_value = plan(identity, artifact_sha256)
    manifest = _manifest({**model, "candidate_artifact_sha256": artifact_sha256})
    result = stop(plan_value, manifest, timeout)
    return {**result, "plan": plan_value}


def stop(plan_value: dict, manifest: dict, timeout: int = 180) -> dict:
    observation = observe(plan_value, manifest)
    calls = observation["provider_calls"]
    if observation["app_id"] and observation["app_state"] in ACTIVE:
        result = _execute(
            plan_value,
            [_binary(), "app", "stop", "-y", "-e", plan_value["environment"], observation["app_id"]],
            timeout=120,
        )
        calls += 1
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        observation = observe(plan_value, manifest)
        calls += observation["provider_calls"]
        if observation["active_containers"] == 0 and observation["app_state"] not in ACTIVE:
            return {"state": "zero", "observation": observation, "provider_calls": calls}
        time.sleep(3)
    raise ProviderError("Modal candidate did not reach zero capacity", calls, ambiguous=True)
