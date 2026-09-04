from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

from . import eval as eval_job
from . import eval_plan, semantic, summary


CODE_VERSION = "milk.dataset.v4"
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
    if not eval_job.current_matches(store, settings):
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
        or manifest.get("schema_version") not in {"milk.dataset.v2", "milk.dataset.v3"}
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
        or (
            manifest.get("schema_version") == "milk.dataset.v3"
            and (
                manifest.get("eval_manifest_key") != eval_pointer.get("manifest_key")
                or manifest.get("eval_manifest_sha256") != eval_pointer.get("sha256")
                or manifest.get("eval_content_sha256") != eval_pointer.get("content_sha256")
                or manifest.get("eval_revision_key") != eval_pointer.get("revision_key")
                or manifest.get("eval_revision_sha256") != eval_pointer.get("revision_sha256")
            )
        )
        or reference.get("counts") != counts
    ):
        return None
    return reference


def _eval_context_v2(store, pointer: dict, pointer_body: bytes) -> tuple[dict, str, list[dict], dict, None]:
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
    return pointer, summary.digest(pointer_body), cases, source["policy"], None


def _digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _eval_context_v3(store, settings, pointer: dict, pointer_body: bytes) -> tuple[dict, str, None, dict, dict[str, dict]]:
    manifest_key = pointer.get("manifest_key")
    manifest, manifest_body = _object(store, manifest_key if isinstance(manifest_key, str) else "")
    eval_uuid = pointer.get("uuid")
    eval_prefix = settings.scope_prefix + f"e/{eval_uuid}/"
    revision_key = manifest.get("revision_key")
    revision, revision_body = _object(store, revision_key if isinstance(revision_key, str) else "")
    identity = revision.get("identity") if isinstance(revision, dict) else None
    counts = manifest.get("target_split_counts")
    shards = manifest.get("shards")
    if (
        pointer.get("schema_version") != "milk.pointer.v2"
        or pointer.get("kind") != "eval"
        or pointer.get("scope_id") != settings.scope_id
        or not isinstance(eval_uuid, str)
        or manifest_key != eval_prefix + "manifest.json"
        or pointer.get("key") != manifest_key
        or summary.digest(manifest_body) != pointer.get("sha256")
        or manifest.get("schema_version") != "milk.eval-manifest.v3"
        or manifest.get("eval_uuid") != eval_uuid
        or manifest.get("scope_id") != settings.scope_id
        or manifest.get("profile") != settings.profile
        or revision_key != eval_prefix + "revision.json"
        or summary.digest(revision_body) != manifest.get("revision_sha256")
        or pointer.get("revision_key") != revision_key
        or pointer.get("revision_sha256") != manifest.get("revision_sha256")
        or revision.get("schema_version") != "milk.eval-revision.v3"
        or revision.get("eval_uuid") != eval_uuid
        or not isinstance(identity, dict)
        or identity.get("schema_version") != "milk.eval-revision-identity.v3"
        or identity.get("scope_id") != settings.scope_id
        or identity.get("profile") != settings.profile
        or manifest.get("context_key") != eval_prefix + "context.json.zst"
        or revision.get("context_key") != manifest.get("context_key")
        or revision.get("context_sha256") != manifest.get("context_sha256")
        or not _digest(manifest.get("context_sha256"))
        or identity.get("summary_sha256") != manifest.get("summary_sha256")
        or identity.get("readiness_sha256") != manifest.get("readiness_sha256")
        or identity.get("readiness_pointer_sha256") != manifest.get("readiness_pointer_sha256")
        or pointer.get("summary_sha256") != manifest.get("summary_sha256")
        or pointer.get("readiness_sha256") != manifest.get("readiness_sha256")
        or pointer.get("readiness_pointer_sha256") != manifest.get("readiness_pointer_sha256")
        or not isinstance(counts, dict)
        or set(counts) != set(SPLITS[1:])
        or any(not isinstance(counts[split], int) or isinstance(counts[split], bool) or counts[split] < 1 for split in SPLITS[1:])
        or identity.get("target_split_counts") != counts
        or identity.get("target_case_count") != manifest.get("target_case_count")
        or manifest.get("case_count") != manifest.get("target_case_count")
        or manifest.get("case_count") != sum(counts.values())
        or pointer.get("case_count") != manifest.get("case_count")
        or not isinstance(shards, list)
        or not shards
        or manifest.get("shard_count") != len(shards)
        or pointer.get("shard_count") != len(shards)
        or manifest.get("cases_content_sha256") != pointer.get("content_sha256")
        or not _digest(manifest.get("cases_content_sha256"))
        or not _digest(manifest.get("normalized_hashes_sha256"))
        or identity.get("shard_case_count") != manifest.get("shard_case_count")
        or not isinstance(manifest.get("shard_case_count"), int)
        or isinstance(manifest.get("shard_case_count"), bool)
        or not 1 <= manifest["shard_case_count"] <= 256
        or revision.get("revision_id") != summary.digest(identity)
        or not isinstance(identity.get("policy"), dict)
        or identity["policy"].get("split_version") != eval_plan.SPLIT_VERSION
    ):
        raise DatasetError("current eval manifest identity differs")

    try:
        context_body = store.get(manifest["context_key"]).body
    except FileNotFoundError as error:
        raise DatasetError("current eval context is missing") from error
    if summary.digest(context_body) != manifest["context_sha256"]:
        raise DatasetError("current eval context digest differs")
    try:
        context = json.loads(summary._zstd(context_body, True))
    except (summary.SummaryError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetError("current eval context is invalid") from error
    conversations = context.get("conversations") if isinstance(context, dict) else None
    conversation_fields = {
        "source_key",
        "source_object_sha256",
        "source_request_sha256",
        "source_response_sha256",
        "source_content_sha256",
        "split",
        "request",
        "response",
    }
    if (
        not isinstance(context, dict)
        or set(context) != {"schema_version", "summary_checkpoint", "conversations"}
        or context.get("schema_version") != "milk.eval-context.v3"
        or not isinstance(context.get("summary_checkpoint"), dict)
        or summary.digest(context["summary_checkpoint"]) != identity["summary_sha256"]
        or not isinstance(conversations, list)
        or len(conversations) != revision.get("context_conversation_count")
        or any(
            not isinstance(conversation, dict)
            or set(conversation) != conversation_fields
            or not isinstance(conversation.get("source_key"), str)
            or not conversation["source_key"]
            or any(not _digest(conversation.get(field)) for field in ("source_object_sha256", "source_request_sha256", "source_response_sha256", "source_content_sha256"))
            or conversation.get("split") not in {"train", "dev", "calibration", "sealed"}
            or not isinstance(conversation.get("request"), str)
            or not isinstance(conversation.get("response"), str)
            for conversation in conversations or []
        )
        or len({conversation["source_key"] for conversation in conversations}) != len(conversations)
    ):
        raise DatasetError("current eval context identity differs")

    expected_fields = {"split", "start", "end", "count", "cases_key", "cases_sha256", "cases_content_sha256", "validation_key", "validation_sha256"}
    split_objects = {split: [] for split in SPLITS[1:]}
    split_totals = {split: 0 for split in SPLITS[1:]}
    boundaries = {}
    boundary = 0
    for split in SPLITS[1:]:
        boundary += counts[split]
        boundaries[split] = boundary
    cursor = 0
    for shard in shards:
        if not isinstance(shard, dict) or set(shard) != expected_fields:
            raise DatasetError("current eval shard descriptor is invalid")
        split, start, end, count = (shard.get(name) for name in ("split", "start", "end", "count"))
        expected_key = eval_prefix + f"shards/{split}/{start:09d}-{end:09d}/cases.jsonl.zst" if isinstance(start, int) and isinstance(end, int) else ""
        expected_validation_key = expected_key.removesuffix("cases.jsonl.zst") + "validation.json"
        expected_split = next((name for name in SPLITS[1:] if cursor < boundaries[name]), None)
        if (
            not isinstance(split, str)
            or split not in split_objects
            or split != expected_split
            or not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or start != cursor
            or end <= start
            or count != end - start
            or end > boundaries[split]
            or end - start > manifest.get("shard_case_count")
            or shard.get("cases_key") != expected_key
            or shard.get("validation_key") != expected_validation_key
            or any(not _digest(shard.get(name)) for name in ("cases_sha256", "cases_content_sha256", "validation_sha256"))
        ):
            raise DatasetError("current eval shard descriptor is invalid")
        try:
            verified = eval_job._read_shard(store, revision, split, start, end)
        except eval_job.EvalError as error:
            raise DatasetError(str(error)) from error
        if verified != shard:
            raise DatasetError("current eval shard differs from its manifest")
        split_objects[split].append({
            "split": split,
            "start": start,
            "end": end,
            "count": count,
            "key": shard["cases_key"],
            "sha256": shard["cases_sha256"],
            "content_sha256": shard["cases_content_sha256"],
            "validation_key": shard["validation_key"],
            "validation_sha256": shard["validation_sha256"],
        })
        split_totals[split] += count
        cursor = end
    if (
        cursor != manifest["case_count"]
        or split_totals != counts
        or summary.digest({"schema_version": "milk.eval-content.v3", "shards": [shard["cases_content_sha256"] for shard in shards]}) != manifest["cases_content_sha256"]
    ):
        raise DatasetError("current eval shard set differs")
    objects = {
        split: {"count": counts[split], "root_sha256": summary.digest(split_objects[split]), "shards": split_objects[split]}
        for split in SPLITS[1:]
    }
    return pointer, summary.digest(pointer_body), None, identity["policy"], objects


def _eval_context(store, settings) -> tuple[dict, str, list[dict] | None, dict, dict[str, dict] | None]:
    if not eval_job.current_matches(store, settings):
        raise DatasetError("the current eval is missing or stale")
    pointer, pointer_body = _object(store, settings.scope_prefix + "e/current.json")
    if pointer.get("manifest_key") is None:
        return _eval_context_v2(store, pointer, pointer_body)
    return _eval_context_v3(store, settings, pointer, pointer_body)


def _train_sources(store, settings, eval_pointer: dict, count: int, text_bytes: int) -> list[dict]:
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
            or row.get("model_completed") is not True
            or row.get("modalities") != ["text"]
            or row.get("tool_definitions") != 0
            or row.get("tool_calls") != 0
            or not isinstance(request_sha256, str)
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
        if (
            parsed["object_sha256"] != row.get("object_sha256")
            or parsed["content_sha256"] != row.get("content_sha256")
            or parsed["request_sha256"] != row.get("request_sha256")
            or eval_plan.split_for(parsed["request_sha256"]) != "train"
            or not parsed["request_text"].strip()
            or not parsed["response_text"].strip()
        ):
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

    eval_pointer, eval_pointer_sha256, eval_cases, split_policy, eval_objects = _eval_context(store, settings)
    requested = _integer("MILK_DATASET_TRAIN_EXAMPLES", 128 if settings.profile == "production" else 1, 1, 256)
    text_bytes = _integer("MILK_DATASET_TEXT_BYTES", 2048, 128, 4096)
    eval_requests = {case["source_request_sha256"] for case in eval_cases or []}
    sources = _train_sources(store, settings, eval_pointer, requested, text_bytes)
    if len(sources) < requested:
        identity = summary.digest({"schema_version": "milk.dataset-wait.v2", "eval_pointer_sha256": eval_pointer_sha256, "requested": requested, "available": len(sources)})
        return {"state": "idle", "identity": identity, "artifacts": [], "inference_calls": 0, "provider_calls": 0, "next": "dataset", "details": {"reason": "insufficient_train_sources", "requested": requested, "available": len(sources)}}

    binding = semantic.binding("TEACHER")
    prompt_path = Path(__file__).resolve().parents[1] / runtime.job("dataset").system_prompt
    prompt = prompt_path.read_text()
    student_base = {"model_repo": runtime.student_base.model_repo, "model_revision": runtime.student_base.model_revision, "digest": runtime.student_base.digest}
    settings_value = {"teacher": binding, "prompt_sha256": summary.digest(prompt.encode()), "temperature": 0, "train_examples_requested": requested, "train_examples_effective": len(sources), "source_text_bytes": text_bytes}
    identity = {
        "schema_version": "milk.dataset-job-identity.v3" if eval_objects is not None else "milk.dataset-job-identity.v2",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "eval_uuid": eval_pointer["uuid"],
        "eval_pointer_sha256": eval_pointer_sha256,
        "split_policy": split_policy,
        "train_sources": [{key: source[key] for key in ("source_key", "source_object_sha256", "source_request_sha256", "source_response_sha256", "source_content_sha256")} for source in sources],
        "student_base": student_base,
        "settings": settings_value,
        "config_digest": runtime.digest,
    }
    if eval_objects is None:
        identity["eval_object_sha256"] = eval_pointer["sha256"]
        identity["excluded_eval_request_sha256"] = sorted(eval_requests)
    else:
        identity["eval_manifest_key"] = eval_pointer["manifest_key"]
        identity["eval_manifest_sha256"] = eval_pointer["sha256"]
        identity["eval_content_sha256"] = eval_pointer["content_sha256"]
        identity["eval_revision_sha256"] = eval_pointer["revision_sha256"]
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
    train_plain = b"".join(summary.canonical(row) for row in train_rows)
    train_content_sha256 = summary.digest(train_plain)
    if eval_objects is None:
        rows = {"train": train_rows, **{split: [case for case in eval_cases if case["split"] == split] for split in SPLITS[1:]}}
        plain = {"train": train_plain, **{split: b"".join(summary.canonical(row) for row in rows[split]) for split in SPLITS[1:]}}
        logical = {split: summary.digest(plain[split]) for split in SPLITS}
    else:
        logical = {"train": train_content_sha256, **{split: eval_objects[split]["root_sha256"] for split in SPLITS[1:]}}
    dataset_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:dataset:" + summary.digest({"job_id": job_id, "content_sha256": logical})))
    dataset_prefix = settings.scope_prefix + f"d/{dataset_uuid}/"
    train_body = summary._zstd(train_plain, False)
    train_object = {"key": dataset_prefix + "train.jsonl.zst", "sha256": summary.digest(train_body), "content_sha256": train_content_sha256, "count": len(train_rows)}
    if eval_objects is None:
        bodies = {"train": train_body, **{split: summary._zstd(plain[split], False) for split in SPLITS[1:]}}
        object_values = {
            split: {"key": dataset_prefix + f"{split}.jsonl.zst", "sha256": summary.digest(bodies[split]), "content_sha256": logical[split], "count": len(rows[split])}
            for split in SPLITS
        }
    else:
        bodies = {"train": train_body}
        object_values = {"train": train_object, **eval_objects}
    manifest = {
        "schema_version": "milk.dataset.v3" if eval_objects is not None else "milk.dataset.v2",
        "code_version": CODE_VERSION,
        "dataset_uuid": dataset_uuid,
        "job_id": job_id,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "eval_uuid": eval_pointer["uuid"],
        "eval_pointer_sha256": eval_pointer_sha256,
        "split_policy": split_policy,
        "student_base": student_base,
        "settings": settings_value,
        "train_sources": identity["train_sources"],
        "objects": object_values,
    }
    if eval_objects is None:
        manifest["excluded_eval_request_sha256"] = sorted(eval_requests)
    else:
        manifest.update({
            "eval_manifest_key": eval_pointer["manifest_key"],
            "eval_manifest_sha256": eval_pointer["sha256"],
            "eval_content_sha256": eval_pointer["content_sha256"],
            "eval_revision_key": eval_pointer["revision_key"],
            "eval_revision_sha256": eval_pointer["revision_sha256"],
        })
    manifest_key = dataset_prefix + "manifest.json"
    for split, body in bodies.items():
        store.create_same(object_values[split]["key"], body)
    manifest_body = summary.canonical(manifest)
    store.create_same(manifest_key, manifest_body)
    counts = split_counts(manifest)
    reference = {"schema_version": "milk.dataset-reference.v2", "scope_id": settings.scope_id, "uuid": dataset_uuid, "key": manifest_key, "sha256": summary.digest(manifest_body), "eval_pointer_sha256": eval_pointer_sha256, "counts": counts}
    status_key = _status(store, settings, reference)
    artifact_keys = [intent_key, receipt_key, *(object_values[split]["key"] for split in bodies), manifest_key, status_key, result_key]
    ready = training_ready(counts)
    result = {"schema_version": "milk.dataset-job-result.v2", "job_id": job_id, "state": "progressed", "next": "train" if ready else "summary", "dataset": reference, "artifact_keys": artifact_keys, "details": {"dataset_uuid": dataset_uuid, "counts": counts, "training_ready": ready}}
    store.create_same(result_key, summary.canonical(result))
    return {"state": "progressed", "identity": job_id, "artifacts": _artifacts(store, artifact_keys), "inference_calls": receipt["inference_calls"], "provider_calls": 0, "next": result["next"], "details": result["details"]}
