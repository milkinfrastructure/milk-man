#!/usr/bin/env python3
"""One env-selected, cached-weight vLLM deployment; run, observe, or stop it."""

from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from milk_v2.providers import baseten
from milk_v2.providers.modal_controller import atomic_json, digest, now, read_json, state_root
from milk_v2.providers.modal_serve import api_mode, locked
from milk_v2.store import open_store, settings_from_environment
from milk_v2.state import redact


IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
READY = {"ACTIVE", "SCALED_TO_ZERO"}
FAILED = {"BUILD_FAILED", "BUILD_STOPPED", "DEPLOY_FAILED", "FAILED", "UNHEALTHY"}
OWNED = {"--model", "--revision", "--host", "--port", "--served-model-name", "--tensor-parallel-size", "--api-key", "--hf-token"}


def setting(name: str, default: str = "") -> str:
    value = os.environ.get("MILK_BASETEN_SERVE_" + name, default)
    if not value or len(value) > 1024 or any(ord(c) < 32 for c in value):
        raise ValueError(f"MILK_BASETEN_SERVE_{name} must be a nonempty single line")
    return value


def number(name: str, default: int, minimum: int = 1) -> int:
    value = int(setting(name, str(default)))
    if value < minimum:
        raise ValueError(f"MILK_BASETEN_SERVE_{name} must be at least {minimum}")
    return value


def checkpoint(model: str, revision: str) -> dict | None:
    key = os.environ.get("MILK_BASETEN_SERVE_CHECKPOINT_KEY")
    expected = os.environ.get("MILK_BASETEN_SERVE_CHECKPOINT_SHA256")
    if key is None and expected is None:
        return None
    settings = settings_from_environment()
    if (not key or not expected or not re.fullmatch(r"[0-9a-f]{64}", expected)
            or not re.fullmatch(re.escape(settings.scope_prefix) + r"m/[0-9a-f-]{36}/manifest\.json", key)):
        raise ValueError("set CHECKPOINT_KEY and CHECKPOINT_SHA256 to an exact model manifest in this scope")
    raw = open_store(settings).get(key).body
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("checkpoint manifest digest differs")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schema_version") != "milk.model.v2":
        raise ValueError("checkpoint must be a Milk model manifest")
    provider = value.get("provider") or {}
    if (not isinstance(provider, dict) or provider.get("name") != "baseten" or provider.get("status") != "TRAINING_JOB_COMPLETED"
            or not IDENTIFIER.fullmatch(str(provider.get("job_id", "")))
            or value.get("student_base") != {"model_repo": model, "model_revision": revision}
            or key != settings.scope_prefix + f"m/{value.get('model_uuid')}/manifest.json"):
        raise ValueError("checkpoint provider, base model, revision or model UUID differs")
    return {"key": key, "sha256": expected, "model_uuid": value["model_uuid"], "provider": provider}


def plan() -> dict:
    model, revision, image = setting("MODEL"), setting("REVISION"), setting("IMAGE")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", model) or not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise ValueError("model must be a Hugging Face repository and revision an exact commit")
    if any(c.isspace() for c in image) or ":" not in image or image.endswith(":latest"):
        raise ValueError("image must have an explicit version tag or digest")
    gpu, count = setting("GPU", "L4"), number("GPU_COUNT", 1)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", gpu):
        raise ValueError("GPU must be a Baseten accelerator name; use GPU_COUNT separately")
    arguments = json.loads(setting("VLLM_ARGS_JSON", "[]"))
    if not isinstance(arguments, list) or any(
        not isinstance(arg, str) or not arg or any(ord(c) < 32 for c in arg)
        or arg.split("=", 1)[0] in OWNED for arg in arguments
    ):
        raise ValueError("VLLM_ARGS_JSON must be arguments without job-owned model, binding, or key flags")
    served = setting("SERVED_MODEL", model)
    trained = checkpoint(model, revision)
    model_path = f"/tmp/training_checkpoints/{trained['provider']['job_id']}/rank-0/merged" if trained else "/models/milk"
    weights = {"source": f"hf://{model}@{revision}", "mount_location": "/models/milk"}
    secret = os.environ.get("MILK_BASETEN_SERVE_HF_SECRET_NAME")
    if secret:
        if not IDENTIFIER.fullmatch(secret):
            raise ValueError("HF_SECRET_NAME must name an existing Baseten secret")
        weights["auth"] = {"auth_method": "CUSTOM_SECRET", "auth_secret_name": secret}
    concurrency = number("CONCURRENCY", 1)
    autoscaling = {
        "min_replica": number("MIN_REPLICAS", 0, 0),
        "max_replica": number("MAX_REPLICAS", 1),
        "scale_down_delay": number("SCALEDOWN_SECONDS", 300),
        "concurrency_target": concurrency,
    }
    if autoscaling["min_replica"] > autoscaling["max_replica"]:
        raise ValueError("MIN_REPLICAS cannot exceed MAX_REPLICAS")
    config = {
        "model_metadata": {"tags": ["openai-compatible"]},
        "base_image": {"image": image},
        "docker_server": {
            "start_command": shlex.join([
                "vllm", "serve", model_path, "--served-model-name", served,
                "--host", "0.0.0.0", "--port", "8000", "--tensor-parallel-size", str(count), *arguments,
            ]),
            "server_port": 8000, "predict_endpoint": "/v1/chat/completions",
            "readiness_endpoint": "/health", "liveness_endpoint": "/health",
        },
        "weights": [weights],
        "resources": {"accelerator": f"{gpu}:{count}", "use_gpu": True},
        "runtime": {"predict_concurrency": concurrency, "streaming_read_timeout": 120},
    }
    if trained:
        del config["weights"]
        config["training_checkpoints"] = {
            "download_folder": "/tmp/training_checkpoints",
            "artifact_references": [{"training_job_id": trained["provider"]["job_id"], "paths": ["rank-0/merged/*"]}],
        }
    elif secret:
        config["secrets"] = {secret: None}
    value = {
        "provider": "baseten", "model": model, "revision": revision, "served_model": served,
        "gpu": gpu, "gpu_count": count, "image": image, "truss_version": baseten.TRUSS_VERSION,
        "team": os.environ.get("BASETEN_TEAM_NAME"), "config": config, "autoscaling": autoscaling,
    }
    if trained:
        value["checkpoint"] = trained
    identity = digest(value)
    return {**value, "profile_id": identity, "model_name": f"milk-serve-{identity[:20]}", "deployment_name": identity[:32]}


def save(path: Path, record: dict, action: str) -> None:
    record = {**record, "updated_at": now(), "action": action}
    atomic_json(path / "receipts" / f"{digest(record)}.json", record)
    atomic_json(path / "current.json", record)


def observe(client: baseten.Client, value: dict, record: dict) -> dict:
    model_id, deployment_id = record.get("model_id"), record.get("deployment_id")
    if not model_id or not deployment_id:
        models = [item for item in client.models() if item.get("name") == value["model_name"]]
        if len(models) > 1:
            raise ValueError("multiple Baseten models match this serving profile")
        if not models:
            return {"status": "absent", "active_replica_count": 0}
        model_id = models[0].get("id")
        if not isinstance(model_id, str) or not IDENTIFIER.fullmatch(model_id):
            raise ValueError("Baseten returned an invalid model ID")
        deployments = [item for item in client.deployments(model_id) if item.get("name") == value["deployment_name"]]
        if len(deployments) != 1:
            raise ValueError("Baseten model exists without exactly one matching deployment; do not resubmit")
        deployment_id = deployments[0].get("id")
    if not all(isinstance(v, str) and IDENTIFIER.fullmatch(v) for v in (model_id, deployment_id)):
        raise ValueError("Baseten deployment identity is invalid")
    deployment = client.deployment(model_id, deployment_id)
    if deployment.get("name") != value["deployment_name"] or (deployment.get("labels") or {}).get("milk-serve-profile") != value["profile_id"]:
        raise ValueError("Baseten deployment does not match the saved serving profile")
    return {key: deployment.get(key) for key in (
        "model_id", "id", "status", "active_replica_count", "instance_type_name", "autoscaling_settings",
    )}


def output(value: dict, record: dict, observed: dict | None, calls: int, *, include_driver: bool = True) -> dict:
    status = (observed or {}).get("status")
    settings = (observed or {}).get("autoscaling_settings") or {}
    configured = all(settings.get(key) == expected for key, expected in value["autoscaling"].items())
    if status in READY and configured:
        state = "complete"
    elif status in FAILED:
        state = "failed"
    elif status == "INACTIVE" or (status == "absent" and not record.get("submitted")):
        state = "idle"
    elif status == "absent":
        state = "blocked"
    else:
        state = "active"
    details = {"provider": "baseten", "plan": value, "observation": observed, "configuration_applied": configured, "retained_state": str(record.get("state_path", ""))}
    if status in READY and not configured:
        details["next"] = "run serve-baseten again to apply the selected autoscaling settings; this reuses the existing deployment"
    if include_driver and observed and observed.get("id"):
        mode = api_mode("MILK_BASETEN_SERVE_API_MODE")
        endpoint = "/v1/responses" if mode == "responses" else "/v1/chat/completions"
        details["driver"] = {
            "api_url": f"https://model-{observed['model_id']}.api.baseten.co/deployment/{observed['id']}/sync{endpoint}",
            "api_mode": mode, "auth_scheme": "Bearer",
            "model": value["served_model"], "api_key_env": "BASETEN_API_KEY",
        }
    return {"state": state, "identity": value["profile_id"], "provider_calls": calls, "inference_calls": 0, "details": details}


def execute(action: str, path: Path, client: baseten.Client) -> dict:
    record = read_json(path / "current.json") or {}
    value = plan() if action == "run" else record.get("plan") or plan()
    if record.get("plan", {}).get("profile_id") not in (None, value["profile_id"]):
        old = observe(client, record["plan"], record)
        if old["status"] != "INACTIVE" or old.get("active_replica_count") != 0:
            raise ValueError("stop the saved Baseten deployment and verify zero replicas before changing profiles")
        record = {}
    record = {**record, "plan": value, "state_path": str(path / "current.json")}
    observed = observe(client, value, record)
    if action == "run":
        if observed["status"] == "absent":
            if record.get("submitted"):
                raise ValueError("a prior submission has no visible deployment; reconcile it before any retry")
            record["submitted"] = True
            save(path, record, "submit")
            client.calls += 1
            try:
                pushed = baseten.push(
                    {**value["config"], "model_name": value["model_name"]}, value["model_name"], value["deployment_name"],
                    labels={"milk-serve-profile": value["profile_id"]}, timeout=number("PUSH_TIMEOUT_SECONDS", 600),
                )
            except baseten.ProviderError as error:
                if not error.ambiguous:
                    record["submitted"] = False
                    save(path, record, "rejected")
                raise
            record.update(model_id=pushed.get("model_id"), deployment_id=pushed.get("model_version_id"))
            save(path, record, "submitted")
            observed = observe(client, value, record)
        if observed.get("id"):
            record.update(model_id=observed["model_id"], deployment_id=observed["id"])
            if observed["status"] == "INACTIVE":
                save(path, record, "activate")
                client.set_active(record["model_id"], record["deployment_id"], True)
                observed = observe(client, value, record)
            if observed.get("autoscaling_settings") is not None and any(
                observed["autoscaling_settings"].get(key) != expected for key, expected in value["autoscaling"].items()
            ):
                client.autoscale(record["model_id"], record["deployment_id"], value["autoscaling"])
                observed = observe(client, value, record)
            record["observation"] = observed
            save(path, record, "observe")
    elif action == "stop":
        if observed.get("id"):
            record.update(model_id=observed["model_id"], deployment_id=observed["id"])
            if observed["status"] not in {"INACTIVE", "DEACTIVATING"}:
                save(path, record, "deactivate")
                client.set_active(record["model_id"], record["deployment_id"], False)
                observed = observe(client, value, record)
            record["observation"] = observed
            save(path, record, "stop")
    result = output(value, record, observed, client.calls, include_driver=action != "stop")
    if action == "status" and (seconds := number("LOG_SECONDS", 0, 0)):
        if seconds > 3600:
            raise ValueError("LOG_SECONDS must be at most 3600")
        if observed.get("id"):
            end = int(time.time() * 1000)
            try:
                logs = client.deployment_logs(observed["model_id"], observed["id"], end - seconds * 1000, end)
            except baseten.ProviderError:
                result["details"]["logs_error"] = "Baseten log fetch failed; resource status is unchanged"
            else:
                result["details"]["logs"] = [
                    {"timestamp": row.get("timestamp"), "message": redact(str(row.get("message", "")))[:384]}
                    for row in sorted(logs, key=lambda row: str(row.get("timestamp", "")))[-20:]
                ]
                result["details"]["logs_truncated"] = len(logs) > 20 or any(len(str(row.get("message", ""))) > 384 for row in logs)
            result["provider_calls"] = client.calls
    if action == "stop":
        stopped = observed["status"] == "INACTIVE" and observed.get("active_replica_count") == 0
        absent = observed["status"] == "absent" and not record.get("submitted")
        result["state"] = "complete" if stopped or absent else "blocked" if observed["status"] == "absent" else "active"
        result["details"]["zero_replicas_verified"] = stopped or absent
    return result


def main() -> None:
    client = None
    try:
        action = sys.argv[1] if len(sys.argv) == 2 else ""
        if action != "stop":
            api_mode("MILK_BASETEN_SERVE_API_MODE")
        if action == "plan":
            print(json.dumps({"state": "planned", "provider_calls": 0, "inference_calls": 0, "details": plan()}, sort_keys=True))
            return
        if action not in {"run", "status", "stop"}:
            raise ValueError("action must be plan, run, status, or stop")
        path = state_root() / "serve-baseten"
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        client = baseten.Client(os.environ.get("BASETEN_API_KEY", ""), number("API_TIMEOUT_SECONDS", 30))
        with nullcontext() if action == "status" else locked(path):
            result = execute(action, path, client)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if result["state"] in {"failed", "blocked"}:
            raise SystemExit(70 if result["state"] == "failed" else 75)
    except BlockingIOError:
        print(json.dumps({"state": "blocked", "identity": "unknown", "error": "another Baseten serving operation is active", "provider_calls": 0, "inference_calls": 0}))
        raise SystemExit(75)
    except (ValueError, OSError, baseten.ProviderError) as error:
        message = str(error)
        for name, value in os.environ.items():
            if len(value) >= 8 and any(word in name.upper() for word in ("KEY", "TOKEN", "SECRET")):
                message = message.replace(value, "[redacted]")
        print(json.dumps({"state": "failed", "identity": "unknown", "error": message, "provider_calls": client.calls if client else 0, "inference_calls": 0}))
        raise SystemExit(70) from error


if __name__ == "__main__":
    main()
