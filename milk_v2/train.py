from __future__ import annotations

import json
import math
import os
import re
import uuid

from . import dataset, summary
from .providers import baseten


CODE_VERSION = "milk.train.v2.4"
IMAGE = re.compile(r"ghcr\.io/milkinfrastructure/milk-man-train@sha256:[0-9a-f]{64}\Z")
PROJECT = re.compile(r"[a-z0-9]{5,32}\Z")
TERMINAL_FAILURE = {"TRAINING_JOB_FAILED", "TRAINING_JOB_STOPPED", "TRAINING_JOB_CANCELED"}
BASETEN_BASE_IMAGE = "pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime@sha256:c16f4c749e2d9e96878875cdf6cc45cddda1d1a36fddd371dd6f2360f1b6e2a2"
TRANSFORMERS_SOURCE = "https://github.com/huggingface/transformers/archive/ac3244569528944b9d5773cafea525cd8a8b63de.zip"
TRAIN_SOURCE_URL = "https://raw.githubusercontent.com/milkinfrastructure/milk-man/a454beba54075d4910c9ff776c0411f3cda1429c/images/train/train.py"
TRAIN_SOURCE_SHA256 = "238e1d710529e209e700995839ee6fcc5c587f0d89ea6095befee248af54ac68"
REINFORCE_SOURCE_URL = "https://raw.githubusercontent.com/milkinfrastructure/milk-man/89875d6b7f8610703a4dfe383c62f84be35a9d2a/images/train/train.py"
REINFORCE_SOURCE_SHA256 = "a123dea785ad619f76de5a23944004af33fbf1b50657c549ee851860d8afac42"


class TrainError(ValueError):
    pass


class ProviderError(RuntimeError):
    def __init__(self, message: str, provider_calls: int, *, ambiguous: bool = False):
        super().__init__(message)
        self.provider_calls = provider_calls
        self.ambiguous = ambiguous


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise TrainError(f"{name} is required")
    return value


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise TrainError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise TrainError(f"{name} must be in {minimum}..{maximum}")
    return value


def _object(store, key: str) -> tuple[dict, bytes]:
    body = store.get(key).body
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TrainError(f"{key} is invalid JSON") from error
    if not isinstance(value, dict):
        raise TrainError(f"{key} must contain an object")
    return value, body


def current(store, settings, runtime) -> dict | None:
    try:
        status, unused_status = _object(store, settings.scope_prefix + "status/current.json")
        dataset_reference = dataset.current(store, settings, runtime)
    except FileNotFoundError:
        return None
    if dataset_reference is None:
        return None
    reference = status.get("training")
    if not isinstance(reference, dict):
        return None
    try:
        model, model_body = _object(store, reference.get("key", ""))
    except FileNotFoundError:
        return None
    if (
        reference.get("schema_version") != "milk.model-reference.v2"
        or reference.get("scope_id") != settings.scope_id
        or summary.digest(model_body) != reference.get("sha256")
        or model.get("schema_version") != "milk.model.v2"
        or model.get("model_uuid") != reference.get("uuid")
        or model.get("scope_id") != settings.scope_id
        or model.get("profile") != settings.profile
        or model.get("job_id") != reference.get("training_job_id")
        or model.get("dataset_uuid") != dataset_reference.get("uuid")
        or model.get("student_base") != {
            "model_repo": runtime.student_base.model_repo,
            "model_revision": runtime.student_base.model_revision,
        }
    ):
        return None
    return reference


def _settings(settings, reference: dict) -> dict:
    if settings.kind != "s3":
        raise TrainError("remote training requires an S3-compatible dataset store")
    image = _required("MILK_TRAIN_IMAGE")
    if IMAGE.fullmatch(image) is None:
        raise TrainError("MILK_TRAIN_IMAGE must pin the reviewed GHCR image by sha256 digest")
    project_id = _required("BASETEN_TRAINING_PROJECT_ID")
    if PROJECT.fullmatch(project_id) is None:
        raise TrainError("BASETEN_TRAINING_PROJECT_ID is invalid")
    accelerator = os.environ.get("BASETEN_TRAINING_ACCELERATOR", "H100")
    if accelerator not in {"H100", "H200"}:
        raise TrainError("BASETEN_TRAINING_ACCELERATOR must be H100 or H200")
    secret_map_raw = os.environ.get(
        "MILK_BASETEN_RUNTIME_SECRET_MAP_JSON",
        '{"MILK_STORE_ACCESS_KEY_ID":"milk-control-store-access-key-id","MILK_STORE_SECRET_ACCESS_KEY":"milk-control-store-secret-access-key"}',
    )
    try:
        secret_map = json.loads(secret_map_raw)
    except json.JSONDecodeError as error:
        raise TrainError("MILK_BASETEN_RUNTIME_SECRET_MAP_JSON is invalid JSON") from error
    required_secrets = {"MILK_STORE_ACCESS_KEY_ID", "MILK_STORE_SECRET_ACCESS_KEY"}
    if not isinstance(secret_map, dict) or set(secret_map) != required_secrets or any(not isinstance(value, str) or not value for value in secret_map.values()):
        raise TrainError("MILK_BASETEN_RUNTIME_SECRET_MAP_JSON must map the two reviewed store credentials")
    try:
        learning_rate = float(os.environ.get("MILK_TRAIN_LEARNING_RATE", "2e-6"))
    except ValueError as error:
        raise TrainError("MILK_TRAIN_LEARNING_RATE must be numeric") from error
    if not 0 < learning_rate <= 1e-3:
        raise TrainError("MILK_TRAIN_LEARNING_RATE is outside the reviewed range")
    recipe = os.environ.get("MILK_TRAIN_RECIPE", "sft")
    if recipe not in {"sft", "reinforce"}:
        raise TrainError("MILK_TRAIN_RECIPE must be sft or reinforce")
    steps = _integer("MILK_TRAIN_STEPS", 1 if settings.profile == "mechanics" else 64, 1, 1024)
    if recipe == "reinforce" and steps != 1:
        raise TrainError("MILK_TRAIN_STEPS must be 1 for reinforce")
    config = {
        "provider": "baseten",
        "project_id": project_id,
        "release_image": image,
        "baseten_base_image": BASETEN_BASE_IMAGE,
        "train_source_url": TRAIN_SOURCE_URL,
        "train_source_sha256": TRAIN_SOURCE_SHA256,
        "accelerator": accelerator,
        "availability_model": "dedicated",
        "runtime_secret_map": secret_map,
        "steps": steps,
        "max_tokens": _integer("MILK_TRAIN_MAX_TOKENS", 2048, 128, 8192),
        "learning_rate": learning_rate,
        "dataset": {key: reference[key] for key in ("uuid", "key", "sha256", "counts")},
    }
    if recipe == "reinforce":
        config.update({
            "recipe": recipe,
            "train_source_url": REINFORCE_SOURCE_URL,
            "train_source_sha256": REINFORCE_SOURCE_SHA256,
            "rollouts": _integer("MILK_TRAIN_ROLLOUTS", 4, 2, 16),
            "rollout_max_new_tokens": _integer("MILK_TRAIN_ROLLOUT_MAX_NEW_TOKENS", 256, 1, 1024),
        })
    return config


def _job_body(settings, runtime, manifest: dict, config: dict, job_id: str) -> dict:
    environment = {
        "MILK_SCOPE_ID": settings.scope_id,
        "MILK_STORE_ENDPOINT": settings.endpoint,
        "MILK_STORE_REGION": settings.region,
        "MILK_STORE_BUCKET": settings.bucket,
        "MILK_DATASET_MANIFEST_KEY": config["dataset"]["key"],
        "MILK_DATASET_MANIFEST_SHA256": config["dataset"]["sha256"],
        "MILK_TRAIN_JOB_ID": job_id,
        "MILK_TRAIN_STEPS": str(config["steps"]),
        "MILK_TRAIN_MAX_TOKENS": str(config["max_tokens"]),
        "MILK_TRAIN_LEARNING_RATE": str(config["learning_rate"]),
    }
    if config.get("recipe") == "reinforce":
        environment.update({
            "MILK_TRAIN_RECIPE": "reinforce",
            "MILK_TRAIN_ROLLOUTS": str(config["rollouts"]),
            "MILK_TRAIN_ROLLOUT_MAX_NEW_TOKENS": str(config["rollout_max_new_tokens"]),
        })
    environment.update({name: {"name": secret} for name, secret in config["runtime_secret_map"].items()})
    fetch_source = (
        "python -c \"import hashlib,urllib.request;"
        f"u='{config['train_source_url']}';b=urllib.request.urlopen(u,timeout=30).read();"
        f"assert hashlib.sha256(b).hexdigest()=='{config['train_source_sha256']}';"
        "open('/tmp/milk-train.py','wb').write(b)\""
    )
    return {
        "image": {"base_image": config["baseten_base_image"], "docker_auth": None},
        "compute": {
            "node_count": 1,
            "cpu_count": 4,
            "memory": "32Gi",
            "accelerator": {"accelerator": config["accelerator"], "count": 1},
            "availability_model": config["availability_model"],
        },
        "runtime": {
            "start_commands": [
                f"python -m pip install --no-cache-dir boto3==1.40.40 {TRANSFORMERS_SOURCE} zstandard==0.25.0",
                fetch_source,
                "mkdir -p /models && ln -sfn /app/models/qwen3.5-0.8b /models/qwen3.5-0.8b",
                "python /tmp/milk-train.py",
            ],
            "environment_variables": environment,
            "cache_config": {"enabled": True, "require_cache_affinity": False},
            "checkpointing_config": {"enabled": True, "checkpoint_path": "/mnt/ckpts", "volume_size_gib": 10},
        },
        "name": "milk-" + job_id[:20],
        "weights": [{
            "source": f"hf://{runtime.student_base.model_repo}@{runtime.student_base.model_revision}",
            "mount_location": "/app/models/qwen3.5-0.8b",
        }],
        "enable_baseten_workdir": False,
        "priority": 0,
    }


def _artifacts(store, keys: list[str]) -> list[dict]:
    return [{"key": key, "sha256": summary.digest(store.get(key).body)} for key in keys]


def _advance_status(store, settings, reference: dict, next_action: str = "evaluate") -> str:
    key = settings.scope_prefix + "status/current.json"
    value, unused = _object(store, key)
    if value.get("schema_version") != "milk.status.v2" or value.get("scope_id") != settings.scope_id:
        raise TrainError("current status identity differs")
    updated = {**value, "next_action": next_action}
    if reference:
        updated["training"] = reference
    summary._advance(store, key, updated)
    return key


def _completed(store, settings, runtime, client, config: dict, manifest: dict, job_id: str, provider_job: dict, prefix: str) -> dict:
    files = client.checkpoint_files(config["project_id"], provider_job["id"])
    result_file = next((item for item in files if item.get("relative_file_name", "").endswith("merged/milk-result.json")), None)
    if not result_file or not isinstance(result_file.get("url"), str):
        return {
            "state": "active",
            "identity": job_id,
            "artifacts": _artifacts(store, [prefix + "intent.json", prefix + "receipt.json"]),
            "provider_calls": client.calls,
            "next": "train",
            "details": {
                "provider": "baseten",
                "project_id": config["project_id"],
                "provider_job_id": provider_job["id"],
                "status": "CHECKPOINT_SYNCING",
                "visible_checkpoint_files": len(files),
            },
        }
    output, output_body = baseten.fetch_json(result_file["url"], client.timeout)
    expected_base = {"model_repo": runtime.student_base.model_repo, "model_revision": runtime.student_base.model_revision}
    expected_parent = {"kind": "hf_base", **expected_base}
    recipe = config.get("recipe", "sft")
    if (
        output.get("schema_version") != "milk.training-output.v2"
        or output.get("job_id") != job_id
        or output.get("dataset_uuid") != manifest.get("dataset_uuid")
        or output.get("student_base") != expected_base
        or output.get("recipe", "sft") != recipe
        or (recipe == "reinforce" and output.get("parent") != expected_parent)
        or (recipe == "sft" and output.get("parent", expected_parent) != expected_parent)
        or output.get("steps") != config["steps"]
        or not isinstance(output.get("files"), list)
        or not any(item.get("path", "").endswith(".safetensors") for item in output["files"] if isinstance(item, dict))
    ):
        raise TrainError("Baseten training output identity differs")
    reinforce = output.get("reinforce")
    if recipe == "reinforce":
        rollouts = reinforce.get("rollouts") if isinstance(reinforce, dict) else None
        mean = reinforce.get("reward_mean_bps") if isinstance(reinforce, dict) else None
        deviation = reinforce.get("reward_std_bps") if isinstance(reinforce, dict) else None
        policy_loss = reinforce.get("policy_loss") if isinstance(reinforce, dict) else None
        updated = reinforce.get("updated") if isinstance(reinforce, dict) else None
        skip_reason = reinforce.get("skip_reason") if isinstance(reinforce, dict) else None
        sampling = reinforce.get("sampling") if isinstance(reinforce, dict) else None
        if (
            not isinstance(reinforce, dict)
            or re.fullmatch(r"[0-9a-f]{64}", reinforce.get("source_request_sha256", "")) is None
            or re.fullmatch(r"[0-9a-f]{64}", reinforce.get("prompt_sha256", "")) is None
            or reinforce.get("rollout_count") != config["rollouts"]
            or not isinstance(rollouts, list)
            or len(rollouts) != config["rollouts"]
            or reinforce.get("rollouts_sha256") != summary.digest(rollouts)
            or not isinstance(mean, (int, float))
            or isinstance(mean, bool)
            or not math.isfinite(mean)
            or not 0 <= mean <= 10_000
            or not isinstance(deviation, (int, float))
            or isinstance(deviation, bool)
            or not math.isfinite(deviation)
            or not 0 <= deviation <= 10_000
            or not isinstance(policy_loss, (int, float))
            or isinstance(policy_loss, bool)
            or not math.isfinite(policy_loss)
            or not isinstance(updated, bool)
            or (updated and (deviation == 0 or skip_reason is not None))
            or (not updated and (deviation != 0 or policy_loss != 0 or skip_reason != "zero_reward_variance"))
            or sampling != {"temperature": 1.0, "top_p": 1.0, "top_k": 0, "max_new_tokens": config["rollout_max_new_tokens"]}
        ):
            raise TrainError("Baseten reinforce output identity differs")
    elif reinforce is not None:
        raise TrainError("Baseten SFT output contains reinforce results")
    if recipe == "reinforce" and not reinforce["updated"]:
        result_key = prefix + "result.json"
        details = {
            "reason": "zero_reward_variance",
            "recipe": recipe,
            "updated": False,
            "rollouts_sha256": reinforce["rollouts_sha256"],
            "reward_mean_bps": reinforce["reward_mean_bps"],
            "reward_std_bps": reinforce["reward_std_bps"],
        }
        result = {
            "schema_version": "milk.train-job-result.v2",
            "job_id": job_id,
            "state": "idle",
            "next": "train",
            "reason": "zero_reward_variance",
            "provider_job_id": provider_job["id"],
            "artifact_keys": [prefix + "intent.json", prefix + "receipt.json", result_key],
            "details": details,
        }
        store.create_same(result_key, summary.canonical(result))
        return {"state": "idle", "identity": job_id, "artifacts": _artifacts(store, result["artifact_keys"]), "provider_calls": client.calls, "next": "train", "details": details}
    model_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:model:" + summary.digest({"job_id": job_id, "output": output})))
    model_key = settings.scope_prefix + f"m/{model_uuid}/manifest.json"
    model = {
        "schema_version": "milk.model.v2",
        "model_uuid": model_uuid,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "job_id": job_id,
        "dataset_uuid": manifest["dataset_uuid"],
        "student_base": expected_base,
        "training_kind": "full_bf16",
        "training_recipe": recipe,
        "parent": expected_parent,
        "provider": {"name": "baseten", "project_id": config["project_id"], "job_id": provider_job["id"], "status": provider_job["current_status"]},
        "images": {"release": config["release_image"], "provider_base": config["baseten_base_image"]},
        "checkpoint_files": [{key: item.get(key) for key in ("relative_file_name", "size_bytes", "last_modified", "node_rank")} for item in files],
        "output_sha256": summary.digest(output_body),
        "output": output,
    }
    model_body = summary.canonical(model)
    store.create_same(model_key, model_body)
    reference = {"schema_version": "milk.model-reference.v2", "scope_id": settings.scope_id, "uuid": model_uuid, "key": model_key, "sha256": summary.digest(model_body), "training_job_id": job_id}
    status_key = _advance_status(store, settings, reference)
    result_key = prefix + "result.json"
    result = {"schema_version": "milk.train-job-result.v2", "job_id": job_id, "state": "progressed", "next": "evaluate", "model": reference, "provider_job_id": provider_job["id"], "artifact_keys": [model_key, status_key, result_key]}
    store.create_same(result_key, summary.canonical(result))
    return {"state": "progressed", "identity": job_id, "artifacts": _artifacts(store, result["artifact_keys"]), "provider_calls": client.calls, "next": "evaluate", "details": {"model_uuid": model_uuid, "provider_job_id": provider_job["id"], "status": provider_job["current_status"], "recipe": recipe}}


def reconcile(store, settings, runtime) -> dict:
    reference = dataset.current(store, settings, runtime)
    if reference is None:
        return {"state": "idle", "identity": summary.digest({"scope_id": settings.scope_id, "reason": "dataset_missing"}), "artifacts": [], "provider_calls": 0, "next": "dataset", "details": {"reason": "dataset_missing"}}
    manifest, manifest_body = _object(store, reference["key"])
    counts = dataset.split_counts(manifest)
    if summary.digest(manifest_body) != reference["sha256"] or reference.get("counts") != counts:
        raise TrainError("dataset manifest digest differs")
    if not dataset.training_ready(counts):
        status_key = _advance_status(store, settings, {}, "summary")
        missing = [split for split in dataset.SPLITS if counts[split] == 0]
        identity = summary.digest({"schema_version": "milk.train-wait.v2", "dataset": reference, "missing_splits": missing})
        return {"state": "idle", "identity": identity, "artifacts": _artifacts(store, [reference["key"], status_key]), "provider_calls": 0, "next": "summary", "details": {"reason": "evaluation_splits_missing", "missing_splits": missing, "counts": counts}}
    config = _settings(settings, reference)
    identity = {
        "schema_version": "milk.train-job-identity.v2",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "dataset": config["dataset"],
        "student_base": {"model_repo": runtime.student_base.model_repo, "model_revision": runtime.student_base.model_revision, "digest": runtime.student_base.digest},
        "settings": {key: value for key, value in config.items() if key != "runtime_secret_map"},
        "runtime_secret_names": config["runtime_secret_map"],
        "config_digest": runtime.digest,
    }
    job_id = summary.digest(identity)
    prefix = settings.scope_prefix + f"j/train/{job_id}/"
    intent_key, receipt_key, result_key = (prefix + name for name in ("intent.json", "receipt.json", "result.json"))
    try:
        prior, unused = _object(store, result_key)
        if prior.get("schema_version") != "milk.train-job-result.v2" or prior.get("job_id") != job_id:
            raise TrainError("stored training result is invalid")
        if prior.get("state") == "idle" and prior.get("reason") == "zero_reward_variance":
            details = prior.get("details")
            if not isinstance(details, dict) or details.get("reason") != "zero_reward_variance" or details.get("updated") is not False or prior.get("next") != "train" or not isinstance(prior.get("artifact_keys"), list):
                raise TrainError("stored no-policy-update result is invalid")
            return {"state": "idle", "identity": job_id, "artifacts": _artifacts(store, prior["artifact_keys"]), "provider_calls": 0, "next": "train", "details": details}
        model = prior.get("model")
        if not isinstance(model, dict):
            raise TrainError("stored training result has no model")
        status_key = _advance_status(store, settings, model)
        return {"state": "idle", "identity": job_id, "artifacts": _artifacts(store, [*prior["artifact_keys"], status_key]), "provider_calls": 0, "next": "evaluate", "details": {"model_uuid": model["uuid"], "provider_job_id": prior["provider_job_id"], "status": "TRAINING_JOB_COMPLETED"}}
    except FileNotFoundError:
        pass

    client = baseten.Client(_required("BASETEN_API_KEY"), _integer("MILK_TRAIN_TIMEOUT_SECONDS", 30, 1, 120))
    body = _job_body(settings, runtime, manifest, config, job_id)
    store.create_same(intent_key, summary.canonical({**identity, "job_id": job_id, "provider_request": body}))
    try:
        receipt, unused = _object(store, receipt_key)
        provider_job_id = receipt.get("provider_job_id")
        if receipt.get("schema_version") != "milk.train-provider-receipt.v2" or receipt.get("job_id") != job_id or not isinstance(provider_job_id, str):
            raise TrainError("stored Baseten receipt is invalid")
    except FileNotFoundError:
        try:
            matches = [job for job in client.jobs(config["project_id"]) if job.get("name") == body["name"]]
        except baseten.ProviderError as error:
            raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
        if len(matches) > 1:
            raise ProviderError("multiple Baseten jobs match the deterministic name", client.calls, ambiguous=True)
        if matches:
            provider_job = matches[0]
        else:
            try:
                provider_job = client.create(config["project_id"], body)
            except baseten.ProviderError as error:
                raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
        provider_job_id = provider_job["id"]
        receipt = {"schema_version": "milk.train-provider-receipt.v2", "job_id": job_id, "provider": "baseten", "project_id": config["project_id"], "provider_job_id": provider_job_id, "request_sha256": summary.digest(body)}
        store.create_same(receipt_key, summary.canonical(receipt))
    try:
        provider_job = client.get(config["project_id"], provider_job_id)
    except baseten.ProviderError as error:
        raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
    status = provider_job.get("current_status")
    if status == "TRAINING_JOB_COMPLETED":
        try:
            return _completed(store, settings, runtime, client, config, manifest, job_id, provider_job, prefix)
        except baseten.ProviderError as error:
            raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
    if status in TERMINAL_FAILURE:
        raise ProviderError(f"Baseten training ended in {status}: {provider_job.get('error_message') or 'no detail'}", client.calls)
    return {"state": "active", "identity": job_id, "artifacts": _artifacts(store, [intent_key, receipt_key]), "provider_calls": client.calls, "next": "train", "details": {"provider": "baseten", "project_id": config["project_id"], "provider_job_id": provider_job_id, "status": status}}
