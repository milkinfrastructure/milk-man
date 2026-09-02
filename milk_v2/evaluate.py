from __future__ import annotations

import json
import os
import re
import uuid

from . import dataset, summary, train
from .providers import baseten


CODE_VERSION = "milk.evaluate.v2.0"
IMAGE = re.compile(r"ghcr\.io/milkinfrastructure/milk-man-eval@sha256:[0-9a-f]{64}\Z")
PROJECT = re.compile(r"[a-z0-9]{5,32}\Z")
TERMINAL_FAILURE = {"TRAINING_JOB_FAILED", "TRAINING_JOB_STOPPED", "TRAINING_JOB_CANCELED"}
BASETEN_BASE_IMAGE = train.BASETEN_BASE_IMAGE
TRANSFORMERS_SOURCE = train.TRANSFORMERS_SOURCE
EVALUATE_SOURCE_URL = "https://raw.githubusercontent.com/milkinfrastructure/milk-man/625ef95048cf1a106fef86b8024e6634abbdd0a3/images/eval/evaluate.py"
EVALUATE_SOURCE_SHA256 = "fc4bef3f9c4137b3c23647658d418b93d4b5a815c4910fa8beed240f04c00d90"


class EvaluateError(ValueError):
    pass


class ProviderError(RuntimeError):
    def __init__(self, message: str, provider_calls: int, *, ambiguous: bool = False):
        super().__init__(message)
        self.provider_calls = provider_calls
        self.ambiguous = ambiguous


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise EvaluateError(f"{name} is required")
    return value


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise EvaluateError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise EvaluateError(f"{name} must be in {minimum}..{maximum}")
    return value


def _object(store, key: str) -> tuple[dict, bytes]:
    body = store.get(key).body
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluateError(f"{key} is invalid JSON") from error
    if not isinstance(value, dict):
        raise EvaluateError(f"{key} must contain an object")
    return value, body


def _artifacts(store, keys: list[str]) -> list[dict]:
    return [{"key": key, "sha256": summary.digest(store.get(key).body)} for key in keys]


def _settings(settings, dataset_reference: dict, model_reference: dict, model: dict) -> dict:
    if settings.kind != "s3":
        raise EvaluateError("remote evaluation requires an S3-compatible dataset store")
    image = _required("MILK_EVAL_IMAGE")
    if IMAGE.fullmatch(image) is None:
        raise EvaluateError("MILK_EVAL_IMAGE must pin the reviewed GHCR image by sha256 digest")
    project_id = _required("BASETEN_TRAINING_PROJECT_ID")
    if PROJECT.fullmatch(project_id) is None:
        raise EvaluateError("BASETEN_TRAINING_PROJECT_ID is invalid")
    provider = model.get("provider")
    if (
        not isinstance(provider, dict)
        or provider.get("name") != "baseten"
        or provider.get("project_id") != project_id
        or not isinstance(provider.get("job_id"), str)
    ):
        raise EvaluateError("model has no usable Baseten checkpoint")
    secret_map_raw = os.environ.get(
        "MILK_BASETEN_RUNTIME_SECRET_MAP_JSON",
        '{"MILK_STORE_ACCESS_KEY_ID":"milk-control-store-access-key-id","MILK_STORE_SECRET_ACCESS_KEY":"milk-control-store-secret-access-key"}',
    )
    try:
        secret_map = json.loads(secret_map_raw)
    except json.JSONDecodeError as error:
        raise EvaluateError("MILK_BASETEN_RUNTIME_SECRET_MAP_JSON is invalid JSON") from error
    required_secrets = {"MILK_STORE_ACCESS_KEY_ID", "MILK_STORE_SECRET_ACCESS_KEY"}
    if not isinstance(secret_map, dict) or set(secret_map) != required_secrets or any(not isinstance(value, str) or not value for value in secret_map.values()):
        raise EvaluateError("MILK_BASETEN_RUNTIME_SECRET_MAP_JSON must map the two reviewed store credentials")
    accelerator = os.environ.get("BASETEN_TRAINING_ACCELERATOR", "H100")
    if accelerator not in {"H100", "H200"}:
        raise EvaluateError("BASETEN_TRAINING_ACCELERATOR must be H100 or H200")
    return {
        "provider": "baseten",
        "project_id": project_id,
        "source_job_id": provider["job_id"],
        "release_image": image,
        "baseten_base_image": BASETEN_BASE_IMAGE,
        "evaluate_source_url": EVALUATE_SOURCE_URL,
        "evaluate_source_sha256": EVALUATE_SOURCE_SHA256,
        "accelerator": accelerator,
        "availability_model": "dedicated",
        "runtime_secret_map": secret_map,
        "branch": "bf16",
        "split": "dev",
        "max_new_tokens": _integer("MILK_EVALUATE_MAX_NEW_TOKENS", 256, 1, 2048),
        "dataset": {key: dataset_reference[key] for key in ("uuid", "key", "sha256", "counts")},
        "model": {key: model_reference[key] for key in ("uuid", "key", "sha256", "training_job_id")},
    }


def _job_body(settings, config: dict, job_id: str) -> dict:
    environment = {
        "MILK_SCOPE_ID": settings.scope_id,
        "MILK_STORE_ENDPOINT": settings.endpoint,
        "MILK_STORE_REGION": settings.region,
        "MILK_STORE_BUCKET": settings.bucket,
        "MILK_DATASET_MANIFEST_KEY": config["dataset"]["key"],
        "MILK_DATASET_MANIFEST_SHA256": config["dataset"]["sha256"],
        "MILK_MODEL_UUID": config["model"]["uuid"],
        "MILK_EVALUATE_JOB_ID": job_id,
        "MILK_EVALUATE_BRANCH": config["branch"],
        "MILK_EVALUATE_SPLIT": config["split"],
        "MILK_EVALUATE_MAX_NEW_TOKENS": str(config["max_new_tokens"]),
    }
    environment.update({name: {"name": secret} for name, secret in config["runtime_secret_map"].items()})
    fetch_source = (
        "python -c \"import hashlib,urllib.request;"
        f"u='{config['evaluate_source_url']}';b=urllib.request.urlopen(u,timeout=30).read();"
        f"assert hashlib.sha256(b).hexdigest()=='{config['evaluate_source_sha256']}';"
        "open('/tmp/milk-evaluate.py','wb').write(b)\""
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
                "python /tmp/milk-evaluate.py",
            ],
            "environment_variables": environment,
            "cache_config": {"enabled": True, "require_cache_affinity": False},
            "checkpointing_config": {"enabled": True, "checkpoint_path": "/mnt/ckpts", "volume_size_gib": 10},
            "load_checkpoint_config": {
                "enabled": True,
                "download_folder": "/app/checkpoint",
                "checkpoints": [{"typ": "baseten_latest_checkpoint", "job_id": config["source_job_id"]}],
            },
        },
        "name": "milk-eval-" + job_id[:20],
        "weights": [],
        "enable_baseten_workdir": False,
        "priority": 0,
    }


def _advance_status(store, settings, reference: dict) -> str:
    key = settings.scope_prefix + "status/current.json"
    value, unused = _object(store, key)
    if value.get("schema_version") != "milk.status.v2" or value.get("scope_id") != settings.scope_id:
        raise EvaluateError("current status identity differs")
    summary._advance(store, key, {**value, "evaluation": reference, "next_action": "evaluate"})
    return key


def _completed(store, settings, runtime, client, config: dict, job_id: str, provider_job: dict, prefix: str) -> dict:
    files = client.checkpoint_files(config["project_id"], provider_job["id"])
    result_file = next((item for item in files if item.get("relative_file_name", "").endswith("evaluation/milk-result.json")), None)
    if not result_file or not isinstance(result_file.get("url"), str):
        return {
            "state": "active",
            "identity": job_id,
            "artifacts": _artifacts(store, [prefix + "intent.json", prefix + "receipt.json"]),
            "provider_calls": client.calls,
            "next": "evaluate",
            "details": {"provider_job_id": provider_job["id"], "status": "CHECKPOINT_SYNCING", "visible_checkpoint_files": len(files)},
        }
    output, output_body = baseten.fetch_json(result_file["url"], client.timeout)
    expected_base = {"model_repo": runtime.student_base.model_repo, "model_revision": runtime.student_base.model_revision}
    if (
        output.get("schema_version") != "milk.evaluation-output.v2"
        or output.get("job_id") != job_id
        or output.get("scope_id") != settings.scope_id
        or output.get("dataset_uuid") != config["dataset"]["uuid"]
        or output.get("model_uuid") != config["model"]["uuid"]
        or output.get("student_base") != expected_base
        or output.get("branch") != config["branch"]
        or output.get("split") != config["split"]
        or not isinstance(output.get("rows"), list)
        or len(output["rows"]) != config["dataset"]["counts"]["dev"]
        or not isinstance(output.get("metrics"), dict)
    ):
        raise EvaluateError("Baseten evaluation output identity differs")
    evaluation_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:evaluation:" + summary.digest({"job_id": job_id, "output": output})))
    evaluation_key = settings.scope_prefix + f"v/{evaluation_uuid}/{config['branch']}.json"
    evaluation = {
        "schema_version": "milk.evaluation.v2",
        "evaluation_uuid": evaluation_uuid,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "job_id": job_id,
        "dataset": config["dataset"],
        "model": config["model"],
        "branch": config["branch"],
        "split": config["split"],
        "provider": {"name": "baseten", "project_id": config["project_id"], "job_id": provider_job["id"], "status": provider_job["current_status"]},
        "images": {"release": config["release_image"], "provider_base": config["baseten_base_image"]},
        "output_sha256": summary.digest(output_body),
        "case_ids": output["case_ids"],
        "metrics": output["metrics"],
        "rows": output["rows"],
    }
    evaluation_body = summary.canonical(evaluation)
    store.create_same(evaluation_key, evaluation_body)
    reference = {
        "schema_version": "milk.evaluation-reference.v2",
        "scope_id": settings.scope_id,
        "uuid": evaluation_uuid,
        "key": evaluation_key,
        "sha256": summary.digest(evaluation_body),
        "branch": config["branch"],
        "evaluation_job_id": job_id,
    }
    status_key = _advance_status(store, settings, reference)
    result_key = prefix + "result.json"
    result = {
        "schema_version": "milk.evaluate-job-result.v2",
        "job_id": job_id,
        "state": "progressed",
        "next": "evaluate",
        "evaluation": reference,
        "provider_job_id": provider_job["id"],
        "artifact_keys": [evaluation_key, status_key, result_key],
    }
    store.create_same(result_key, summary.canonical(result))
    return {
        "state": "progressed",
        "identity": job_id,
        "artifacts": _artifacts(store, result["artifact_keys"]),
        "provider_calls": client.calls,
        "next": "evaluate",
        "details": {"evaluation_uuid": evaluation_uuid, "branch": config["branch"], "metrics": output["metrics"], "provider_job_id": provider_job["id"], "status": provider_job["current_status"]},
    }


def reconcile(store, settings, runtime) -> dict:
    dataset_reference = dataset.current(store, settings, runtime)
    model_reference = train.current(store, settings, runtime)
    if dataset_reference is None or model_reference is None:
        reason = "dataset_missing" if dataset_reference is None else "training_missing"
        return {"state": "idle", "identity": summary.digest({"scope_id": settings.scope_id, "reason": reason}), "artifacts": [], "provider_calls": 0, "next": "dataset" if dataset_reference is None else "train", "details": {"reason": reason}}
    model, model_body = _object(store, model_reference["key"])
    if summary.digest(model_body) != model_reference["sha256"]:
        raise EvaluateError("model manifest digest differs")
    config = _settings(settings, dataset_reference, model_reference, model)
    if config["dataset"]["counts"]["dev"] < 1:
        return {"state": "idle", "identity": summary.digest({"dataset": config["dataset"], "reason": "dev_missing"}), "artifacts": [], "provider_calls": 0, "next": "dataset", "details": {"reason": "dev_missing"}}
    identity = {
        "schema_version": "milk.evaluate-job-identity.v2",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "dataset": config["dataset"],
        "model": config["model"],
        "student_base": {"model_repo": runtime.student_base.model_repo, "model_revision": runtime.student_base.model_revision, "digest": runtime.student_base.digest},
        "settings": {key: value for key, value in config.items() if key != "runtime_secret_map"},
        "runtime_secret_names": config["runtime_secret_map"],
        "config_digest": runtime.digest,
    }
    job_id = summary.digest(identity)
    prefix = settings.scope_prefix + f"j/evaluate/{job_id}/"
    intent_key, receipt_key, result_key = (prefix + name for name in ("intent.json", "receipt.json", "result.json"))
    try:
        prior, unused = _object(store, result_key)
        reference = prior.get("evaluation")
        if prior.get("schema_version") != "milk.evaluate-job-result.v2" or prior.get("job_id") != job_id or not isinstance(reference, dict):
            raise EvaluateError("stored evaluation result is invalid")
        status_key = _advance_status(store, settings, reference)
        return {"state": "idle", "identity": job_id, "artifacts": _artifacts(store, [*prior["artifact_keys"], status_key]), "provider_calls": 0, "next": "evaluate", "details": {"evaluation_uuid": reference["uuid"], "branch": reference["branch"], "provider_job_id": prior["provider_job_id"], "status": "TRAINING_JOB_COMPLETED"}}
    except FileNotFoundError:
        pass

    client = baseten.Client(_required("BASETEN_API_KEY"), _integer("MILK_EVALUATE_TIMEOUT_SECONDS", 30, 1, 120))
    body = _job_body(settings, config, job_id)
    store.create_same(intent_key, summary.canonical({**identity, "job_id": job_id, "provider_request": body}))
    try:
        receipt, unused = _object(store, receipt_key)
        provider_job_id = receipt.get("provider_job_id")
        if receipt.get("schema_version") != "milk.evaluate-provider-receipt.v2" or receipt.get("job_id") != job_id or not isinstance(provider_job_id, str):
            raise EvaluateError("stored Baseten evaluation receipt is invalid")
    except FileNotFoundError:
        try:
            matches = [job for job in client.jobs(config["project_id"]) if job.get("name") == body["name"]]
        except baseten.ProviderError as error:
            raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
        if len(matches) > 1:
            raise ProviderError("multiple Baseten jobs match the deterministic evaluation name", client.calls, ambiguous=True)
        if matches:
            provider_job = matches[0]
        else:
            try:
                provider_job = client.create(config["project_id"], body)
            except baseten.ProviderError as error:
                raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
        provider_job_id = provider_job["id"]
        receipt = {"schema_version": "milk.evaluate-provider-receipt.v2", "job_id": job_id, "provider": "baseten", "project_id": config["project_id"], "provider_job_id": provider_job_id, "request_sha256": summary.digest(body)}
        store.create_same(receipt_key, summary.canonical(receipt))
    try:
        provider_job = client.get(config["project_id"], provider_job_id)
    except baseten.ProviderError as error:
        raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
    status = provider_job.get("current_status")
    if status == "TRAINING_JOB_COMPLETED":
        try:
            return _completed(store, settings, runtime, client, config, job_id, provider_job, prefix)
        except baseten.ProviderError as error:
            raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
    if status in TERMINAL_FAILURE:
        raise ProviderError(f"Baseten evaluation ended in {status}: {provider_job.get('error_message') or 'no detail'}", client.calls)
    return {"state": "active", "identity": job_id, "artifacts": _artifacts(store, [intent_key, receipt_key]), "provider_calls": client.calls, "next": "evaluate", "details": {"provider": "baseten", "project_id": config["project_id"], "provider_job_id": provider_job_id, "status": status}}
