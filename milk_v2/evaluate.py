from __future__ import annotations

import json
import os
from pathlib import Path
import re
import uuid

from . import dataset, summary, train
from .providers import baseten


CODE_VERSION = "milk.evaluate.v2.5"
IMAGE = re.compile(r"ghcr\.io/milkinfrastructure/milk-man-eval@sha256:[0-9a-f]{64}\Z")
PROJECT = re.compile(r"[a-z0-9]{5,32}\Z")
TERMINAL_FAILURE = {"TRAINING_JOB_FAILED", "TRAINING_JOB_STOPPED", "TRAINING_JOB_CANCELED"}


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


def _policy() -> tuple[dict, str]:
    path = Path(__file__).resolve().parents[1] / "config" / "evaluation.json"
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluateError(f"cannot read evaluation policy: {error}") from error
    expected = {
        "schema_version": "milk.evaluation-policy.v3",
        "branches": ["bf16", "dynamic_fp8", "static_fp8"],
        "production_eligible_branches": ["bf16", "dynamic_fp8"],
        "dev_split": "dev",
        "sealed_split": "sealed",
        "score_order": [
            {"metric": "mean_score_bps", "direction": "desc"},
            {"metric": "errors", "direction": "asc"},
            {"metric": "p95_latency_ms", "direction": "asc"},
            {"metric": "tokens_per_second", "direction": "desc"},
        ],
        "tie_break": ["bf16", "dynamic_fp8", "static_fp8"],
        "static_calibration_split": "calibration",
        "torchao_version": "0.15.0",
    }
    if value != expected:
        raise EvaluateError("evaluation policy differs from the reviewed contract")
    return value, summary.digest(summary.canonical(value))


def _artifacts(store, keys: list[str]) -> list[dict]:
    return [{"key": key, "sha256": summary.digest(store.get(key).body)} for key in dict.fromkeys(keys)]


def _settings(settings, dataset_reference: dict, model_reference: dict, model: dict, policy_digest: str) -> dict:
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
    try:
        secret_map = json.loads(
            os.environ.get(
                "MILK_BASETEN_RUNTIME_SECRET_MAP_JSON",
                '{"MILK_STORE_ACCESS_KEY_ID":"milk-control-store-access-key-id","MILK_STORE_SECRET_ACCESS_KEY":"milk-control-store-secret-access-key"}',
            )
        )
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
        "accelerator": accelerator,
        "availability_model": "dedicated",
        "runtime_secret_map": secret_map,
        "max_new_tokens": _integer("MILK_EVALUATE_MAX_NEW_TOKENS", 256, 1, 2048),
        "dataset": {key: dataset_reference[key] for key in ("uuid", "key", "sha256", "counts")},
        "model": {key: model_reference[key] for key in ("uuid", "key", "sha256", "training_job_id")},
        "policy_digest": policy_digest,
    }


def _plan(settings, runtime, base: dict, branch: str, split: str) -> dict:
    config = {**base, "branch": branch, "split": split}
    identity = {
        "schema_version": "milk.evaluate-job-identity.v2",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "dataset": config["dataset"],
        "model": config["model"],
        "student_base": {
            "model_repo": runtime.student_base.model_repo,
            "model_revision": runtime.student_base.model_revision,
            "digest": runtime.student_base.digest,
        },
        "settings": {key: value for key, value in config.items() if key != "runtime_secret_map"},
        "runtime_secret_names": config["runtime_secret_map"],
        "config_digest": runtime.digest,
    }
    job_id = summary.digest(identity)
    return {"config": config, "identity": identity, "job_id": job_id, "prefix": settings.scope_prefix + f"j/evaluate/{job_id}/"}


def _job_body(settings, plan: dict) -> dict:
    config, job_id = plan["config"], plan["job_id"]
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
    return {
        "image": {"base_image": config["release_image"], "docker_auth": None},
        "compute": {
            "node_count": 1,
            "cpu_count": 4,
            "memory": "32Gi",
            "accelerator": {"accelerator": config["accelerator"], "count": 1},
            "availability_model": config["availability_model"],
        },
        "runtime": {
            "start_commands": [
                "python /opt/milk/evaluate.py",
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


def _stored(store, plan: dict) -> dict | None:
    result_key = plan["prefix"] + "result.json"
    try:
        prior, unused = _object(store, result_key)
    except FileNotFoundError:
        return None
    reference = prior.get("evaluation")
    if (
        prior.get("schema_version") != "milk.evaluate-job-result.v2"
        or prior.get("job_id") != plan["job_id"]
        or not isinstance(reference, dict)
        or reference.get("branch") != plan["config"]["branch"]
        or reference.get("split") != plan["config"]["split"]
        or not isinstance(prior.get("artifact_keys"), list)
    ):
        raise EvaluateError("stored evaluation result is invalid")
    return {
        "state": "complete",
        "reference": reference,
        "artifacts": _artifacts(store, prior["artifact_keys"]),
        "details": {"branch": reference["branch"], "split": reference["split"], "provider_job_id": prior["provider_job_id"], "status": "TRAINING_JOB_COMPLETED"},
    }


def _completed(store, settings, runtime, client, plan: dict, provider_job: dict) -> dict:
    config, prefix, job_id = plan["config"], plan["prefix"], plan["job_id"]
    files = client.checkpoint_files(config["project_id"], provider_job["id"])
    result_file = next((item for item in files if item.get("relative_file_name", "").endswith("evaluation/milk-result.json")), None)
    if not result_file or not isinstance(result_file.get("url"), str):
        return {"state": "active", "reference": None, "artifacts": _artifacts(store, [prefix + "intent.json", prefix + "receipt.json"]), "details": {"branch": config["branch"], "split": config["split"], "provider_job_id": provider_job["id"], "status": "CHECKPOINT_SYNCING"}}
    output, output_body = baseten.fetch_json(result_file["url"], client.timeout)
    expected_base = {"model_repo": runtime.student_base.model_repo, "model_revision": runtime.student_base.model_revision}
    quantization = output.get("quantization")
    expected_count = config["dataset"]["counts"][config["split"]]
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
        or len(output["rows"]) != expected_count
        or not isinstance(output.get("metrics"), dict)
        or not isinstance(output.get("case_ids"), list)
        or len(output["case_ids"]) != expected_count
        or not isinstance(quantization, dict)
        or quantization.get("kind") != config["branch"]
    ):
        raise EvaluateError("Baseten evaluation output identity differs")
    if config["branch"] == "static_fp8" and len(quantization.get("calibration_case_ids", [])) != config["dataset"]["counts"]["calibration"]:
        raise EvaluateError("static FP8 did not bind the calibration split")
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
        "policy_digest": config["policy_digest"],
        "branch": config["branch"],
        "split": config["split"],
        "provider": {"name": "baseten", "project_id": config["project_id"], "job_id": provider_job["id"], "status": provider_job["current_status"]},
        "images": {"runtime": config["release_image"]},
        "output_sha256": summary.digest(output_body),
        "case_ids": output["case_ids"],
        "quantization": quantization,
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
        "split": config["split"],
        "evaluation_job_id": job_id,
    }
    result_key = prefix + "result.json"
    result = {"schema_version": "milk.evaluate-job-result.v2", "job_id": job_id, "state": "progressed", "evaluation": reference, "provider_job_id": provider_job["id"], "artifact_keys": [evaluation_key, result_key]}
    store.create_same(result_key, summary.canonical(result))
    return {"state": "complete", "reference": reference, "artifacts": _artifacts(store, result["artifact_keys"]), "details": {"branch": config["branch"], "split": config["split"], "metrics": output["metrics"], "provider_job_id": provider_job["id"], "status": provider_job["current_status"]}}


def _provider_run(store, settings, runtime, client, jobs: dict[str, dict], plan: dict) -> dict:
    config, prefix, job_id = plan["config"], plan["prefix"], plan["job_id"]
    intent_key, receipt_key = prefix + "intent.json", prefix + "receipt.json"
    body = _job_body(settings, plan)
    store.create_same(intent_key, summary.canonical({**plan["identity"], "job_id": job_id, "provider_request": body}))
    try:
        receipt, unused = _object(store, receipt_key)
        provider_job_id = receipt.get("provider_job_id")
        if receipt.get("schema_version") != "milk.evaluate-provider-receipt.v2" or receipt.get("job_id") != job_id or not isinstance(provider_job_id, str):
            raise EvaluateError("stored Baseten evaluation receipt is invalid")
    except FileNotFoundError:
        provider_job = jobs.get(body["name"])
        if provider_job is None:
            try:
                provider_job = client.create(config["project_id"], body)
            except baseten.ProviderError as error:
                raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
            jobs[body["name"]] = provider_job
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
            return _completed(store, settings, runtime, client, plan, provider_job)
        except baseten.ProviderError as error:
            raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
    if status in TERMINAL_FAILURE:
        raise ProviderError(f"Baseten evaluation ended in {status}: {provider_job.get('error_message') or 'no detail'}", client.calls)
    return {"state": "active", "reference": None, "artifacts": _artifacts(store, [intent_key, receipt_key]), "details": {"branch": config["branch"], "split": config["split"], "provider_job_id": provider_job_id, "status": status}}


def _load_evaluation(store, reference: dict) -> dict:
    value, body = _object(store, reference.get("key", ""))
    if (
        reference.get("schema_version") != "milk.evaluation-reference.v2"
        or reference.get("sha256") != summary.digest(body)
        or value.get("schema_version") != "milk.evaluation.v2"
        or value.get("evaluation_uuid") != reference.get("uuid")
        or value.get("branch") != reference.get("branch")
        or value.get("split") != reference.get("split")
    ):
        raise EvaluateError("evaluation reference identity differs")
    return value


def _winner(store, policy: dict, runs: list[dict], eligible_branches: list[str]) -> tuple[dict, list[dict]]:
    evaluations = [_load_evaluation(store, run["reference"]) for run in runs]
    if any(value["split"] != policy["dev_split"] for value in evaluations):
        raise EvaluateError("winner inputs must be DEV evaluations")
    case_ids = evaluations[0]["case_ids"]
    if any(value["case_ids"] != case_ids for value in evaluations[1:]):
        raise EvaluateError("evaluation branches did not use identical ordered DEV cases")

    def key(value: dict):
        metrics = value["metrics"]
        values = []
        for rule in policy["score_order"]:
            metric = metrics.get(rule["metric"])
            if not isinstance(metric, (int, float)) or isinstance(metric, bool):
                raise EvaluateError(f"evaluation metric {rule['metric']} is invalid")
            values.append(-metric if rule["direction"] == "desc" else metric)
        values.append(policy["tie_break"].index(value["branch"]))
        return tuple(values)

    eligible = [value for value in evaluations if value["branch"] in eligible_branches]
    if len(eligible) != len(eligible_branches):
        raise EvaluateError("eligible evaluation branches are incomplete")
    winner = min(eligible, key=key)
    score = [{"metric": rule["metric"], "direction": rule["direction"], "value": winner["metrics"][rule["metric"]]} for rule in policy["score_order"]]
    return {"branch": winner["branch"], "dev_evaluation_uuid": winner["evaluation_uuid"], "score": score}, evaluations


def _finalize(store, settings, base: dict, policy: dict, eligible_branches: list[str], winner: dict, dev_runs: list[dict], sealed_run: dict) -> dict:
    sealed = _load_evaluation(store, sealed_run["reference"])
    if sealed["branch"] != winner["branch"] or sealed["split"] != policy["sealed_split"]:
        raise EvaluateError("sealed evaluation does not belong to the selected winner")
    identity = {
        "schema_version": "milk.evaluation-group-identity.v2",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "dataset": base["dataset"],
        "model": base["model"],
        "policy_digest": base["policy_digest"],
        "eligible_branches": eligible_branches,
        "dev": [run["reference"] for run in dev_runs],
        "winner": winner,
        "sealed": sealed_run["reference"],
    }
    group_identity = summary.digest(identity)
    group_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:evaluation-group:" + group_identity))
    group_key = settings.scope_prefix + f"v/{group_uuid}/manifest.json"
    group = {**identity, "schema_version": "milk.evaluation-group.v2", "evaluation_group_uuid": group_uuid, "policy": policy}
    group_body = summary.canonical(group)
    store.create_same(group_key, group_body)
    reference = {"schema_version": "milk.evaluation-group-reference.v2", "scope_id": settings.scope_id, "uuid": group_uuid, "key": group_key, "sha256": summary.digest(group_body), "winner_branch": winner["branch"]}
    status_key = settings.scope_prefix + "status/current.json"
    status, unused = _object(store, status_key)
    if status.get("schema_version") != "milk.status.v2" or status.get("scope_id") != settings.scope_id:
        raise EvaluateError("current status identity differs")
    summary._advance(store, status_key, {**status, "evaluation": reference, "next_action": "select-route-provider"})
    result_key = settings.scope_prefix + f"j/evaluate-group/{group_identity}/result.json"
    result = {"schema_version": "milk.evaluate-group-result.v2", "evaluation": reference, "state": "progressed", "next": "select-route-provider", "artifact_keys": [group_key, status_key, result_key]}
    store.create_same(result_key, summary.canonical(result))
    return {"state": "progressed", "identity": group_identity, "artifacts": _artifacts(store, result["artifact_keys"]), "provider_calls": 0, "next": "select-route-provider", "details": {"evaluation_group_uuid": group_uuid, "winner": winner, "sealed_evaluation_uuid": sealed["evaluation_uuid"]}}


def current(store, settings, runtime) -> dict | None:
    try:
        status, unused = _object(store, settings.scope_prefix + "status/current.json")
        reference = status.get("evaluation")
        value, body = _object(store, reference.get("key", "") if isinstance(reference, dict) else "")
        model_reference = train.current(store, settings, runtime)
        unused_policy, policy_digest = _policy()
    except FileNotFoundError:
        return None
    if (
        not isinstance(reference, dict)
        or model_reference is None
        or reference.get("schema_version") != "milk.evaluation-group-reference.v2"
        or reference.get("scope_id") != settings.scope_id
        or reference.get("sha256") != summary.digest(body)
        or value.get("schema_version") != "milk.evaluation-group.v2"
        or value.get("evaluation_group_uuid") != reference.get("uuid")
        or value.get("model", {}).get("uuid") != model_reference.get("uuid")
        or value.get("policy_digest") != policy_digest
    ):
        return None
    return reference


def reconcile(store, settings, runtime) -> dict:
    dataset_reference = dataset.current(store, settings, runtime)
    model_reference = train.current(store, settings, runtime)
    if dataset_reference is None or model_reference is None:
        reason = "dataset_missing" if dataset_reference is None else "training_missing"
        return {"state": "idle", "identity": summary.digest({"scope_id": settings.scope_id, "reason": reason}), "artifacts": [], "provider_calls": 0, "next": "dataset" if dataset_reference is None else "train", "details": {"reason": reason}}
    model, model_body = _object(store, model_reference["key"])
    if summary.digest(model_body) != model_reference["sha256"]:
        raise EvaluateError("model manifest digest differs")
    policy, policy_digest = _policy()
    base = _settings(settings, dataset_reference, model_reference, model, policy_digest)
    if any(base["dataset"]["counts"].get(split, 0) < 1 for split in ("dev", "calibration", "sealed")):
        return {"state": "idle", "identity": summary.digest({"dataset": base["dataset"], "reason": "evaluation_split_missing"}), "artifacts": [], "provider_calls": 0, "next": "dataset", "details": {"reason": "evaluation_split_missing"}}

    eligible_branches = policy["production_eligible_branches"] if settings.profile == "production" else policy["branches"]
    dev_plans = [_plan(settings, runtime, base, branch, policy["dev_split"]) for branch in eligible_branches]
    dev_runs = [_stored(store, plan) for plan in dev_plans]
    client = None
    provider_jobs = None
    if any(run is None for run in dev_runs):
        client = baseten.Client(_required("BASETEN_API_KEY"), _integer("MILK_EVALUATE_TIMEOUT_SECONDS", 30, 1, 120))
        try:
            listed = client.jobs(base["project_id"])
        except baseten.ProviderError as error:
            raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
        names = [job["name"] for job in listed if isinstance(job.get("name"), str)]
        if len(names) != len(set(names)):
            raise ProviderError("multiple Baseten jobs share a deterministic name", client.calls, ambiguous=True)
        provider_jobs = {job["name"]: job for job in listed if isinstance(job.get("name"), str)}
        dev_runs = [run or _provider_run(store, settings, runtime, client, provider_jobs, plan) for run, plan in zip(dev_runs, dev_plans)]
    artifacts = [artifact for run in dev_runs for artifact in run["artifacts"]]
    if any(run["state"] != "complete" for run in dev_runs):
        return {"state": "active", "identity": summary.digest({"plans": [plan["job_id"] for plan in dev_plans]}), "artifacts": artifacts, "provider_calls": client.calls if client else 0, "next": "evaluate", "details": {"branches": {plan["config"]["branch"]: run["details"] for plan, run in zip(dev_plans, dev_runs)}}}

    winner, _ = _winner(store, policy, dev_runs, eligible_branches)
    sealed_plan = _plan(settings, runtime, base, winner["branch"], policy["sealed_split"])
    sealed_run = _stored(store, sealed_plan)
    if sealed_run is None:
        if client is None:
            client = baseten.Client(_required("BASETEN_API_KEY"), _integer("MILK_EVALUATE_TIMEOUT_SECONDS", 30, 1, 120))
            try:
                listed = client.jobs(base["project_id"])
            except baseten.ProviderError as error:
                raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
            names = [job["name"] for job in listed if isinstance(job.get("name"), str)]
            if len(names) != len(set(names)):
                raise ProviderError("multiple Baseten jobs share a deterministic name", client.calls, ambiguous=True)
            provider_jobs = {job["name"]: job for job in listed if isinstance(job.get("name"), str)}
        sealed_run = _provider_run(store, settings, runtime, client, provider_jobs or {}, sealed_plan)
    artifacts.extend(sealed_run["artifacts"])
    if sealed_run["state"] != "complete":
        return {"state": "active", "identity": sealed_plan["job_id"], "artifacts": artifacts, "provider_calls": client.calls if client else 0, "next": "evaluate", "details": {"winner": winner, "sealed": sealed_run["details"]}}
    result = _finalize(store, settings, base, policy, eligible_branches, winner, dev_runs, sealed_run)
    result["artifacts"] = artifacts + result["artifacts"]
    result["provider_calls"] = client.calls if client else 0
    return result
