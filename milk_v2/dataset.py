from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

from . import eval as eval_job
from . import eval_plan, semantic, summary


CODE_VERSION = "milk.dataset.v2"
SPLITS = ("train", "dev", "calibration", "sealed")


class DatasetError(ValueError):
    pass


class ProviderError(RuntimeError):
    def __init__(self, message: str, inference_calls: int = 0):
        super().__init__(message)
        self.inference_calls = inference_calls


class BusyError(RuntimeError):
    def __init__(self, identity: str):
        super().__init__("an incomplete dataset intent already exists")
        self.identity = identity


def training_ready(counts: object) -> bool:
    if (
        not isinstance(counts, dict)
        or set(counts) != set(SPLITS)
        or any(not isinstance(counts[split], int) or isinstance(counts[split], bool) or counts[split] < 0 for split in SPLITS)
    ):
        raise DatasetError("dataset split counts are invalid")
    return all(counts[split] > 0 for split in SPLITS)


def split_counts(manifest: dict) -> dict[str, int]:
    objects = manifest.get("objects")
    if not isinstance(objects, dict) or set(objects) != set(SPLITS):
        raise DatasetError("dataset split objects are invalid")
    counts = {}
    for split in SPLITS:
        item = objects[split]
        count = item.get("count") if isinstance(item, dict) else None
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise DatasetError("dataset split counts are invalid")
        counts[split] = count
    return counts


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise DatasetError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise DatasetError(f"{name} must be in {minimum}..{maximum}")
    return value


def _object(store, key: str) -> tuple[dict, bytes]:
    body = store.get(key).body
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetError(f"{key} is not valid JSON") from error
    if not isinstance(value, dict):
        raise DatasetError(f"{key} must contain an object")
    return value, body


def current(store, settings, runtime) -> dict | None:
    try:
        status, unused_status_body = _object(store, settings.scope_prefix + "status/current.json")
    except FileNotFoundError:
        return None
    reference = status.get("dataset")
    if not isinstance(reference, dict):
        return None
    try:
        eval_pointer, eval_pointer_body = _object(store, settings.scope_prefix + "e/current.json")
        manifest, manifest_body = _object(store, reference.get("key", ""))
    except FileNotFoundError:
        return None
    try:
        counts = split_counts(manifest)
    except DatasetError:
        return None
    if (
        reference.get("schema_version") != "milk.dataset-reference.v2"
        or reference.get("scope_id") != settings.scope_id
        or summary.digest(manifest_body) != reference.get("sha256")
        or summary.digest(eval_pointer_body) != reference.get("eval_pointer_sha256")
        or manifest.get("schema_version") != "milk.dataset.v2"
        or manifest.get("dataset_uuid") != reference.get("uuid")
        or manifest.get("scope_id") != settings.scope_id
        or manifest.get("profile") != settings.profile
        or manifest.get("eval_pointer_sha256") != reference.get("eval_pointer_sha256")
        or manifest.get("student_base") != {
            "model_repo": runtime.student_base.model_repo,
            "model_revision": runtime.student_base.model_revision,
            "digest": runtime.student_base.digest,
        }
        or eval_pointer.get("uuid") != manifest.get("eval_uuid")
        or reference.get("counts") != counts
    ):
        return None
    return reference


def _eval_context(store, settings) -> tuple[dict, str, list[dict], dict]:
    if not eval_job.current_matches(store, settings):
        raise DatasetError("the current eval is missing or stale")
    pointer, pointer_body = _object(store, settings.scope_prefix + "e/current.json")
    eval_body = store.get(pointer.get("key", "")).body
    if summary.digest(eval_body) != pointer.get("sha256"):
        raise DatasetError("current eval object digest differs")
    source_body = store.get(pointer.get("source_key", "")).body
    validation, validation_body = _object(store, pointer.get("validation_key", ""))
    if summary.digest(source_body) != pointer.get("source_sha256") or summary.digest(validation_body) != pointer.get("validation_sha256"):
        raise DatasetError("current eval provenance digest differs")
    try:
        source = json.loads(summary._zstd(source_body, True))
        cases = [json.loads(line) for line in summary._zstd(eval_body, True).splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetError("current eval content is invalid") from error
    if (
        not isinstance(source, dict)
        or source.get("schema_version") != "milk.eval-source.v2"
        or source.get("eval_uuid") != pointer.get("uuid")
        or validation.get("schema_version") != "milk.eval-validation.v2"
        or validation.get("eval_uuid") != pointer.get("uuid")
        or validation.get("accepted") is not True
        or validation.get("case_count") != len(cases)
        or validation.get("eval_content_sha256") != pointer.get("content_sha256")
        or validation.get("eval_object_sha256") != pointer.get("sha256")
        or len(cases) != pointer.get("case_count")
        or not isinstance(source.get("policy"), dict)
        or source["policy"].get("split_version") != eval_plan.SPLIT_VERSION
    ):
        raise DatasetError("current eval identity differs")
    seen_ids, seen_requests = set(), set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or case.get("schema_version") != "milk.eval-case.v2"
            or case.get("split") not in {"dev", "calibration", "sealed"}
            or not isinstance(case.get("case_id"), str)
            or case["case_id"] in seen_ids
            or not isinstance(case.get("source_request_sha256"), str)
            or case["source_request_sha256"] in seen_requests
        ):
            raise DatasetError("current eval contains an invalid or duplicate case")
        seen_ids.add(case["case_id"])
        seen_requests.add(case["source_request_sha256"])
    verdict_ids = [item.get("case_id") for item in validation.get("verdicts", []) if isinstance(item, dict) and item.get("accepted") is True]
    if verdict_ids != [case["case_id"] for case in cases]:
        raise DatasetError("current eval verdicts differ from its cases")
    return pointer, summary.digest(pointer_body), cases, source["policy"]


def _train_sources(store, settings, eval_pointer: dict, eval_requests: set[str], count: int, text_bytes: int) -> list[dict]:
    summary_pointer, unused_pointer_body, summary_value = summary._read_pointer(store, settings.scope_prefix)
    if summary_pointer is None or summary_pointer.get("sha256") != eval_pointer.get("summary_sha256"):
        raise DatasetError("current summary differs from the eval source")
    source_rows, unused_keys = summary._ancestry(store, settings, summary_value)
    distinct = {}
    for row in source_rows:
        request_sha256 = row.get("request_sha256")
        if (
            row.get("parse") is not True
            or row.get("success") is not True
            or row.get("modalities") != ["text"]
            or row.get("tool_definitions") != 0
            or row.get("tool_calls") != 0
            or not isinstance(request_sha256, str)
            or request_sha256 in eval_requests
        ):
            continue
        try:
            split = eval_plan.split_for(request_sha256)
        except eval_plan.PlanError:
            continue
        if split != "train":
            continue
        prior = distinct.get(request_sha256)
        if prior is None or row.get("content_sha256", "") < prior.get("content_sha256", ""):
            distinct[request_sha256] = row
    selected = sorted(distinct.values(), key=lambda row: summary.digest(("milk.dataset.train.v2:" + row["request_sha256"] + row["content_sha256"]).encode()))[:count]
    prepared = []
    for row in selected:
        parsed = summary.parse_capture(store, settings, row["key"])
        if parsed["object_sha256"] != row.get("object_sha256") or parsed["content_sha256"] != row.get("content_sha256") or parsed["request_sha256"] != row.get("request_sha256") or eval_plan.split_for(parsed["request_sha256"]) != "train" or parsed["request_sha256"] in eval_requests:
            raise DatasetError("selected train source identity differs")
        prepared.append({
            "source_request_sha256": parsed["request_sha256"],
            "source_response_sha256": parsed["response_sha256"],
            "source_content_sha256": parsed["content_sha256"],
            "source_object_sha256": parsed["object_sha256"],
            "source_key": parsed["key"],
            "input": parsed["request_text"].encode()[:text_bytes].decode("utf-8", "ignore"),
            "reference_response": parsed["response_text"].encode()[:text_bytes].decode("utf-8", "ignore"),
        })
    return prepared


def _target_schema(count: int) -> dict:
    item = {
        "type": "object",
        "properties": {"source_request_sha256": {"type": "string"}, "target": {"type": "string", "minLength": 1, "maxLength": 16384}},
        "required": ["source_request_sha256", "target"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"schema_version": {"type": "string", "enum": ["milk.teacher-targets.v2"]}, "targets": {"type": "array", "items": item, "minItems": count, "maxItems": count}},
        "required": ["schema_version", "targets"],
        "additionalProperties": False,
    }


def _target_contract(value: dict, sources: list[dict]) -> dict:
    if not isinstance(value, dict) or set(value) != {"schema_version", "targets"} or value.get("schema_version") != "milk.teacher-targets.v2" or not isinstance(value.get("targets"), list) or len(value["targets"]) != len(sources):
        raise ValueError("teacher returned an invalid target set")
    checked = []
    for source, target in zip(sources, value["targets"]):
        if not isinstance(target, dict) or set(target) != {"source_request_sha256", "target"} or target.get("source_request_sha256") != source["source_request_sha256"] or not isinstance(target.get("target"), str) or not 1 <= len(target["target"].encode()) <= 16384:
            raise ValueError("teacher changed source identity, order, or target bounds")
        checked.append(target)
    return {"schema_version": "milk.teacher-targets.v2", "targets": checked}


def _artifacts(store, keys: list[str]) -> list[dict]:
    return [{"key": key, "sha256": summary.digest(store.get(key).body)} for key in keys]


def _status(store, settings, reference: dict) -> str:
    key = settings.scope_prefix + "status/current.json"
    value, unused_body = _object(store, key)
    if value.get("schema_version") != "milk.status.v2" or value.get("scope_id") != settings.scope_id or value.get("profile") != settings.profile:
        raise DatasetError("current status identity differs")
    next_action = "train" if training_ready(reference.get("counts")) else "summary"
    summary._advance(store, key, {**value, "dataset": reference, "next_action": next_action})
    return key


def reconcile(store, settings, runtime) -> dict:
    existing = current(store, settings, runtime)
    if existing is not None:
        ready = training_ready(existing.get("counts"))
        status_key = _status(store, settings, existing)
        return {"state": "idle", "identity": existing["uuid"], "artifacts": _artifacts(store, [existing["key"], status_key]), "inference_calls": 0, "provider_calls": 0, "next": "train" if ready else "summary", "details": {"dataset_uuid": existing["uuid"], "counts": existing["counts"], "training_ready": ready}}

    eval_pointer, eval_pointer_sha256, eval_cases, split_policy = _eval_context(store, settings)
    requested = _integer("MILK_DATASET_TRAIN_EXAMPLES", 128 if settings.profile == "production" else 1, 1, 256)
    text_bytes = _integer("MILK_DATASET_TEXT_BYTES", 2048, 128, 4096)
    eval_requests = {case["source_request_sha256"] for case in eval_cases}
    sources = _train_sources(store, settings, eval_pointer, eval_requests, requested, text_bytes)
    if len(sources) < requested:
        identity = summary.digest({"schema_version": "milk.dataset-wait.v2", "eval_pointer_sha256": eval_pointer_sha256, "requested": requested, "available": len(sources)})
        return {"state": "idle", "identity": identity, "artifacts": [], "inference_calls": 0, "provider_calls": 0, "next": "dataset", "details": {"reason": "insufficient_train_sources", "requested": requested, "available": len(sources)}}

    binding = semantic.binding("TEACHER")
    prompt_path = Path(__file__).resolve().parents[1] / runtime.job("dataset").system_prompt
    prompt = prompt_path.read_text()
    student_base = {"model_repo": runtime.student_base.model_repo, "model_revision": runtime.student_base.model_revision, "digest": runtime.student_base.digest}
    settings_value = {"teacher": binding, "prompt_sha256": summary.digest(prompt.encode()), "temperature": 0, "train_examples_requested": requested, "train_examples_effective": len(sources), "source_text_bytes": text_bytes}
    identity = {
        "schema_version": "milk.dataset-job-identity.v2",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "eval_uuid": eval_pointer["uuid"],
        "eval_pointer_sha256": eval_pointer_sha256,
        "eval_object_sha256": eval_pointer["sha256"],
        "split_policy": split_policy,
        "excluded_eval_request_sha256": sorted(eval_requests),
        "train_sources": [{key: source[key] for key in ("source_key", "source_object_sha256", "source_request_sha256", "source_response_sha256", "source_content_sha256")} for source in sources],
        "student_base": student_base,
        "settings": settings_value,
        "config_digest": runtime.digest,
    }
    job_id = summary.digest(identity)
    prefix = settings.scope_prefix + f"j/dataset/{job_id}/"
    intent_key, receipt_key, result_key = (prefix + name for name in ("intent.json", "receipt.json", "result.json"))
    try:
        prior, unused_body = _object(store, result_key)
        if prior.get("schema_version") != "milk.dataset-job-result.v2" or prior.get("job_id") != job_id:
            raise DatasetError("stored dataset result is invalid")
        reference = prior.get("dataset")
        if not isinstance(reference, dict):
            raise DatasetError("stored dataset result has no dataset reference")
        status_key = _status(store, settings, reference)
        ready = training_ready(reference.get("counts"))
        details = {**prior["details"], "training_ready": ready}
        return {"state": prior["state"], "identity": job_id, "artifacts": _artifacts(store, [*prior.get("artifact_keys", []), status_key]), "inference_calls": 0, "provider_calls": 0, "next": "train" if ready else "summary", "details": details}
    except FileNotFoundError:
        pass
    if not store.create_same(intent_key, summary.canonical({**identity, "job_id": job_id})).created:
        raise BusyError(job_id)

    teacher_input = {"schema_version": "milk.teacher-input.v2", "sources": sources}
    try:
        targets, receipt = semantic.call("dataset", "TEACHER", prompt, teacher_input, _target_schema(len(sources)), lambda value: _target_contract(value, sources), "MILK_DATASET_TIMEOUT_SECONDS")
    except semantic.ProviderError as error:
        raise ProviderError(str(error), error.inference_calls) from error
    store.create_same(receipt_key, summary.canonical({"schema_version": "milk.dataset-teacher-receipt.v2", "job_id": job_id, "receipt": receipt}))
    train_rows = []
    for source, target in zip(sources, targets["targets"]):
        train_rows.append({
            "schema_version": "milk.training-example.v2",
            "example_id": summary.digest({"request": source["source_request_sha256"], "target": summary.digest(target["target"].encode()), "teacher": settings_value}),
            "split": "train",
            "input": source["input"],
            "target": target["target"],
            **{key: source[key] for key in ("source_key", "source_object_sha256", "source_request_sha256", "source_response_sha256", "source_content_sha256")},
        })
    rows = {"train": train_rows, **{split: [case for case in eval_cases if case["split"] == split] for split in SPLITS[1:]}}
    plain = {split: b"".join(summary.canonical(row) for row in rows[split]) for split in SPLITS}
    logical = {split: summary.digest(plain[split]) for split in SPLITS}
    dataset_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:dataset:" + summary.digest({"job_id": job_id, "content_sha256": logical})))
    dataset_prefix = settings.scope_prefix + f"d/{dataset_uuid}/"
    bodies = {split: summary._zstd(plain[split], False) for split in SPLITS}
    object_values = {
        split: {"key": dataset_prefix + f"{split}.jsonl.zst", "sha256": summary.digest(bodies[split]), "content_sha256": logical[split], "count": len(rows[split])}
        for split in SPLITS
    }
    manifest = {
        "schema_version": "milk.dataset.v2",
        "code_version": CODE_VERSION,
        "dataset_uuid": dataset_uuid,
        "job_id": job_id,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "eval_uuid": eval_pointer["uuid"],
        "eval_pointer_sha256": eval_pointer_sha256,
        "split_policy": split_policy,
        "excluded_eval_request_sha256": sorted(eval_requests),
        "student_base": student_base,
        "settings": settings_value,
        "train_sources": identity["train_sources"],
        "objects": object_values,
    }
    manifest_key = dataset_prefix + "manifest.json"
    for split in SPLITS:
        store.create_same(object_values[split]["key"], bodies[split])
    manifest_body = summary.canonical(manifest)
    store.create_same(manifest_key, manifest_body)
    counts = {split: len(rows[split]) for split in SPLITS}
    reference = {"schema_version": "milk.dataset-reference.v2", "scope_id": settings.scope_id, "uuid": dataset_uuid, "key": manifest_key, "sha256": summary.digest(manifest_body), "eval_pointer_sha256": eval_pointer_sha256, "counts": counts}
    status_key = _status(store, settings, reference)
    artifact_keys = [intent_key, receipt_key, *(object_values[split]["key"] for split in SPLITS), manifest_key, status_key, result_key]
    ready = training_ready(counts)
    result = {"schema_version": "milk.dataset-job-result.v2", "job_id": job_id, "state": "progressed", "next": "train" if ready else "summary", "dataset": reference, "artifact_keys": artifact_keys, "details": {"dataset_uuid": dataset_uuid, "counts": counts, "training_ready": ready}}
    store.create_same(result_key, summary.canonical(result))
    return {"state": "progressed", "identity": job_id, "artifacts": _artifacts(store, artifact_keys), "inference_calls": receipt["inference_calls"], "provider_calls": 0, "next": result["next"], "details": result["details"]}
