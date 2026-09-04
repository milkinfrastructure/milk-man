from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

from . import dataset, summary, train
from .providers import baseten


CODE_VERSION = "milk.evaluate.v3"
IMAGE = re.compile(r"ghcr\.io/milkinfrastructure/milk-man-eval@sha256:[0-9a-f]{64}\Z")
PROJECT = re.compile(r"[a-z0-9]{5,32}\Z")
INFERENCE_BATCH_CASES = 64
RESULT_SHARD_CASES = 256
SCHEMA_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})
SCHEMA_MAX_DEPTH = 16
TERMINAL_FAILURE = {"TRAINING_JOB_FAILED", "TRAINING_JOB_STOPPED", "TRAINING_JOB_CANCELED"}
BASETEN_BASE_IMAGE = train.BASETEN_BASE_IMAGE
TRANSFORMERS_SOURCE = train.TRANSFORMERS_SOURCE
EVALUATE_SOURCE_URL = "https://raw.githubusercontent.com/milkinfrastructure/milk-man/9d1762bf1ab3861253f06f6d3dd72f068c9de778/images/eval/evaluate.py"
EVALUATE_SOURCE_SHA256 = "602199a5d37c1275af52f1a955fc1f91f2173a6914ad7ce6da5f6b8562c69330"


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


def _hex_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _case_id(eval_uuid: str, order: int) -> str:
    return summary.digest(f"{eval_uuid}\0{order}".encode())


def _case_ids_sha256(eval_uuid: str, start: int, end: int) -> str:
    value = hashlib.sha256()
    for order in range(start, end):
        value.update(bytes.fromhex(_case_id(eval_uuid, order)))
    return value.hexdigest()


def _normalized(value: str) -> list[str]:
    return "".join(character.lower() if character.isalnum() else " " for character in value).split()


def _similarity(reference: str, candidate: str) -> float:
    left, right = _normalized(reference), _normalized(candidate)
    if len(left) * len(right) > 4_000_000:
        raise EvaluateError("reference comparison exceeds its work bound")
    prior = list(range(len(right) + 1))
    for row_index, left_token in enumerate(left, 1):
        current = [row_index]
        for column_index, right_token in enumerate(right, 1):
            current.append(min(current[-1] + 1, prior[column_index] + 1, prior[column_index - 1] + (left_token != right_token)))
        prior = current
    return max(0.0, 1.0 - prior[-1] / max(len(left), len(right), 1))


def _schema_type_matches(expected: str, value: object) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and math.isfinite(value)),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }[expected]


def _schema_oracle_valid(schema: object, depth: int = 0) -> bool:
    if depth > SCHEMA_MAX_DEPTH:
        return False
    expected = schema.get("type") if isinstance(schema, dict) else None
    if not isinstance(expected, str) or expected not in SCHEMA_TYPES:
        return False
    allowed = {"type", "enum"}
    if expected == "object":
        allowed.update({"properties", "required", "additionalProperties"})
    elif expected == "array":
        allowed.add("items")
    if set(schema) - allowed:
        return False
    options = schema.get("enum")
    if options is not None:
        if expected in {"object", "array"} or not isinstance(options, list) or not options or any(not _schema_type_matches(expected, value) for value in options):
            return False
        encoded = [json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) for value in options]
        if len(set(encoded)) != len(encoded):
            return False
    if expected == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional = schema.get("additionalProperties", True)
        return (
            isinstance(properties, dict)
            and all(isinstance(key, str) and _schema_oracle_valid(value, depth + 1) for key, value in properties.items())
            and isinstance(required, list)
            and all(isinstance(key, str) for key in required)
            and len(set(required)) == len(required)
            and all(key in properties for key in required)
            and isinstance(additional, bool)
        )
    return expected != "array" or "items" not in schema or _schema_oracle_valid(schema["items"], depth + 1)


def _schema_match(schema: object, value: object) -> bool:
    if not _schema_oracle_valid(schema) or not _schema_type_matches(schema["type"], value):
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required_fields, list) or any(field not in value for field in required_fields):
            return False
        if schema.get("additionalProperties") is False and any(key not in properties for key in value):
            return False
        return all(key not in value or _schema_match(child, value[key]) for key, child in properties.items())
    if isinstance(value, list) and "items" in schema:
        return all(_schema_match(schema["items"], item) for item in value)
    return True


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _finite_json_float(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    return value


def _invalid_json_constant(value: str):
    raise ValueError(f"invalid JSON constant: {value}")


def _strict_json(value: str):
    return json.loads(value, object_pairs_hook=_unique_json_object, parse_float=_finite_json_float, parse_constant=_invalid_json_constant)


def _score(row: dict, candidate: str) -> int:
    expected = row.get("expected")
    if row["oracle"] == "exact":
        return 10_000 if isinstance(expected, str) and candidate.strip() == expected.strip() else 0
    if row["oracle"] == "reference":
        return int(_similarity(expected, candidate) * 10_000) if isinstance(expected, str) else 0
    try:
        value = _strict_json(candidate)
    except (UnicodeDecodeError, ValueError):
        return 0
    return 10_000 if _schema_match(expected, value) else 0


def _split_start(counts: dict, split: str) -> int:
    names = ("dev", "calibration", "sealed")
    return sum(counts[name] for name in names[:names.index(split)])


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
        "baseten_base_image": BASETEN_BASE_IMAGE,
        "evaluate_source_url": EVALUATE_SOURCE_URL,
        "evaluate_source_sha256": EVALUATE_SOURCE_SHA256,
        "accelerator": accelerator,
        "availability_model": "dedicated",
        "runtime_secret_map": secret_map,
        "max_new_tokens": _integer("MILK_EVALUATE_MAX_NEW_TOKENS", 256, 1, 2048),
        "dataset": {key: dataset_reference[key] for key in ("uuid", "key", "sha256", "counts")},
        "model": {key: model_reference[key] for key in ("uuid", "key", "sha256", "training_job_id")},
        "policy_digest": policy_digest,
    }


def _training_recipe(runtime, model: dict) -> str:
    recipe = model.get("training_recipe", "sft")
    if recipe not in {"sft", "reinforce"}:
        raise EvaluateError("model training recipe is invalid")
    if recipe == "reinforce":
        expected_parent = {
            "kind": "hf_base",
            "model_repo": runtime.student_base.model_repo,
            "model_revision": runtime.student_base.model_revision,
        }
        output = model.get("output")
        reinforce = output.get("reinforce") if isinstance(output, dict) else None
        if (
            model.get("parent") != expected_parent
            or not isinstance(output, dict)
            or output.get("recipe") != "reinforce"
            or output.get("parent") != expected_parent
            or not isinstance(reinforce, dict)
            or reinforce.get("updated") is not True
        ):
            raise EvaluateError("reinforce model has no verified policy update")
    return recipe


def _parent_base(runtime, base: dict) -> dict:
    source = {
        "kind": "hf_parent",
        "model_repo": runtime.student_base.model_repo,
        "model_revision": runtime.student_base.model_revision,
        "digest": runtime.student_base.digest,
    }
    parent_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:hf-parent:" + summary.digest(source)))
    return {
        **{key: value for key, value in base.items() if key != "source_job_id"},
        "model": {"uuid": parent_uuid, **source},
        "model_source": source,
    }


def _plan(settings, runtime, base: dict, branch: str, split: str) -> dict:
    config = {**base, "branch": branch, "split": split}
    identity = {
        "schema_version": "milk.evaluate-job-identity.v3",
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
    packages = f"boto3==1.40.40 {TRANSFORMERS_SOURCE} zstandard==0.25.0"
    setup = []
    if config["branch"] != "bf16":
        environment["CC"] = "/usr/bin/gcc"
        packages += " torchao==0.15.0"
        setup.append("apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*")
    environment.update({name: {"name": secret} for name, secret in config["runtime_secret_map"].items()})
    fetch_source = (
        "python -c \"import hashlib,urllib.request;"
        f"u='{config['evaluate_source_url']}';b=urllib.request.urlopen(u,timeout=30).read();"
        f"assert hashlib.sha256(b).hexdigest()=='{config['evaluate_source_sha256']}';"
        "open('/tmp/milk-evaluate.py','wb').write(b)\""
    )
    runtime = {
        "start_commands": [
            *setup,
            f"python -m pip install --no-cache-dir {packages}",
            fetch_source,
            "python /tmp/milk-evaluate.py",
        ],
        "environment_variables": environment,
        "cache_config": {"enabled": True, "require_cache_affinity": False},
        "checkpointing_config": {"enabled": True, "checkpoint_path": "/mnt/ckpts", "volume_size_gib": 10},
    }
    source = config.get("model_source")
    if source is None:
        runtime["load_checkpoint_config"] = {
            "enabled": True,
            "download_folder": "/app/checkpoint",
            "checkpoints": [{"typ": "baseten_latest_checkpoint", "job_id": config["source_job_id"]}],
        }
        weights = []
    else:
        if set(source) != {"kind", "model_repo", "model_revision", "digest"} or source.get("kind") != "hf_parent":
            raise EvaluateError("evaluation model source is invalid")
        weights = [{
            "source": f"hf://{source['model_repo']}@{source['model_revision']}",
            "mount_location": "/app/checkpoint/merged",
        }]
    return {
        "image": {"base_image": config["baseten_base_image"], "docker_auth": None},
        "compute": {
            "node_count": 1,
            "cpu_count": 4,
            "memory": "32Gi",
            "accelerator": {"accelerator": config["accelerator"], "count": 1},
            "availability_model": config["availability_model"],
        },
        "runtime": runtime,
        "name": "milk-eval-" + job_id[:20],
        "weights": weights,
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
        prior.get("schema_version") != "milk.evaluate-job-result.v3"
        or prior.get("job_id") != plan["job_id"]
        or not isinstance(reference, dict)
        or reference.get("evaluation_job_id") != plan["job_id"]
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


def _validate_quantization(value: object, config: dict, eval_uuid: str) -> dict:
    branch = config["branch"]
    if not isinstance(value, dict):
        raise EvaluateError("Baseten evaluation quantization identity differs")
    if branch == "bf16":
        if set(value) != {"kind", "quantized_linear_count"} or value.get("kind") != branch or value.get("quantized_linear_count") != 0:
            raise EvaluateError("Baseten evaluation quantization identity differs")
        return value
    fields = {"kind", "torchao_version", "quantized_linear_count"}
    if branch == "static_fp8":
        fields |= {"activation_scale", "calibration_case_count", "calibration_case_ids_sha256"}
    count = value.get("quantized_linear_count")
    if (
        set(value) != fields
        or value.get("kind") != branch
        or value.get("torchao_version") != "0.15.0"
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count < 1
    ):
        raise EvaluateError("Baseten evaluation quantization identity differs")
    if branch == "static_fp8":
        counts = config["dataset"]["counts"]
        calibration_count = counts["calibration"]
        calibration_start = _split_start(counts, "calibration")
        scale = value.get("activation_scale")
        if (
            value.get("calibration_case_count") != calibration_count
            or value.get("calibration_case_ids_sha256") != _case_ids_sha256(eval_uuid, calibration_start, calibration_start + calibration_count)
            or not isinstance(scale, (int, float))
            or isinstance(scale, bool)
            or not math.isfinite(scale)
            or scale <= 0
        ):
            raise EvaluateError("static FP8 did not bind the calibration split")
    return value


def _dataset_rows(store, settings, config: dict, manifest: dict):
    split = config["split"]
    counts = config["dataset"]["counts"]
    expected_count = counts[split]
    expected_start = _split_start(counts, split)
    expected_end = expected_start + expected_count
    objects = manifest.get("objects")
    source = objects.get(split) if isinstance(objects, dict) else None
    shards = source.get("shards") if isinstance(source, dict) else None
    if (
        not isinstance(source, dict)
        or set(source) != {"count", "root_sha256", "shards"}
        or source.get("count") != expected_count
        or not _hex_digest(source.get("root_sha256"))
        or not isinstance(shards, list)
        or not shards
        or summary.digest(shards) != source["root_sha256"]
    ):
        raise EvaluateError("evaluation dataset split manifest differs")

    expected_fields = {"split", "start", "end", "count", "key", "sha256", "content_sha256", "validation_key", "validation_sha256"}
    cursor = expected_start
    for shard in shards:
        if not isinstance(shard, dict) or set(shard) != expected_fields:
            raise EvaluateError("evaluation dataset shard descriptor differs")
        start, end, count = (shard.get(name) for name in ("start", "end", "count"))
        prefix = settings.scope_prefix + f"e/{manifest.get('eval_uuid', '')}/shards/{split}/{cursor:09d}-{end:09d}/" if type(end) is int else ""
        if (
            shard.get("split") != split
            or type(start) is not int
            or type(end) is not int
            or type(count) is not int
            or start != cursor
            or not start < end <= expected_end
            or count != end - start
            or count > RESULT_SHARD_CASES
            or shard.get("key") != prefix + "cases.jsonl.zst"
            or shard.get("validation_key") != prefix + "validation.json"
            or any(not _hex_digest(shard.get(name)) for name in ("sha256", "content_sha256", "validation_sha256"))
        ):
            raise EvaluateError("evaluation dataset shard descriptor differs")
        try:
            body = store.get(shard["key"]).body
            plain = summary._zstd(body, True)
            validation, validation_body = _object(store, shard["validation_key"])
        except (FileNotFoundError, summary.SummaryError) as error:
            raise EvaluateError("evaluation dataset shard is unavailable") from error
        if summary.digest(body) != shard["sha256"] or summary.digest(plain) != shard["content_sha256"] or summary.digest(validation_body) != shard["validation_sha256"]:
            raise EvaluateError("evaluation dataset shard digest differs")
        try:
            rows = [json.loads(line) for line in plain.splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EvaluateError("evaluation dataset shard is invalid JSONL") from error
        if not rows or len(rows) != count or b"".join(summary.canonical(row) for row in rows) != plain:
            raise EvaluateError("evaluation dataset shard content differs")
        hashes = []
        case_ids = []
        for order, row in zip(range(start, end), rows):
            oracle = row.get("oracle") if isinstance(row, dict) else None
            expected = row.get("expected") if isinstance(row, dict) else None
            case_id = _case_id(manifest["eval_uuid"], order)
            if (
                not isinstance(row, dict)
                or row.get("schema_version") != "milk.eval-case.v2"
                or row.get("case_id") != case_id
                or row.get("order") != order
                or row.get("split") != split
                or oracle not in {"exact", "reference", "schema"}
                or not isinstance(row.get("input"), str)
                or not row["input"]
                or (oracle in {"exact", "reference"} and not isinstance(expected, str))
                or (oracle == "schema" and not _schema_oracle_valid(expected))
            ):
                raise EvaluateError("evaluation dataset row differs")
            case_ids.append(case_id)
            hashes.append({"case_id": case_id, "input_sha256": summary.digest(" ".join(re.findall(r"[a-z0-9]+", row["input"].lower())).encode())})
        verdicts = validation.get("verdicts")
        if (
            validation_body != summary.canonical(validation)
            or set(validation) != {"schema_version", "eval_uuid", "revision_sha256", "split", "start", "end", "accepted", "case_count", "cases_sha256", "cases_content_sha256", "normalized_hashes", "normalized_ledger_sha256", "verdicts"}
            or validation.get("schema_version") != "milk.eval-validation-shard.v3"
            or validation.get("eval_uuid") != manifest["eval_uuid"]
            or validation.get("revision_sha256") != manifest.get("eval_revision_sha256")
            or validation.get("split") != split
            or validation.get("start") != start
            or validation.get("end") != end
            or validation.get("accepted") is not True
            or validation.get("case_count") != count
            or validation.get("cases_sha256") != shard["sha256"]
            or validation.get("cases_content_sha256") != shard["content_sha256"]
            or validation.get("normalized_hashes") != hashes
            or not _hex_digest(validation.get("normalized_ledger_sha256"))
            or not isinstance(verdicts, list)
            or len(verdicts) != count
            or any(
                not isinstance(item, dict)
                or set(item) != {"case_id", "accepted", "reason", "guidance"}
                or not isinstance(item.get("guidance"), str)
                for item in verdicts
            )
            or [item.get("case_id") for item in verdicts if item.get("accepted") is True and item.get("reason") == "accepted"] != case_ids
        ):
            raise EvaluateError("evaluation dataset shard validation differs")
        yield from rows
        cursor = end
    if cursor != expected_end:
        raise EvaluateError("evaluation dataset split range differs")


def _validate_result_shards(store, settings, config: dict, output: dict, dataset_manifest: dict) -> list[str]:
    split = config["split"]
    expected_count = config["dataset"]["counts"][split]
    expected_start = _split_start(config["dataset"]["counts"], split)
    expected_end = expected_start + expected_count
    eval_uuid = dataset_manifest["eval_uuid"]
    case_rows = iter(_dataset_rows(store, settings, config, dataset_manifest))
    missing = object()
    shards = output.get("result_shards")
    if (
        type(output.get("result_shard_case_count")) is not int
        or output.get("result_shard_case_count") != RESULT_SHARD_CASES
        or not isinstance(shards, list)
        or len(shards) != (expected_count + RESULT_SHARD_CASES - 1) // RESULT_SHARD_CASES
        or type(output.get("result_shard_count")) is not int
        or output.get("result_shard_count") != len(shards)
        or output.get("result_shards_sha256") != summary.digest(shards)
    ):
        raise EvaluateError("Baseten evaluation result shard manifest differs")

    expected_fields = {"split", "start", "end", "count", "key", "sha256", "content_sha256"}
    prefix = settings.scope_prefix + f"j/evaluate/{output['job_id']}/results/{split}/"
    cursor = expected_start
    case_ids = hashlib.sha256()
    score_total = latency_total = output_tokens = 0
    latencies = []
    keys = []
    for shard in shards:
        if not isinstance(shard, dict) or set(shard) != expected_fields:
            raise EvaluateError("Baseten evaluation result shard descriptor differs")
        start, end, count = (shard.get(name) for name in ("start", "end", "count"))
        expected_shard_end = min(cursor + RESULT_SHARD_CASES, expected_end)
        expected_key = prefix + f"{cursor:09d}-{expected_shard_end:09d}/rows.jsonl.zst"
        if (
            shard.get("split") != split
            or type(start) is not int
            or type(end) is not int
            or type(count) is not int
            or start != cursor
            or end != expected_shard_end
            or count != end - start
            or shard.get("key") != expected_key
            or not _hex_digest(shard.get("sha256"))
            or not _hex_digest(shard.get("content_sha256"))
        ):
            raise EvaluateError("Baseten evaluation result shard descriptor differs")
        try:
            body = store.get(shard["key"]).body
            plain = summary._zstd(body, True)
        except (FileNotFoundError, summary.SummaryError) as error:
            raise EvaluateError("Baseten evaluation result shard is unavailable") from error
        if summary.digest(body) != shard["sha256"] or summary.digest(plain) != shard["content_sha256"]:
            raise EvaluateError("Baseten evaluation result shard digest differs")
        try:
            rows = [json.loads(line) for line in plain.splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EvaluateError("Baseten evaluation result shard is invalid JSONL") from error
        if not rows or len(rows) != count or b"".join(summary.canonical(row) for row in rows) != plain:
            raise EvaluateError("Baseten evaluation result shard content differs")
        for order, row in zip(range(start, end), rows):
            source = next(case_rows, missing)
            candidate = row.get("candidate") if isinstance(row, dict) else None
            if (
                not isinstance(row, dict)
                or set(row) != {"case_id", "order", "score_bps", "candidate", "response_sha256", "latency_ms", "output_tokens"}
                or source is missing
                or source["case_id"] != row.get("case_id")
                or source["order"] != order
                or row.get("case_id") != _case_id(eval_uuid, order)
                or row.get("order") != order
                or type(row.get("score_bps")) is not int
                or not 0 <= row["score_bps"] <= 10_000
                or not isinstance(candidate, str)
                or row.get("response_sha256") != summary.digest(candidate.encode())
                or row["score_bps"] != _score(source, candidate)
                or type(row.get("latency_ms")) is not int
                or row["latency_ms"] < 1
                or type(row.get("output_tokens")) is not int
                or not 0 <= row["output_tokens"] <= config["max_new_tokens"]
            ):
                raise EvaluateError("Baseten evaluation result row differs")
            case_ids.update(bytes.fromhex(row["case_id"]))
            score_total += row["score_bps"]
            latency_total += row["latency_ms"]
            output_tokens += row["output_tokens"]
            latencies.append(row["latency_ms"])
        keys.append(shard["key"])
        cursor = end
    metrics = output.get("metrics")
    metric_fields = {"mean_score_bps", "errors", "p95_latency_ms", "total_latency_ms", "output_tokens", "tokens_per_second"}
    latencies.sort()
    if (
        cursor != expected_end
        or next(case_rows, missing) is not missing
        or output.get("case_count") != expected_count
        or output.get("case_ids_sha256") != case_ids.hexdigest()
        or not isinstance(metrics, dict)
        or set(metrics) != metric_fields
        or any(type(metrics.get(name)) is not int for name in ("mean_score_bps", "errors", "p95_latency_ms", "total_latency_ms", "output_tokens"))
        or not isinstance(metrics.get("tokens_per_second"), (int, float))
        or isinstance(metrics.get("tokens_per_second"), bool)
        or not math.isfinite(metrics["tokens_per_second"])
        or metrics.get("mean_score_bps") != score_total // expected_count
        or metrics.get("errors") != 0
        or metrics.get("p95_latency_ms") != latencies[(expected_count * 95 + 99) // 100 - 1]
        or metrics.get("total_latency_ms") != latency_total
        or metrics.get("output_tokens") != output_tokens
        or metrics.get("tokens_per_second") != round(output_tokens * 1000 / latency_total, 3)
    ):
        raise EvaluateError("Baseten evaluation aggregate metrics differ")
    return keys


def _completed(store, settings, runtime, client, plan: dict, provider_job: dict) -> dict:
    config, prefix, job_id = plan["config"], plan["prefix"], plan["job_id"]
    files = client.checkpoint_files(config["project_id"], provider_job["id"])
    result_file = next((item for item in files if item.get("relative_file_name", "").endswith("evaluation/milk-result.json")), None)
    if not result_file or not isinstance(result_file.get("url"), str):
        return {"state": "active", "reference": None, "artifacts": _artifacts(store, [prefix + "intent.json", prefix + "receipt.json"]), "details": {"branch": config["branch"], "split": config["split"], "provider_job_id": provider_job["id"], "status": "CHECKPOINT_SYNCING"}}
    output, output_body = baseten.fetch_json(result_file["url"], client.timeout)
    expected_base = {"model_repo": runtime.student_base.model_repo, "model_revision": runtime.student_base.model_revision}
    expected_count = config["dataset"]["counts"][config["split"]]
    if (
        output_body != summary.canonical(output)
        or set(output) != {"schema_version", "job_id", "scope_id", "dataset_uuid", "model_uuid", "student_base", "branch", "split", "case_count", "case_ids_sha256", "inference_batch_case_count", "result_shard_case_count", "result_shard_count", "result_shards_sha256", "result_shards", "quantization", "metrics"}
        or output.get("schema_version") != "milk.evaluation-output.v3"
        or output.get("job_id") != job_id
        or output.get("scope_id") != settings.scope_id
        or output.get("dataset_uuid") != config["dataset"]["uuid"]
        or output.get("model_uuid") != config["model"]["uuid"]
        or output.get("student_base") != expected_base
        or output.get("branch") != config["branch"]
        or output.get("split") != config["split"]
        or type(output.get("case_count")) is not int
        or output.get("case_count") != expected_count
        or not _hex_digest(output.get("case_ids_sha256"))
        or type(output.get("inference_batch_case_count")) is not int
        or output.get("inference_batch_case_count") != INFERENCE_BATCH_CASES
        or not _hex_digest(output.get("result_shards_sha256"))
    ):
        raise EvaluateError("Baseten evaluation output identity differs")
    dataset_manifest, dataset_body = _object(store, config["dataset"]["key"])
    if (
        summary.digest(dataset_body) != config["dataset"]["sha256"]
        or dataset_manifest.get("schema_version") != "milk.dataset.v3"
        or dataset_manifest.get("dataset_uuid") != config["dataset"]["uuid"]
        or not isinstance(dataset_manifest.get("eval_uuid"), str)
    ):
        raise EvaluateError("evaluation dataset manifest identity differs")
    eval_uuid = dataset_manifest["eval_uuid"]
    quantization = _validate_quantization(output.get("quantization"), config, eval_uuid)
    result_keys = _validate_result_shards(store, settings, config, output, dataset_manifest)
    evaluation_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:evaluation:" + summary.digest({"job_id": job_id, "output": output})))
    evaluation_key = settings.scope_prefix + f"v/{evaluation_uuid}/{config['branch']}.json"
    evaluation = {
        "schema_version": "milk.evaluation.v3",
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
        "images": {"release": config["release_image"], "provider_base": config["baseten_base_image"]},
        "output_sha256": summary.digest(output_body),
        "case_count": output["case_count"],
        "case_ids_sha256": output["case_ids_sha256"],
        "inference_batch_case_count": output["inference_batch_case_count"],
        "result_shard_case_count": output["result_shard_case_count"],
        "result_shard_count": output["result_shard_count"],
        "result_shards_sha256": output["result_shards_sha256"],
        "result_shards": output["result_shards"],
        "quantization": quantization,
        "metrics": output["metrics"],
    }
    evaluation_body = summary.canonical(evaluation)
    store.create_same(evaluation_key, evaluation_body)
    reference = {
        "schema_version": "milk.evaluation-reference.v3",
        "scope_id": settings.scope_id,
        "uuid": evaluation_uuid,
        "key": evaluation_key,
        "sha256": summary.digest(evaluation_body),
        "branch": config["branch"],
        "split": config["split"],
        "evaluation_job_id": job_id,
    }
    result_key = prefix + "result.json"
    result = {"schema_version": "milk.evaluate-job-result.v3", "job_id": job_id, "state": "progressed", "evaluation": reference, "provider_job_id": provider_job["id"], "artifact_keys": [*result_keys, evaluation_key, result_key]}
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


def _run_plans(store, settings, runtime, plans: list[dict], client=None, jobs=None):
    runs = [_stored(store, plan) for plan in plans]
    if all(run is not None for run in runs):
        return runs, client, jobs
    if client is None:
        client = baseten.Client(_required("BASETEN_API_KEY"), _integer("MILK_EVALUATE_TIMEOUT_SECONDS", 30, 1, 120))
        try:
            listed = client.jobs(plans[0]["config"]["project_id"])
        except baseten.ProviderError as error:
            raise ProviderError(str(error), client.calls, ambiguous=error.ambiguous) from error
        names = [job["name"] for job in listed if isinstance(job.get("name"), str)]
        if len(names) != len(set(names)):
            raise ProviderError("multiple Baseten jobs share a deterministic name", client.calls, ambiguous=True)
        jobs = {job["name"]: job for job in listed if isinstance(job.get("name"), str)}
    if jobs is None:
        jobs = {}
    return [run or _provider_run(store, settings, runtime, client, jobs, plan) for run, plan in zip(runs, plans)], client, jobs


def _load_evaluation(store, reference: dict) -> dict:
    value, body = _object(store, reference.get("key", ""))
    if (
        reference.get("schema_version") != "milk.evaluation-reference.v3"
        or reference.get("sha256") != summary.digest(body)
        or value.get("schema_version") != "milk.evaluation.v3"
        or value.get("evaluation_uuid") != reference.get("uuid")
        or value.get("branch") != reference.get("branch")
        or value.get("split") != reference.get("split")
    ):
        raise EvaluateError("evaluation reference identity differs")
    return value


def _parent_comparison(store, settings, base: dict, parent_base: dict, parent_run: dict, child_run: dict) -> tuple[dict, list[dict]]:
    parent = _load_evaluation(store, parent_run["reference"])
    child = _load_evaluation(store, child_run["reference"])
    case_identity = (parent["case_count"], parent["case_ids_sha256"])
    if (
        parent.get("branch") != "bf16"
        or child.get("branch") != "bf16"
        or parent.get("split") != "dev"
        or child.get("split") != "dev"
        or parent.get("scope_id") != settings.scope_id
        or child.get("scope_id") != settings.scope_id
        or parent.get("profile") != settings.profile
        or child.get("profile") != settings.profile
        or parent.get("dataset") != base["dataset"]
        or child.get("dataset") != base["dataset"]
        or parent.get("policy_digest") != base["policy_digest"]
        or child.get("policy_digest") != base["policy_digest"]
        or parent.get("model") != parent_base["model"]
        or child.get("model") != base["model"]
        or parent.get("job_id") != parent_run["reference"].get("evaluation_job_id")
        or child.get("job_id") != child_run["reference"].get("evaluation_job_id")
        or (child["case_count"], child["case_ids_sha256"]) != case_identity
    ):
        raise EvaluateError("parent and reinforce evaluations are not comparable")
    parent_score = parent["metrics"]["mean_score_bps"]
    child_score = child["metrics"]["mean_score_bps"]
    promoted = child_score > parent_score
    identity = {
        "schema_version": "milk.parent-comparison-identity.v1",
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "dataset": base["dataset"],
        "parent": parent_run["reference"],
        "child": child_run["reference"],
    }
    comparison_id = summary.digest(identity)
    key = settings.scope_prefix + f"j/evaluate-parent/{comparison_id}/result.json"
    value = {
        **identity,
        "schema_version": "milk.parent-comparison.v1",
        "comparison_id": comparison_id,
        "case_count": case_identity[0],
        "case_ids_sha256": case_identity[1],
        "parent_mean_score_bps": parent_score,
        "child_mean_score_bps": child_score,
        "delta_mean_score_bps": child_score - parent_score,
        "selected": "child" if promoted else "parent",
        "child_promoted": promoted,
    }
    body = summary.canonical(value)
    store.create_same(key, body)
    reference = {
        "schema_version": "milk.parent-comparison-reference.v1",
        "comparison_id": comparison_id,
        "key": key,
        "sha256": summary.digest(body),
        "child_promoted": promoted,
        "parent_mean_score_bps": parent_score,
        "child_mean_score_bps": child_score,
        "delta_mean_score_bps": child_score - parent_score,
    }
    return reference, _artifacts(store, [key])


def _winner(store, policy: dict, runs: list[dict], eligible_branches: list[str]) -> tuple[dict, list[dict]]:
    evaluations = [_load_evaluation(store, run["reference"]) for run in runs]
    if any(value["split"] != policy["dev_split"] for value in evaluations):
        raise EvaluateError("winner inputs must be DEV evaluations")
    case_identity = (evaluations[0]["case_count"], evaluations[0]["case_ids_sha256"])
    if any((value["case_count"], value["case_ids_sha256"]) != case_identity for value in evaluations[1:]):
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


def _finalize(store, settings, base: dict, policy: dict, eligible_branches: list[str], winner: dict, dev_runs: list[dict], sealed_run: dict, parent_comparison: dict | None = None) -> dict:
    sealed = _load_evaluation(store, sealed_run["reference"])
    if sealed["branch"] != winner["branch"] or sealed["split"] != policy["sealed_split"]:
        raise EvaluateError("sealed evaluation does not belong to the selected winner")
    identity = {
        "schema_version": "milk.evaluation-group-identity.v3",
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
    if parent_comparison is not None:
        identity["parent_comparison"] = parent_comparison
    group_identity = summary.digest(identity)
    group_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:evaluation-group:" + group_identity))
    group_key = settings.scope_prefix + f"v/{group_uuid}/manifest.json"
    group = {**identity, "schema_version": "milk.evaluation-group.v3", "evaluation_group_uuid": group_uuid, "policy": policy}
    group_body = summary.canonical(group)
    store.create_same(group_key, group_body)
    reference = {"schema_version": "milk.evaluation-group-reference.v3", "scope_id": settings.scope_id, "uuid": group_uuid, "key": group_key, "sha256": summary.digest(group_body), "winner_branch": winner["branch"]}
    status_key = settings.scope_prefix + "status/current.json"
    status, unused = _object(store, status_key)
    if status.get("schema_version") != "milk.status.v2" or status.get("scope_id") != settings.scope_id:
        raise EvaluateError("current status identity differs")
    summary._advance(store, status_key, {**status, "evaluation": reference, "next_action": "select-route-provider"})
    result_key = settings.scope_prefix + f"j/evaluate-group/{group_identity}/result.json"
    artifact_keys = [group_key, status_key, result_key]
    if parent_comparison is not None:
        artifact_keys.insert(0, parent_comparison["key"])
    result = {"schema_version": "milk.evaluate-group-result.v3", "evaluation": reference, "state": "progressed", "next": "select-route-provider", "artifact_keys": artifact_keys}
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
        or reference.get("schema_version") != "milk.evaluation-group-reference.v3"
        or reference.get("scope_id") != settings.scope_id
        or reference.get("sha256") != summary.digest(body)
        or value.get("schema_version") != "milk.evaluation-group.v3"
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
    dataset_manifest, dataset_body = _object(store, dataset_reference["key"])
    if summary.digest(dataset_body) != dataset_reference["sha256"] or dataset_manifest.get("schema_version") != "milk.dataset.v3":
        raise EvaluateError("evaluation requires a verified milk.dataset.v3 manifest")
    model, model_body = _object(store, model_reference["key"])
    if summary.digest(model_body) != model_reference["sha256"]:
        raise EvaluateError("model manifest digest differs")
    recipe = _training_recipe(runtime, model)
    policy, policy_digest = _policy()
    base = _settings(settings, dataset_reference, model_reference, model, policy_digest)
    if any(base["dataset"]["counts"].get(split, 0) < 1 for split in ("dev", "calibration", "sealed")):
        return {"state": "idle", "identity": summary.digest({"dataset": base["dataset"], "reason": "evaluation_split_missing"}), "artifacts": [], "provider_calls": 0, "next": "dataset", "details": {"reason": "evaluation_split_missing"}}

    eligible_branches = policy["production_eligible_branches"] if settings.profile == "production" else policy["branches"]
    client = None
    provider_jobs = None
    artifacts = []
    parent_comparison = None
    if recipe == "reinforce":
        parent_base = _parent_base(runtime, base)
        comparison_plans = [
            _plan(settings, runtime, parent_base, "bf16", policy["dev_split"]),
            _plan(settings, runtime, base, "bf16", policy["dev_split"]),
        ]
        comparison_runs, client, provider_jobs = _run_plans(store, settings, runtime, comparison_plans)
        artifacts.extend(artifact for run in comparison_runs for artifact in run["artifacts"])
        if any(run["state"] != "complete" for run in comparison_runs):
            labels = ("parent_bf16", "child_bf16")
            return {
                "state": "active",
                "identity": summary.digest({"plans": [plan["job_id"] for plan in comparison_plans]}),
                "artifacts": artifacts,
                "provider_calls": client.calls if client else 0,
                "next": "evaluate",
                "details": {"branches": {label: run["details"] for label, run in zip(labels, comparison_runs)}},
            }
        parent_comparison, comparison_artifacts = _parent_comparison(store, settings, base, parent_base, *comparison_runs)
        artifacts.extend(comparison_artifacts)
        if not parent_comparison["child_promoted"]:
            status_key = settings.scope_prefix + "status/current.json"
            status, unused = _object(store, status_key)
            if status.get("schema_version") != "milk.status.v2" or status.get("scope_id") != settings.scope_id:
                raise EvaluateError("current status identity differs")
            summary._advance(store, status_key, {**status, "next_action": "train"})
            artifacts.extend(_artifacts(store, [status_key]))
            return {
                "state": "idle",
                "identity": parent_comparison["comparison_id"],
                "artifacts": artifacts,
                "provider_calls": client.calls if client else 0,
                "next": "train",
                "details": {"reason": "policy_not_improved", **parent_comparison},
            }

    dev_plans = [_plan(settings, runtime, base, branch, policy["dev_split"]) for branch in policy["branches"]]
    dev_runs, client, provider_jobs = _run_plans(store, settings, runtime, dev_plans, client, provider_jobs)
    artifacts.extend(artifact for run in dev_runs for artifact in run["artifacts"])
    if any(run["state"] != "complete" for run in dev_runs):
        return {"state": "active", "identity": summary.digest({"plans": [plan["job_id"] for plan in dev_plans]}), "artifacts": artifacts, "provider_calls": client.calls if client else 0, "next": "evaluate", "details": {"branches": {plan["config"]["branch"]: run["details"] for plan, run in zip(dev_plans, dev_runs)}}}

    winner, _ = _winner(store, policy, dev_runs, eligible_branches)
    sealed_plan = _plan(settings, runtime, base, winner["branch"], policy["sealed_split"])
    sealed_runs, client, provider_jobs = _run_plans(store, settings, runtime, [sealed_plan], client, provider_jobs)
    sealed_run = sealed_runs[0]
    artifacts.extend(sealed_run["artifacts"])
    if sealed_run["state"] != "complete":
        return {"state": "active", "identity": sealed_plan["job_id"], "artifacts": artifacts, "provider_calls": client.calls if client else 0, "next": "evaluate", "details": {"winner": winner, "sealed": sealed_run["details"]}}
    result = _finalize(store, settings, base, policy, eligible_branches, winner, dev_runs, sealed_run, parent_comparison)
    result["artifacts"] = artifacts + result["artifacts"]
    result["provider_calls"] = client.calls if client else 0
    return result
