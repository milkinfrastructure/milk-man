from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
import uuid

from . import eval_plan, semantic, summary


CODE_VERSION = "milk.eval.v25"
GENERATOR_BATCH_CASES = 64
MAX_GENERATION_ATTEMPTS = 8
VERDICT_SCHEMA = "milk.eval-verdicts.v3"
VERDICTS = ("accepted", "vacuous", "copied", "duplicate")
ORACLE_SCALAR_TYPES = ("string", "number", "integer", "boolean", "null")
ORACLE_SPEC_TYPES = ("none", "object", "array", *ORACLE_SCALAR_TYPES)


class EvalError(ValueError):
    pass


class BusyError(RuntimeError):
    def __init__(self, identity: str):
        super().__init__("another process changed this eval revision")
        self.identity = identity


def _object(store, key: str) -> tuple[dict, bytes]:
    body = store.get(key).body
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvalError(f"{key} is not valid JSON") from error
    if not isinstance(value, dict):
        raise EvalError(f"{key} must contain an object")
    return value, body


def _current(store, settings) -> tuple[dict, dict, dict, dict, str]:
    prefix = settings.scope_prefix
    summary_pointer, unused_summary_pointer_body = _object(store, prefix + "s/current.json")
    readiness_pointer, readiness_pointer_body = _object(store, prefix + "readiness/current.json")
    if summary_pointer.get("schema_version") != "milk.pointer.v2" or summary_pointer.get("kind") != "summary" or summary_pointer.get("scope_id") != settings.scope_id:
        raise EvalError("current summary pointer is invalid")
    if readiness_pointer.get("schema_version") != "milk.pointer.v2" or readiness_pointer.get("kind") != "readiness" or readiness_pointer.get("scope_id") != settings.scope_id:
        raise EvalError("current readiness pointer is invalid")
    summary_value, summary_body = _object(store, summary_pointer.get("key", ""))
    readiness, readiness_body = _object(store, readiness_pointer.get("key", ""))
    if summary.digest(summary_body) != summary_pointer.get("sha256") or summary_value.get("summary_uuid") != summary_pointer.get("uuid") or summary_value.get("scope_id") != settings.scope_id or summary_value.get("profile") != settings.profile:
        raise EvalError("current summary identity differs")
    if summary.digest(readiness_body) != readiness_pointer.get("sha256") or readiness.get("schema_version") != "milk.readiness.v3" or readiness.get("readiness_uuid") != readiness_pointer.get("uuid") or readiness.get("scope_id") != settings.scope_id or readiness.get("profile") != settings.profile:
        raise EvalError("current readiness identity differs")
    if readiness.get("summary_sha256") != summary_pointer.get("sha256") or readiness_pointer.get("summary_sha256") != summary_pointer.get("sha256"):
        raise EvalError("readiness does not bind the current summary")
    return summary_pointer, summary_value, readiness_pointer, readiness, summary.digest(readiness_pointer_body)


def current_matches(
    store,
    settings,
    target: int | None = None,
    shard_cases: int | None = None,
    revision_id: str | None = None,
) -> bool:
    summary_pointer, unused_summary, readiness_pointer, unused_readiness, readiness_pointer_sha256 = _current(store, settings)
    try:
        pointer, pointer_body = _object(store, settings.scope_prefix + "e/current.json")
    except FileNotFoundError:
        return False
    if (
        pointer.get("schema_version") != "milk.pointer.v2"
        or pointer.get("kind") != "eval"
        or pointer.get("scope_id") != settings.scope_id
        or pointer.get("summary_sha256") != summary_pointer.get("sha256")
        or pointer.get("readiness_sha256") != readiness_pointer.get("sha256")
        or pointer.get("readiness_pointer_sha256") != readiness_pointer_sha256
    ):
        return False
    item = store.get(pointer.get("key", ""))
    if summary.digest(item.body) != pointer.get("sha256"):
        raise EvalError("current eval object digest differs")
    if pointer.get("manifest_key") is None:
        return False
    try:
        manifest = json.loads(item.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvalError("current eval manifest is invalid") from error
    if not isinstance(manifest, dict):
        raise EvalError("current eval manifest identity differs")
    # A prior eval revision is a stale candidate, not a corrupt current one.
    # Its immutable artifacts remain readable, but it cannot satisfy this code.
    if (
        manifest.get("schema_version") != "milk.eval-manifest.v3"
        or manifest.get("code_version") != CODE_VERSION
    ):
        return False
    if target is not None and manifest.get("target_case_count") != target:
        return False
    if shard_cases is not None and manifest.get("shard_case_count") != shard_cases:
        return False
    revision_key = manifest.get("revision_key")
    try:
        revision, revision_body = _object(store, revision_key if isinstance(revision_key, str) else "")
    except FileNotFoundError as error:
        raise EvalError("current eval revision is missing") from error
    identity = revision.get("identity") if isinstance(revision, dict) else None
    eval_uuid = pointer.get("uuid")
    eval_prefix = settings.scope_prefix + f"e/{eval_uuid}/"
    if (
        pointer.get("key") != eval_prefix + "manifest.json"
        or pointer.get("manifest_key") != pointer.get("key")
        or manifest.get("eval_uuid") != eval_uuid
        or manifest.get("revision_key") != pointer.get("revision_key")
        or manifest.get("revision_key") != eval_prefix + "revision.json"
        or manifest.get("revision_sha256") != pointer.get("revision_sha256")
        or manifest.get("context_key") != eval_prefix + "context.json.zst"
        or manifest.get("summary_sha256") != pointer.get("summary_sha256")
        or manifest.get("readiness_sha256") != pointer.get("readiness_sha256")
        or manifest.get("readiness_pointer_sha256") != pointer.get("readiness_pointer_sha256")
        or manifest.get("case_count") != pointer.get("case_count")
        or manifest.get("target_case_count") != pointer.get("case_count")
        or manifest.get("shard_count") != pointer.get("shard_count")
        or manifest.get("cases_content_sha256") != pointer.get("content_sha256")
        or revision.get("schema_version") != "milk.eval-revision.v3"
        or revision.get("eval_uuid") != eval_uuid
        or summary.digest(revision_body) != manifest.get("revision_sha256")
        or revision.get("context_key") != manifest.get("context_key")
        or revision.get("context_sha256") != manifest.get("context_sha256")
        or not isinstance(identity, dict)
        or identity.get("schema_version") != "milk.eval-revision-identity.v3"
        or identity.get("code_version") != CODE_VERSION
        or revision.get("revision_id") != summary.digest(identity)
        or eval_uuid != str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:eval-revision:" + revision.get("revision_id", "")))
        or identity.get("scope_id") != settings.scope_id
        or identity.get("profile") != settings.profile
        or identity.get("summary_sha256") != manifest.get("summary_sha256")
        or identity.get("readiness_sha256") != manifest.get("readiness_sha256")
        or identity.get("readiness_pointer_sha256") != manifest.get("readiness_pointer_sha256")
        or identity.get("target_case_count") != manifest.get("target_case_count")
        or identity.get("target_split_counts") != manifest.get("target_split_counts")
        or identity.get("shard_case_count") != manifest.get("shard_case_count")
    ):
        raise EvalError("current eval manifest identity differs")
    if revision_id is not None and revision.get("revision_id") != revision_id:
        return False
    return summary.digest(pointer_body) == summary.digest(pointer)


def _labels(store, settings, summary_value: dict) -> list[dict]:
    semantic_value = summary_value.get("semantic")
    sample = semantic_value.get("sample") if isinstance(semantic_value, dict) else None
    if not isinstance(sample, list):
        raise EvalError("current summary semantic sample is invalid")
    labels = []
    for reference in sample:
        if not isinstance(reference, dict):
            raise EvalError("current summary label reference is invalid")
        key = reference.get("label_key")
        if not isinstance(key, str) or not key.startswith(settings.scope_prefix + "l/"):
            raise EvalError("current summary label key is outside the scope")
        value, body = _object(store, key)
        if (
            summary.digest(body) != reference.get("label_sha256")
            or value.get("schema_version") != "milk.semantic-label.v2"
            or value.get("scope_id") != settings.scope_id
            or value.get("profile") != settings.profile
            or value.get("content_sha256") != reference.get("content_sha256")
            or not isinstance(value.get("label"), dict)
            or value["label"].get("row_id") != reference.get("content_sha256")
        ):
            raise EvalError("current summary label identity differs")
        labels.append({**value["label"], **reference})
    return labels


def _plan(store, settings, summary_value: dict, readiness: dict) -> dict:
    try:
        value = eval_plan.build(_labels(store, settings, summary_value), settings.profile)
        selected = eval_plan.select_sources(value)
    except eval_plan.PlanError as error:
        raise EvalError(str(error)) from error
    expected = {"policy": value["policy"], "counts": value["counts"], "missing": value["missing"]}
    if readiness.get("eval_plan") != expected or not value["ready"] or readiness.get("ready") is not True:
        raise EvalError("current readiness does not admit the deterministic eval plan")
    return selected


def _generation_schema(count: int, oracle: str, schema_kind: str) -> dict:
    property_spec = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 128},
            "type": {"type": "string", "enum": list(ORACLE_SCALAR_TYPES)},
            "required": {"type": "boolean"},
        },
        "required": ["name", "type", "required"],
        "additionalProperties": False,
    }
    if oracle in {"exact", "reference"}:
        spec_type = {"type": "string", "enum": ["none"]}
        spec_properties = {"type": "array", "items": property_spec, "maxItems": 0}
        spec_items = {"type": "string", "enum": ["none"]}
        expected = {"type": "string", "minLength": 1, "maxLength": 4096}
    elif oracle == "schema" and schema_kind == "object":
        spec_type = {"type": "string", "enum": ["object"]}
        spec_properties = {"type": "array", "items": property_spec, "minItems": 1, "maxItems": 16}
        spec_items = {"type": "string", "enum": ["none"]}
        expected = {"type": "string", "maxLength": 4096}
    elif oracle == "schema" and schema_kind == "array":
        spec_type = {"type": "string", "enum": ["array"]}
        spec_properties = {"type": "array", "items": property_spec, "maxItems": 0}
        spec_items = {"type": "string", "enum": list(ORACLE_SCALAR_TYPES)}
        expected = {"type": "string", "maxLength": 4096}
    elif oracle == "schema" and schema_kind in ORACLE_SCALAR_TYPES:
        spec_type = {"type": "string", "enum": [schema_kind]}
        spec_properties = {"type": "array", "items": property_spec, "maxItems": 0}
        spec_items = {"type": "string", "enum": ["none"]}
        expected = {"type": "string", "maxLength": 4096}
    else:
        raise EvalError("eval generation schema binding is invalid")
    oracle_spec = {
        "type": "object",
        "properties": {
            "type": spec_type,
            "properties": spec_properties,
            "items": spec_items,
        },
        "required": ["type", "properties", "items"],
        "additionalProperties": False,
    }
    item = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "minLength": 1, "maxLength": 4096},
            "expected": expected,
            "oracle_spec": oracle_spec,
        },
        "required": ["input", "expected", "oracle_spec"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["milk.eval-generated-cases.v1"]},
            "cases": {"type": "array", "items": item, "minItems": count, "maxItems": count},
        },
        "required": ["schema_version", "cases"],
        "additionalProperties": False,
    }


def _compile_oracle_spec(value: object, oracle: str, schema_kind: str | None = None) -> tuple[dict, dict | None]:
    if not isinstance(value, dict) or set(value) != {"type", "properties", "items"}:
        raise ValueError("invalid oracle spec")
    kind = value.get("type")
    properties = value.get("properties")
    items = value.get("items")
    if kind not in ORACLE_SPEC_TYPES or not isinstance(properties, list) or len(properties) > 16 or items not in ("none", *ORACLE_SCALAR_TYPES):
        raise ValueError("invalid oracle spec")
    if oracle in {"exact", "reference"}:
        return {"type": "none", "properties": [], "items": "none"}, None
    if oracle != "schema" or kind == "none":
        raise ValueError("invalid oracle spec")
    if schema_kind is not None and kind != schema_kind:
        raise ValueError("invalid oracle spec")
    if kind == "object":
        checked_properties = []
        names = set()
        for field in properties:
            if not isinstance(field, dict) or set(field) != {"name", "type", "required"}:
                raise ValueError("invalid oracle spec")
            name = field.get("name")
            field_type = field.get("type")
            required = field.get("required")
            if (
                not isinstance(name, str)
                or not 1 <= len(name.encode()) <= 128
                or any(ord(character) < 32 for character in name)
                or name in names
                or field_type not in ORACLE_SCALAR_TYPES
                or type(required) is not bool
            ):
                raise ValueError("invalid oracle spec")
            names.add(name)
            checked_properties.append({"name": name, "type": field_type, "required": required})
        if not checked_properties:
            raise ValueError("invalid oracle spec")
        checked_properties.sort(key=lambda field: field["name"])
        normalized = {"type": kind, "properties": checked_properties, "items": "none"}
        schema = {
            "type": "object",
            "properties": {field["name"]: {"type": field["type"]} for field in checked_properties},
            "required": [field["name"] for field in checked_properties if field["required"]],
            "additionalProperties": False,
        }
    elif kind == "array":
        if items == "none":
            raise ValueError("invalid oracle spec")
        normalized = {"type": kind, "properties": [], "items": items}
        schema = {"type": "array", "items": {"type": items}}
    else:
        normalized = {"type": kind, "properties": [], "items": "none"}
        schema = {"type": kind}
    return normalized, schema


def _wire_case(value: dict, oracle: str) -> dict:
    spec = value.get("oracle_spec")
    if spec is None:
        expected = value.get("expected")
        if oracle in {"exact", "reference"}:
            spec = {"type": "none", "properties": [], "items": "none"}
        elif isinstance(expected, dict) and expected.get("type") == "object":
            properties = expected.get("properties")
            required = expected.get("required")
            if isinstance(properties, dict) and isinstance(required, list):
                spec = {
                    "type": "object",
                    "properties": [
                        {"name": name, "type": field.get("type"), "required": name in required}
                        for name, field in properties.items()
                        if isinstance(field, dict)
                    ],
                    "items": "none",
                }
        elif isinstance(expected, dict) and expected.get("type") == "array" and isinstance(expected.get("items"), dict):
            spec = {"type": "array", "properties": [], "items": expected["items"].get("type")}
        elif isinstance(expected, dict):
            spec = {"type": expected.get("type"), "properties": [], "items": "none"}
    normalized, compiled = _compile_oracle_spec(spec, oracle)
    if oracle == "schema" and compiled != value.get("expected"):
        raise EvalError("stored eval schema oracle cannot be represented on the generation wire")
    return {
        "case_id": value["case_id"],
        "input": value["input"],
        "expected": "" if oracle == "schema" else value["expected"],
        "oracle_spec": normalized,
    }


def _generation_contract(value: dict, shard_plan: dict, *, stored: bool = False) -> dict:
    version = "milk.eval-generation.v3" if stored else "milk.eval-generated-cases.v1"
    fields = {"case_id", "input", "expected", "oracle_spec"} if stored else {"input", "expected", "oracle_spec"}
    if not isinstance(value, dict) or set(value) != {"schema_version", "cases"} or value.get("schema_version") != version or not isinstance(value.get("cases"), list):
        raise ValueError("eval generation has invalid fields")
    if len(value["cases"]) != len(shard_plan["cases"]):
        raise ValueError("eval generation has the wrong case count")
    generated_cases = value["cases"]
    checked = []
    invalid = []
    for planned, generated in zip(shard_plan["cases"], generated_cases):
        if not isinstance(generated, dict) or set(generated) != fields or (stored and generated.get("case_id") != planned["case_id"]):
            invalid.append((planned["case_id"], "identity"))
            continue
        text = generated.get("input")
        output = generated.get("expected")
        if not isinstance(text, str) or not 1 <= len(text.encode()) <= 4096 or any(ord(character) < 9 for character in text):
            invalid.append((planned["case_id"], "input"))
            continue
        try:
            oracle_spec, compiled = _compile_oracle_spec(
                generated.get("oracle_spec"), planned["oracle"], shard_plan.get("schema_kind")
            )
        except ValueError:
            invalid.append((planned["case_id"], "oracle_spec"))
            continue
        if planned["oracle"] in {"exact", "reference"}:
            if not isinstance(output, str) or not 1 <= len(output.encode()) <= 4096:
                invalid.append((planned["case_id"], "expected"))
                continue
        else:
            if (
                compiled is None
                or (stored and output != compiled)
                or (not stored and (not isinstance(output, str) or len(output.encode()) > 4096))
                or len(summary.canonical(compiled)) > 4096
            ):
                invalid.append((planned["case_id"], "expected"))
                continue
            output = compiled
        checked.append({"case_id": planned["case_id"], "input": text, "expected": output, "oracle_spec": oracle_spec})
    if invalid:
        reasons = ",".join(f"{name}:{count}" for name, count in sorted(Counter(reason for unused_case_id, reason in invalid).items()))
        sample = ",".join(f"{case_id}:{reason}" for case_id, reason in invalid[:8])
        raise ValueError(f"eval generation has invalid cases ({reasons}); sample={sample}")
    return {"schema_version": "milk.eval-generation.v3", "cases": checked}


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _cases(generation: dict, shard_plan: dict, corpus: dict, summary_sha256: str, accepted_hashes: set[str]) -> tuple[list[dict], list[dict], list[dict]]:
    by_content = {source["source_content_sha256"]: source for source in corpus["conversations"]}
    copied_inputs = {
        _normalized(text)
        for source in corpus["conversations"]
        for text in (source.get("request"), source.get("response"))
        if isinstance(text, str)
    }
    cases, hashes, rejected = [], [], []
    seen = set()
    for planned, generated in zip(shard_plan["cases"], generation["cases"]):
        source = by_content.get(planned["content_sha256"])
        if source is None:
            raise ValueError(f"{planned['case_id']} has no bound source")
        normalized = _normalized(generated["input"])
        input_sha256 = summary.digest(normalized.encode())
        expected = generated["expected"]
        reason = None
        if not normalized:
            reason = "vacuous"
        elif input_sha256 in accepted_hashes or input_sha256 in seen:
            reason = "duplicate"
        if reason is None and normalized in copied_inputs:
            reason = "copied"
        if reason is not None:
            guidance = {
                "vacuous": "Create a substantive answerable task.",
                "duplicate": "Change the task framing and several concrete details.",
                "copied": "Synthesize a distinct task; do not copy the source request or response.",
            }[reason]
            rejected.append({"case_id": planned["case_id"], "accepted": False, "reason": reason, "guidance": guidance})
            continue
        seen.add(input_sha256)
        cases.append({
            "schema_version": "milk.eval-case.v2",
            "case_id": planned["case_id"],
            "order": planned["order"],
            "split": planned["split"],
            "selection": planned["selection"],
            "tail_reason": planned["tail_reason"],
            "operation": planned["operation"],
            "oracle": planned["oracle"],
            "source_example_index": planned["source_example_index"],
            "source_example_count": planned["source_example_count"],
            "input": generated["input"],
            "expected": expected,
            "source_key": planned["source_key"],
            "source_object_sha256": planned["source_object_sha256"],
            "source_request_sha256": planned["request_sha256"],
            "source_response_sha256": planned["response_sha256"],
            "source_content_sha256": planned["content_sha256"],
            "summary_sha256": summary_sha256,
        })
        hashes.append({"case_id": planned["case_id"], "input_sha256": input_sha256})
    return cases, hashes, rejected


def _verdict_contract(value: dict, cases: list[dict]) -> dict:
    if not isinstance(value, dict) or set(value) != {"schema_version", "verdicts"} or value.get("schema_version") != VERDICT_SCHEMA or not isinstance(value.get("verdicts"), list):
        raise ValueError("eval validation has invalid fields")
    if len(value["verdicts"]) != len(cases):
        raise ValueError("eval validation has the wrong verdict count")
    checked = []
    for case, verdict in zip(cases, value["verdicts"]):
        if not isinstance(verdict, dict) or set(verdict) != {"case_id", "accepted", "reason", "guidance"} or verdict.get("case_id") != case["case_id"]:
            raise ValueError("eval validation changed case identity or order")
        guidance = verdict.get("guidance")
        if (
            type(verdict.get("accepted")) is not bool
            or verdict.get("reason") not in VERDICTS
            or verdict["accepted"] != (verdict["reason"] == "accepted")
            or not isinstance(guidance, str)
            or len(guidance.encode()) > 512
            or verdict["accepted"] != (guidance == "")
        ):
            raise ValueError("eval validation returned an invalid verdict")
        checked.append(verdict)
    return {"schema_version": VERDICT_SCHEMA, "verdicts": checked}


def _binding(prefix: str) -> dict:
    return {
        "base_url": os.environ.get(f"MILK_{prefix}_BASE_URL", ""),
        "model": os.environ.get(f"MILK_{prefix}_MODEL", ""),
        "api_mode": os.environ.get(f"MILK_{prefix}_API_MODE", "chat_completions"),
        "reasoning_effort": os.environ.get("MILK_REASONING_EFFORT", ""),
        "max_output_tokens": os.environ.get(f"MILK_{prefix}_MAX_OUTPUT_TOKENS", ""),
    }


def _provider_receipt(value: object, job: str, prefix: str, input_value: dict, output: dict) -> dict:
    binding = semantic.binding(prefix)
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "milk.semantic-provider-receipt.v2"
        or value.get("job") != job
        or value.get("input_sha256") != summary.digest(input_value)
        or value.get("output") != output
        or value.get("output_sha256") != summary.digest(output)
        or value.get("model") != binding["model"]
        or value.get("api_mode") != binding["api_mode"]
        or value.get("reasoning_effort") != binding["reasoning_effort"]
        or value.get("max_output_tokens") != binding["max_output_tokens"]
        or value.get("strict_tools") is not True
        or type(value.get("inference_calls")) is not int
        or value["inference_calls"] < 1
    ):
        raise EvalError("stored semantic provider receipt differs")
    return value


def _artifacts(store, keys: list[str]) -> list[dict]:
    return [{"key": key, "sha256": summary.digest(store.get(key).body)} for key in dict.fromkeys(keys)]


def _status_value(store, settings) -> tuple[dict, str]:
    key = settings.scope_prefix + "status/current.json"
    try:
        value, unused_body = _object(store, key)
    except FileNotFoundError:
        value = {"schema_version": "milk.status.v2", "scope_id": settings.scope_id, "profile": settings.profile}
    if value.get("schema_version") != "milk.status.v2" or value.get("scope_id") != settings.scope_id or value.get("profile") != settings.profile:
        raise EvalError("current status identity differs")
    return value, key


def _completed(store, settings, revision: dict) -> tuple[int, str]:
    status, key = _status_value(store, settings)
    progress = status.get("eval_generation")
    if not isinstance(progress, dict) or progress.get("revision_sha256") != summary.digest(revision):
        return 0, key
    completed = progress.get("completed_case_count")
    target = revision["identity"]["target_case_count"]
    if (
        progress.get("schema_version") != "milk.eval-progress.v3"
        or progress.get("eval_uuid") != revision["eval_uuid"]
        or progress.get("target_case_count") != target
        or progress.get("shard_case_count") != revision["identity"]["shard_case_count"]
        or type(completed) is not int
        or not 0 <= completed <= target
    ):
        raise EvalError("stored eval progress identity differs")
    return completed, key


def _advance_progress(store, settings, revision: dict, completed: int, last_shard: dict | None) -> str:
    status, key = _status_value(store, settings)
    progress = {
        "schema_version": "milk.eval-progress.v3",
        "eval_uuid": revision["eval_uuid"],
        "revision_sha256": summary.digest(revision),
        "target_case_count": revision["identity"]["target_case_count"],
        "shard_case_count": revision["identity"]["shard_case_count"],
        "completed_case_count": completed,
        "last_shard": last_shard,
    }
    try:
        summary._advance(store, key, {**status, "eval_generation": progress, "next_action": "eval"})
    except summary.BusyError as error:
        raise BusyError(error.identity) from error
    return key


def _complete_status(store, settings, pointer: dict) -> str:
    status, key = _status_value(store, settings)
    status = {name: value for name, value in status.items() if name != "eval_generation"}
    try:
        summary._advance(store, key, {**status, "eval": pointer, "next_action": "dataset"})
    except summary.BusyError as error:
        raise BusyError(error.identity) from error
    return key


def _seed_identity(plan: dict) -> list[dict]:
    fields = ("case_id", "order", "split", "selection", "tail_reason", "source_key", "source_object_sha256", "request_sha256", "response_sha256", "content_sha256", "label_key", "label_sha256", "operation", "oracle")
    return [{key: case[key] for key in fields} for case in plan["cases"]]


def _generation_source_identity(plan: dict) -> list[dict]:
    fields = (
        "split", "selection", "tail_reason", "source_key", "source_object_sha256", "request_sha256",
        "response_sha256", "content_sha256", "label_key", "label_sha256", "operation", "oracle",
    )
    return [{key: source[key] for key in fields} for source in plan["sources"]]


def _revision_identity(settings, runtime, summary_pointer: dict, readiness_pointer: dict, readiness_pointer_sha256: str, plan: dict, eval_prompt: str, target: int, shard_cases: int) -> dict:
    generation_sources = plan["sources"]
    target_splits = eval_plan.target_allocation(plan, target)
    source_splits = Counter(source["split"] for source in generation_sources)
    if any(count and not source_splits[split] for split, count in target_splits.items()):
        raise EvalError("the eval revision has no held-out source for a required split")
    return {
        "schema_version": "milk.eval-revision-identity.v3",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "summary_sha256": summary_pointer["sha256"],
        "readiness_sha256": readiness_pointer["sha256"],
        "readiness_pointer_sha256": readiness_pointer_sha256,
        "config_digest": runtime.digest,
        "policy": plan["policy"],
        "source_seeds": _seed_identity(plan),
        "generation_sources": _generation_source_identity({"sources": generation_sources}),
        "generation_source_count": len(generation_sources),
        "generation_source_split_counts": {split: source_splits[split] for split in eval_plan.SPLITS},
        "cases_per_conversation": target // len(generation_sources),
        "operation_schedule": eval_plan.OPERATION_SCHEDULE_VERSION,
        "target_case_count": target,
        "target_split_counts": target_splits,
        "shard_case_count": shard_cases,
        "eval_prompt_sha256": summary.digest(eval_prompt.encode()),
        "eval_binding_sha256": summary.digest(_binding("EVAL")),
        "validation": "deterministic-local.v1",
    }


def _context_rows(plan: dict) -> list[dict]:
    return [
        {
            "key": source["source_key"],
            "object_sha256": source["source_object_sha256"],
            "request_sha256": source["request_sha256"],
            "response_sha256": source["response_sha256"],
            "content_sha256": source["content_sha256"],
        }
        for source in plan["sources"]
    ]


def _build_context(store, settings, summary_value: dict, rows: list[dict]) -> dict:
    conversations = []
    for row in rows:
        parsed = summary.parse_capture(store, settings, row["key"])
        if (
            parsed["object_sha256"] != row.get("object_sha256")
            or parsed["request_sha256"] != row.get("request_sha256")
            or parsed["response_sha256"] != row.get("response_sha256")
            or parsed["content_sha256"] != row.get("content_sha256")
        ):
            raise EvalError("eval context capture identity differs")
        conversations.append({
            "source_key": parsed["key"],
            "source_object_sha256": parsed["object_sha256"],
            "source_request_sha256": parsed["request_sha256"],
            "source_response_sha256": parsed["response_sha256"],
            "source_content_sha256": parsed["content_sha256"],
            "split": eval_plan.split_for(parsed["request_sha256"]),
            "request": parsed["request_text"],
            "response": parsed["response_text"],
        })
    return {"schema_version": "milk.eval-context.v3", "summary_checkpoint": summary_value, "conversations": conversations}


def _revision(store, settings, summary_value: dict, plan: dict, identity: dict) -> tuple[dict, dict, list[str]]:
    revision_id = summary.digest(identity)
    eval_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:eval-revision:" + revision_id))
    eval_prefix = settings.scope_prefix + f"e/{eval_uuid}/"
    revision_key = eval_prefix + "revision.json"
    context_key = eval_prefix + "context.json.zst"
    try:
        revision, unused_revision_body = _object(store, revision_key)
        if revision.get("schema_version") != "milk.eval-revision.v3" or revision.get("revision_id") != revision_id or revision.get("eval_uuid") != eval_uuid or revision.get("identity") != identity:
            raise EvalError("stored eval revision identity differs")
        context_body = store.get(context_key).body
        if summary.digest(context_body) != revision.get("context_sha256"):
            raise EvalError("stored eval context digest differs")
    except FileNotFoundError:
        rows = _context_rows(plan)
        context = _build_context(store, settings, summary_value, rows)
        context_body = summary._zstd(summary.canonical(context), False)
        store.create_same(context_key, context_body)
        revision = {
            "schema_version": "milk.eval-revision.v3",
            "revision_id": revision_id,
            "eval_uuid": eval_uuid,
            "identity": identity,
            "context_key": context_key,
            "context_sha256": summary.digest(context_body),
            "context_conversation_count": len(context["conversations"]),
        }
        store.create_same(revision_key, summary.canonical(revision))
    try:
        context = json.loads(summary._zstd(context_body, True))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvalError("stored eval context is invalid") from error
    if not isinstance(context, dict) or context.get("schema_version") != "milk.eval-context.v3" or not isinstance(context.get("conversations"), list) or len(context["conversations"]) != revision.get("context_conversation_count") or len(context["conversations"]) != identity["generation_source_count"]:
        raise EvalError("stored eval context identity differs")
    return revision, context, [revision_key, context_key]


def _range_name(start: int, end: int) -> str:
    return f"{start:09d}-{end:09d}"


def _shard_keys(eval_prefix: str, split: str, start: int, end: int) -> dict[str, str]:
    prefix = eval_prefix + f"shards/{split}/{_range_name(start, end)}/"
    return {"cases": prefix + "cases.jsonl.zst", "ledger": eval_prefix + f"ledgers/{end:09d}.bin", "validation": prefix + "validation.json"}


def _ledger_values(body: bytes, count: int) -> set[str]:
    if len(body) != count * 32:
        raise EvalError("the eval normalized-hash ledger count differs")
    values = [body[offset : offset + 32] for offset in range(0, len(body), 32)]
    if values != sorted(values) or len(set(values)) != count:
        raise EvalError("the eval normalized-hash ledger is not sorted and unique")
    return {value.hex() for value in values}


def _ledger(store, eval_prefix: str, count: int) -> tuple[set[str], bytes]:
    if count == 0:
        return set(), b""
    try:
        body = store.get(eval_prefix + f"ledgers/{count:09d}.bin").body
    except FileNotFoundError as error:
        raise EvalError("the prior eval normalized-hash ledger is missing") from error
    return _ledger_values(body, count), body


def _ledger_body(hashes: set[str]) -> bytes:
    try:
        return b"".join(bytes.fromhex(value) for value in sorted(hashes))
    except ValueError as error:
        raise EvalError("the eval normalized hash is invalid") from error


def _case_source_matches(case: object, split: str) -> bool:
    if not isinstance(case, dict) or case.get("schema_version") != "milk.eval-case.v2" or not isinstance(case.get("source_request_sha256"), str):
        return False
    try:
        return eval_plan.split_for(case["source_request_sha256"]) == split
    except eval_plan.PlanError:
        return False


def _read_shard(store, revision: dict, split: str, start: int, end: int) -> dict | None:
    eval_prefix = revision["context_key"].removesuffix("context.json.zst")
    keys = _shard_keys(eval_prefix, split, start, end)
    try:
        cases_body = store.get(keys["cases"]).body
        ledger_body = store.get(keys["ledger"]).body
        validation, validation_body = _object(store, keys["validation"])
    except FileNotFoundError:
        return None
    try:
        cases_plain = summary._zstd(cases_body, True)
        cases = [json.loads(line) for line in cases_plain.splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvalError("stored eval shard cases are invalid") from error
    count = end - start
    case_ids = [summary.digest(f"{revision['eval_uuid']}\0{ordinal}".encode()) for ordinal in range(start, end)]
    hashes = validation.get("normalized_hashes") if isinstance(validation, dict) else None
    verdicts = validation.get("verdicts") if isinstance(validation, dict) else None
    try:
        checked_verdicts = _verdict_contract(
            {"schema_version": VERDICT_SCHEMA, "verdicts": verdicts}, cases
        )
    except (KeyError, TypeError, ValueError):
        checked_verdicts = None
    expected_hashes = [
        {"case_id": case["case_id"], "input_sha256": summary.digest(_normalized(case.get("input", "")).encode())}
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("input"), str)
    ]
    prior_hashes, unused_prior_body = _ledger(store, eval_prefix, start)
    ledger_hashes = _ledger_values(ledger_body, end)
    current_hashes = {item["input_sha256"] for item in expected_hashes}
    if (
        len(cases) != count
        or [case.get("case_id") for case in cases if isinstance(case, dict)] != case_ids
        or [case.get("order") for case in cases if isinstance(case, dict)] != list(range(start, end))
        or any(case.get("split") != split for case in cases if isinstance(case, dict))
        or any(not _case_source_matches(case, split) for case in cases)
        or validation.get("schema_version") != "milk.eval-validation-shard.v3"
        or validation.get("eval_uuid") != revision["eval_uuid"]
        or validation.get("revision_sha256") != summary.digest(revision)
        or validation.get("split") != split
        or validation.get("start") != start
        or validation.get("end") != end
        or validation.get("accepted") is not True
        or validation.get("case_count") != count
        or validation.get("cases_sha256") != summary.digest(cases_body)
        or validation.get("cases_content_sha256") != summary.digest(cases_plain)
        or not isinstance(hashes, list)
        or hashes != expected_hashes
        or len({item["input_sha256"] for item in hashes}) != count
        or current_hashes & prior_hashes
        or ledger_hashes != prior_hashes | current_hashes
        or validation.get("normalized_ledger_sha256") != summary.digest(ledger_body)
        or not isinstance(verdicts, list)
        or checked_verdicts is None
        or [item["case_id"] for item in checked_verdicts["verdicts"] if item["accepted"]] != case_ids
    ):
        raise EvalError("stored eval shard identity differs")
    return {
        "split": split,
        "start": start,
        "end": end,
        "count": count,
        "cases_key": keys["cases"],
        "cases_sha256": summary.digest(cases_body),
        "cases_content_sha256": validation.get("cases_content_sha256"),
        "validation_key": keys["validation"],
        "validation_sha256": summary.digest(validation_body),
    }


def _write_shard(store, revision: dict, split: str, start: int, end: int, cases: list[dict], hashes: list[dict], verdicts: dict, prior_hashes: set[str]) -> tuple[dict, list[str]]:
    eval_prefix = revision["context_key"].removesuffix("context.json.zst")
    keys = _shard_keys(eval_prefix, split, start, end)
    cases_plain = b"".join(summary.canonical(case) for case in cases)
    cases_body = summary._zstd(cases_plain, False)
    current_hashes = {item["input_sha256"] for item in hashes}
    if len(prior_hashes) != start or len(current_hashes) != len(cases) or prior_hashes & current_hashes:
        raise EvalError("the eval shard normalized hashes do not extend its prior ledger")
    ledger_body = _ledger_body(prior_hashes | current_hashes)
    if len(ledger_body) != end * 32:
        raise EvalError("the eval shard normalized-hash ledger count differs")
    validation = {
        "schema_version": "milk.eval-validation-shard.v3",
        "eval_uuid": revision["eval_uuid"],
        "revision_sha256": summary.digest(revision),
        "split": split,
        "start": start,
        "end": end,
        "accepted": True,
        "case_count": len(cases),
        "cases_sha256": summary.digest(cases_body),
        "cases_content_sha256": summary.digest(cases_plain),
        "normalized_hashes": hashes,
        "normalized_ledger_sha256": summary.digest(ledger_body),
        "verdicts": verdicts["verdicts"],
    }
    store.create_same(keys["cases"], cases_body)
    store.create_same(keys["ledger"], ledger_body)
    store.create_same(keys["validation"], summary.canonical(validation))
    shard = _read_shard(store, revision, split, start, end)
    if shard is None:
        raise EvalError("eval shard write did not complete")
    return shard, list(keys.values())


def _attempt(store, revision: dict, context: dict, shard_plan: dict, summary_sha256: str, eval_prompt: str, attempt: int, rejection: dict | None, accepted_hashes: set[str], job_prefix: str) -> tuple[list[dict], list[dict], dict, dict, int, list[str]]:
    validation_key = job_prefix + f"validation-local-v1-{attempt}.json"
    revision_sha256 = summary.digest(revision)
    case_ids = [case["case_id"] for case in shard_plan["cases"]]
    oracle_by_id = {case["case_id"]: case["oracle"] for case in shard_plan["cases"]}
    conversations_by_key = {source["source_key"]: source for source in context["conversations"]}
    rejected_by_id = None
    prior_by_id = None
    if rejection is not None:
        rejected_by_id = {item["case_id"]: item for item in rejection.get("rejected_verdicts", []) if isinstance(item, dict) and isinstance(item.get("case_id"), str)}
        prior = rejection.get("prior_generation")
        prior_by_id = {item["case_id"]: item for item in prior.get("cases", []) if isinstance(item, dict) and isinstance(item.get("case_id"), str)} if isinstance(prior, dict) else {}
        if set(rejected_by_id) != set(case_ids) or set(prior_by_id) != set(case_ids):
            raise EvalError("eval repair input differs from its requested cases")

    inference_calls = 0
    artifacts: list[str] = []
    generation_batches = []
    generator_inputs = []
    generated_by_id = {}
    model_batches = []
    for oracle in ("exact", "reference", "schema"):
        oracle_cases = [case for case in shard_plan["cases"] if case["oracle"] == oracle]
        model_batches.extend(
            oracle_cases[offset : offset + GENERATOR_BATCH_CASES]
            for offset in range(0, len(oracle_cases), GENERATOR_BATCH_CASES)
        )
    for batch_index, planned_cases in enumerate(model_batches):
        batch_plan = {**shard_plan, "cases": planned_cases}
        batch_case_ids = [case["case_id"] for case in planned_cases]
        source_bindings = []
        for case in planned_cases:
            binding = {
                **{
                    key: case[key]
                    for key in (
                        "case_id", "order", "split", "selection", "tail_reason", "operation", "source_operation", "oracle",
                        "source_example_index", "source_example_count",
                        "source_key", "source_object_sha256", "request_sha256", "response_sha256", "content_sha256",
                    )
                },
            }
            if case["oracle"] == "schema":
                binding["schema_kind"] = shard_plan["schema_kind"]
            source_bindings.append(binding)
        source_keys = list(dict.fromkeys(case["source_key"] for case in planned_cases))
        try:
            distribution_context = [conversations_by_key[key] for key in source_keys]
        except KeyError as error:
            raise EvalError("eval generation source is absent from its revision context") from error
        prepared = {
            "schema_version": "milk.eval-input.v4",
            "eval_uuid": revision["eval_uuid"],
            "ordinal_range": {"split": shard_plan["split"], "start": shard_plan["start"], "end": shard_plan["end"]},
            "model_batch": {"index": batch_index, "case_ids": batch_case_ids},
            "summary_checkpoint": context["summary_checkpoint"],
            "distribution_context": distribution_context,
            "source_bindings": source_bindings,
        }
        if rejected_by_id is not None and prior_by_id is not None:
            prepared["repair"] = {
                "attempt": rejection.get("attempt"),
                "rejected_verdicts": [rejected_by_id[case_id] for case_id in batch_case_ids],
                "prior_generation": {
                    "schema_version": "milk.eval-generation.v3",
                    "cases": [prior_by_id[case_id] for case_id in batch_case_ids],
                },
            }
        generator_input_sha256 = summary.digest(prepared)
        generation_key = job_prefix + f"generation-v6-{attempt}-batch-{batch_index}.json"
        try:
            stored, generation_body = _object(store, generation_key)
            if (
                stored.get("schema_version") != "milk.eval-generation-batch-receipt.v6"
                or stored.get("eval_uuid") != revision["eval_uuid"]
                or stored.get("revision_sha256") != revision_sha256
                or stored.get("attempt") != attempt
                or stored.get("batch_index") != batch_index
                or stored.get("case_ids") != batch_case_ids
                or stored.get("input_sha256") != generator_input_sha256
            ):
                raise EvalError("stored eval generation batch receipt differs")
            batch_generation = _generation_contract(stored.get("generation"), batch_plan, stored=True)
            _provider_receipt(stored.get("receipt"), "eval", "EVAL", prepared, batch_generation)
        except FileNotFoundError:
            batch_generation, receipt = semantic.call(
                "eval",
                "EVAL",
                eval_prompt,
                prepared,
                _generation_schema(len(planned_cases), planned_cases[0]["oracle"], shard_plan["schema_kind"]),
                lambda value, expected=batch_plan: _generation_contract(value, expected),
            )
            inference_calls += receipt["inference_calls"]
            generation_body = summary.canonical({
                "schema_version": "milk.eval-generation-batch-receipt.v6",
                "eval_uuid": revision["eval_uuid"],
                "revision_sha256": revision_sha256,
                "attempt": attempt,
                "batch_index": batch_index,
                "case_ids": batch_case_ids,
                "input_sha256": generator_input_sha256,
                "receipt": receipt,
                "generation": batch_generation,
            })
            store.create_same(generation_key, generation_body)
        generator_inputs.append({"batch_index": batch_index, "case_ids": batch_case_ids, "input_sha256": generator_input_sha256})
        generation_batches.append({"key": generation_key, "sha256": summary.digest(generation_body)})
        generated_by_id.update((case["case_id"], case) for case in batch_generation["cases"])
        artifacts.append(generation_key)
    generated_cases = [generated_by_id[case["case_id"]] for case in shard_plan["cases"]]
    generation = _generation_contract({"schema_version": "milk.eval-generation.v3", "cases": generated_cases}, shard_plan, stored=True)
    generator_input_sha256 = summary.digest({
        "schema_version": "milk.eval-generation-inputs.v2",
        "generator_batch_cases": GENERATOR_BATCH_CASES,
        "batches": generator_inputs,
    })
    cases, hashes, local_rejections = _cases(generation, shard_plan, context, summary_sha256, accepted_hashes)
    candidate_ids = [case["case_id"] for case in cases]
    verdicts = _verdict_contract({
        "schema_version": VERDICT_SCHEMA,
        "verdicts": [
            {"case_id": case["case_id"], "accepted": True, "reason": "accepted", "guidance": ""}
            for case in cases
        ],
    }, cases)
    try:
        validation, unused_body = _object(store, validation_key)
        if (
            validation.get("schema_version") != "milk.eval-attempt-validation.v9"
            or validation.get("eval_uuid") != revision["eval_uuid"]
            or validation.get("revision_sha256") != revision_sha256
            or validation.get("attempt") != attempt
            or validation.get("generator_scheme") != "fixed-ordered-batches.v1"
            or validation.get("generator_batch_cases") != GENERATOR_BATCH_CASES
            or validation.get("generator_batches") != generation_batches
            or validation.get("validation_scheme") != "deterministic-local.v1"
            or validation.get("case_ids") != case_ids
            or validation.get("candidate_case_ids") != candidate_ids
            or validation.get("generator_input_sha256") != generator_input_sha256
            or validation.get("local_rejections") != local_rejections
        ):
            raise EvalError("stored eval attempt validation differs")
        stored_verdicts = _verdict_contract(validation.get("verdicts"), cases)
        if stored_verdicts != verdicts:
            raise EvalError("stored eval attempt validation differs")
    except FileNotFoundError:
        validation = {
            "schema_version": "milk.eval-attempt-validation.v9",
            "eval_uuid": revision["eval_uuid"],
            "revision_sha256": revision_sha256,
            "attempt": attempt,
            "generator_scheme": "fixed-ordered-batches.v1",
            "generator_batch_cases": GENERATOR_BATCH_CASES,
            "generator_batches": generation_batches,
            "validation_scheme": "deterministic-local.v1",
            "case_ids": case_ids,
            "candidate_case_ids": candidate_ids,
            "generator_input_sha256": generator_input_sha256,
            "local_rejections": local_rejections,
            "verdicts": verdicts,
        }
        store.create_same(validation_key, summary.canonical(validation))
    artifacts.append(validation_key)
    model_verdicts = verdicts["verdicts"]
    rejected_by_id = {item["case_id"]: item for item in local_rejections}
    rejected = [rejected_by_id[case_id] for case_id in case_ids if case_id in rejected_by_id]
    accepted_ids = {item["case_id"] for item in model_verdicts if item["accepted"]}
    accepted_cases = [case for case in cases if case["case_id"] in accepted_ids]
    accepted_case_ids = {case["case_id"] for case in accepted_cases}
    accepted_case_hashes = [item for item in hashes if item["case_id"] in accepted_case_ids]
    accepted_verdicts = {"schema_version": VERDICT_SCHEMA, "verdicts": [item for item in model_verdicts if item["case_id"] in accepted_case_ids]}
    if accepted_case_ids | set(rejected_by_id) != set(case_ids) or accepted_case_ids & set(rejected_by_id):
        raise EvalError("eval repair partition differs from its requested cases")
    rejected_ids = set(rejected_by_id)
    repair = {
        "attempt": attempt,
        "rejected_verdicts": rejected,
        "prior_generation": {
            "schema_version": generation["schema_version"],
            "cases": [_wire_case(case, oracle_by_id[case["case_id"]]) for case in generation["cases"] if case["case_id"] in rejected_ids],
        },
    }
    return accepted_cases, accepted_case_hashes, accepted_verdicts, repair, inference_calls, artifacts


def _collect_attempts(store, revision: dict, context: dict, shard_plan: dict, summary_sha256: str, eval_prompt: str, pending: list[dict], rejection: dict | None, base_hashes: set[str], job_prefix: str, accepted=None, max_attempts: int = MAX_GENERATION_ATTEMPTS) -> tuple:
    initial_cases, initial_hashes, initial_verdicts = accepted or ([], [], {"verdicts": []})
    cases_by_id = {case["case_id"]: case for case in initial_cases}
    hashes_by_id = {item["case_id"]: item for item in initial_hashes}
    verdicts_by_id = {item["case_id"]: item for item in initial_verdicts["verdicts"]}
    inference_calls = 0
    artifacts: list[str] = []
    attempts = 0
    while pending and attempts < max_attempts:
        attempt = attempts
        attempts += 1
        attempt_plan = {**shard_plan, "cases": pending}
        cases, hashes, verdicts, rejection, calls, attempt_artifacts = _attempt(
            store,
            revision,
            context,
            attempt_plan,
            summary_sha256,
            eval_prompt,
            attempt,
            rejection,
            base_hashes | {item["input_sha256"] for item in hashes_by_id.values()},
            job_prefix,
        )
        inference_calls += calls
        artifacts.extend(attempt_artifacts)
        cases_by_id.update((case["case_id"], case) for case in cases)
        hashes_by_id.update((item["case_id"], item) for item in hashes)
        verdicts_by_id.update((item["case_id"], item) for item in verdicts["verdicts"])
        rejected_ids = {item["case_id"] for item in rejection["rejected_verdicts"]}
        pending = [case for case in pending if case["case_id"] in rejected_ids]
        if not pending or calls:
            break
    return pending, cases_by_id, hashes_by_id, verdicts_by_id, rejection, attempts, inference_calls, artifacts


def _prepare_range(store, revision: dict, context: dict, shard_plan: dict, summary_sha256: str, eval_prompt: str, job_prefix: str) -> tuple:
    case_ids = [case["case_id"] for case in shard_plan["cases"]]
    pending, cases_by_id, hashes_by_id, verdicts_by_id, rejection, attempts, calls, artifacts = _collect_attempts(
        store, revision, context, shard_plan, summary_sha256, eval_prompt,
        shard_plan["cases"], None, set(), job_prefix,
    )
    if pending:
        if not calls:
            raise EvalError("eval generation exhausted its bounded repairs")
        return None, rejection, attempts, calls, artifacts, False
    prepared = (
        [cases_by_id[case_id] for case_id in case_ids],
        [hashes_by_id[case_id] for case_id in case_ids],
        {"schema_version": VERDICT_SCHEMA, "verdicts": [verdicts_by_id[case_id] for case_id in case_ids]},
    )
    receipt = {
        "schema_version": "milk.eval-prepared-shard.v1",
        "eval_uuid": revision["eval_uuid"],
        "revision_sha256": summary.digest(revision),
        "split": shard_plan["split"],
        "start": shard_plan["start"],
        "end": shard_plan["end"],
        "case_ids": case_ids,
        "attempt_count": attempts,
        "cases_sha256": summary.digest(prepared[0]),
        "normalized_hashes_sha256": summary.digest(prepared[1]),
        "verdicts_sha256": summary.digest(prepared[2]),
        "attempt_artifacts": _artifacts(store, artifacts),
    }
    prepared_key = job_prefix + "prepared.json"
    created = store.create_same(prepared_key, summary.canonical(receipt)).created
    return prepared, None, attempts, calls, [*artifacts, prepared_key], created


def _ranges(plan: dict, target: int, shard_cases: int):
    start = 0
    while start < target:
        split, end = eval_plan.range_for(plan, start, target, shard_cases)
        yield split, start, end
        start = end


def _prefix_quality(counter: Counter) -> dict:
    total = sum(counter.values())
    repeated = [count for count in counter.values() if count > 1]
    maximum = max(counter.values(), default=0)
    return {
        "eligible_case_count": total,
        "repeated_prefix_count": len(repeated),
        "cases_in_repeated_prefixes": sum(repeated),
        "max_case_count": maximum,
        "max_basis_points": maximum * 10_000 // total if total else 0,
    }


def _quality_summary(store, shards: list[dict], exact_unique_input_count: int) -> dict:
    sources, operations, oracles = Counter(), Counter(), Counter()
    prefixes = {8: Counter(), 24: Counter()}
    input_bytes = []
    mechanics_boilerplate = 0
    markers = (
        "source example index", "source example count", "hidden deterministic creative seed",
        "source binding", "synthetic eval", "synthetic sample", "mechanics sample",
        "milk job read", "milk job commit",
    )
    for shard in shards:
        plain = summary._zstd(store.get(shard["cases_key"]).body, True)
        for line in plain.splitlines():
            case = json.loads(line)
            text = case["input"]
            normalized = _normalized(text)
            tokens = ["#" if token.isdigit() else token for token in normalized.split()]
            sources[case["source_content_sha256"]] += 1
            operations[case["operation"]] += 1
            oracles[case["oracle"]] += 1
            input_bytes.append(len(text.encode()))
            for size, counter in prefixes.items():
                if len(tokens) >= size:
                    counter[summary.digest(" ".join(tokens[:size]).encode())] += 1
            searchable = normalized
            if isinstance(case.get("expected"), str):
                searchable += " " + _normalized(case["expected"])
            mechanics_boilerplate += any(marker in searchable for marker in markers)
    ordered_sizes = sorted(input_bytes)

    def percentile(percent: int) -> int:
        return ordered_sizes[max(0, (len(ordered_sizes) * percent + 99) // 100 - 1)]

    return {
        "schema_version": "milk.eval-quality.v1",
        "case_count": len(input_bytes),
        "exact_unique_input_count": exact_unique_input_count,
        "source_count": len(sources),
        "source_case_counts": [
            {"source_content_sha256": source, "case_count": count}
            for source, count in sorted(sources.items())
        ],
        "operation_counts": dict(sorted(operations.items())),
        "oracle_counts": dict(sorted(oracles.items())),
        "input_bytes": {
            "min": ordered_sizes[0], "p50": percentile(50), "p95": percentile(95), "max": ordered_sizes[-1],
        },
        "template_prefixes": {str(size): _prefix_quality(counter) for size, counter in prefixes.items()},
        "mechanics_boilerplate_case_count": mechanics_boilerplate,
    }


def _finalize(store, settings, revision: dict, plan: dict) -> tuple[dict, list[str]]:
    target = revision["identity"]["target_case_count"]
    shard_cases = revision["identity"]["shard_case_count"]
    shards, normalized = [], set()
    for split, start, end in _ranges(plan, target, shard_cases):
        shard = _read_shard(store, revision, split, start, end)
        if shard is None:
            raise EvalError("eval manifest cannot skip a shard")
        validation, unused_body = _object(store, shard["validation_key"])
        for item in validation["normalized_hashes"]:
            value = item.get("input_sha256") if isinstance(item, dict) else None
            if not isinstance(value, str) or value in normalized:
                raise EvalError("eval manifest contains duplicate normalized inputs")
            normalized.add(value)
        shards.append(shard)
    if sum(shard["count"] for shard in shards) != target or len(normalized) != target:
        raise EvalError("eval manifest does not contain the exact target")
    quality = _quality_summary(store, shards, len(normalized))
    ratio = revision["identity"]["cases_per_conversation"]
    if quality["source_count"] != revision["identity"]["generation_source_count"] or any(
        item["case_count"] != ratio for item in quality["source_case_counts"]
    ):
        raise EvalError("eval manifest does not contain the exact per-source case count")
    eval_prefix = revision["context_key"].removesuffix("context.json.zst")
    cases_content_sha256 = summary.digest({"schema_version": "milk.eval-content.v3", "shards": [shard["cases_content_sha256"] for shard in shards]})
    normalized_sha256 = summary.digest({"schema_version": "milk.eval-normalized-set.v3", "hashes": sorted(normalized)})
    manifest = {
        "schema_version": "milk.eval-manifest.v3",
        "code_version": CODE_VERSION,
        "eval_uuid": revision["eval_uuid"],
        "revision_key": eval_prefix + "revision.json",
        "revision_sha256": summary.digest(revision),
        "context_key": revision["context_key"],
        "context_sha256": revision["context_sha256"],
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "summary_sha256": revision["identity"]["summary_sha256"],
        "readiness_sha256": revision["identity"]["readiness_sha256"],
        "readiness_pointer_sha256": revision["identity"]["readiness_pointer_sha256"],
        "target_case_count": target,
        "target_split_counts": revision["identity"]["target_split_counts"],
        "case_count": target,
        "shard_case_count": shard_cases,
        "shard_count": len(shards),
        "cases_content_sha256": cases_content_sha256,
        "normalized_hashes_sha256": normalized_sha256,
        "quality": quality,
        "shards": shards,
    }
    manifest_key = eval_prefix + "manifest.json"
    manifest_body = summary.canonical(manifest)
    store.create_same(manifest_key, manifest_body)
    pointer = {
        "schema_version": "milk.pointer.v2",
        "kind": "eval",
        "scope_id": settings.scope_id,
        "uuid": revision["eval_uuid"],
        "key": manifest_key,
        "manifest_key": manifest_key,
        "sha256": summary.digest(manifest_body),
        "content_sha256": cases_content_sha256,
        "revision_key": manifest["revision_key"],
        "revision_sha256": manifest["revision_sha256"],
        "summary_sha256": manifest["summary_sha256"],
        "readiness_sha256": manifest["readiness_sha256"],
        "readiness_pointer_sha256": manifest["readiness_pointer_sha256"],
        "case_count": target,
        "shard_count": len(shards),
    }
    pointer_key = settings.scope_prefix + "e/current.json"
    summary._advance(store, pointer_key, pointer)
    status_key = _complete_status(store, settings, pointer)
    return pointer, [manifest_key, pointer_key, status_key]


def reconcile(store, settings, runtime) -> dict:
    summary_pointer, summary_value, readiness_pointer, readiness, readiness_pointer_sha256 = _current(store, settings)
    if readiness.get("ready") is not True:
        return {"state": "idle", "identity": readiness_pointer["sha256"], "artifacts": [], "inference_calls": 0, "provider_calls": 0, "next": "summary", "details": {"reason": "readiness_not_met"}}
    plan = _plan(store, settings, summary_value, readiness)
    try:
        target, shard_cases = eval_plan.generation_counts(plan)
        selected = eval_plan.precompute_range(plan, target, shard_cases)
    except eval_plan.PlanError as error:
        raise EvalError(str(error)) from error
    root = Path(__file__).resolve().parents[1]
    eval_prompt = (root / runtime.job("eval").system_prompt).read_text()
    identity = _revision_identity(settings, runtime, summary_pointer, readiness_pointer, readiness_pointer_sha256, plan, eval_prompt, target, shard_cases)
    if selected is None and current_matches(store, settings, target, shard_cases, summary.digest(identity)):
        pointer, pointer_body = _object(store, settings.scope_prefix + "e/current.json")
        status_key = _complete_status(store, settings, pointer)
        return {"state": "idle", "identity": pointer["uuid"], "artifacts": [{"key": settings.scope_prefix + "e/current.json", "sha256": summary.digest(pointer_body)}, *_artifacts(store, [status_key])], "inference_calls": 0, "provider_calls": 0, "next": "dataset", "details": {"eval_uuid": pointer["uuid"], "case_count": pointer["case_count"]}}

    revision, context, base_artifacts = _revision(store, settings, summary_value, plan, identity)
    if selected is not None:
        shard_index, split, start, end = selected
        shard_plan = eval_plan.shard(plan, revision["eval_uuid"], target, start, end)
        job_prefix = settings.scope_prefix + f"j/eval/{revision['revision_id']}/{split}/{_range_name(start, end)}/"
        prepared, rejection, attempts, calls, artifacts, created = _prepare_range(
            store, revision, context, shard_plan, summary_pointer["sha256"], eval_prompt, job_prefix,
        )
        details = {
            "eval_uuid": revision["eval_uuid"],
            "shard_index": shard_index,
            "ordinal_range": {"split": split, "start": start, "end": end},
            "prepared": prepared is not None,
            "attempts": attempts,
        }
        if rejection is not None:
            details["remaining_case_count"] = len(rejection["rejected_verdicts"])
            details["remaining_reasons"] = dict(sorted(Counter(item["reason"] for item in rejection["rejected_verdicts"]).items()))
        return {"state": "progressed" if calls or created else "idle", "identity": revision["revision_id"], "artifacts": _artifacts(store, base_artifacts + artifacts), "inference_calls": calls, "provider_calls": 0, "next": "eval", "details": details}

    completed, unused_status_key = _completed(store, settings, revision)
    if completed == target:
        pointer, final_artifacts = _finalize(store, settings, revision, plan)
        return {"state": "progressed", "identity": revision["revision_id"], "artifacts": _artifacts(store, base_artifacts + final_artifacts), "inference_calls": 0, "provider_calls": 0, "next": "dataset", "details": {"eval_uuid": pointer["uuid"], "case_count": target, "shard_count": pointer["shard_count"]}}

    recovered = []
    last_shard = None
    while completed < target:
        split, end = eval_plan.range_for(plan, completed, target, shard_cases)
        existing = _read_shard(store, revision, split, completed, end)
        if existing is None:
            break
        completed = end
        last_shard = existing
        recovered.extend((existing["cases_key"], existing["validation_key"]))
    if recovered:
        status_key = _advance_progress(store, settings, revision, completed, last_shard)
        base_artifacts.extend((status_key, *recovered))
    if completed == target:
        pointer, final_artifacts = _finalize(store, settings, revision, plan)
        return {"state": "progressed", "identity": revision["revision_id"], "artifacts": _artifacts(store, base_artifacts + final_artifacts), "inference_calls": 0, "provider_calls": 0, "next": "dataset", "details": {"eval_uuid": pointer["uuid"], "case_count": target, "shard_count": pointer["shard_count"]}}

    split, end = eval_plan.range_for(plan, completed, target, shard_cases)

    shard_plan = eval_plan.shard(plan, revision["eval_uuid"], target, completed, end)
    eval_prefix = revision["context_key"].removesuffix("context.json.zst")
    job_prefix = settings.scope_prefix + f"j/eval/{revision['revision_id']}/{split}/{_range_name(completed, end)}/"
    result_key = job_prefix + "result.json"

    prepared, rejection, attempts, inference_calls, prepared_artifacts, unused_created = _prepare_range(
        store, revision, context, shard_plan, summary_pointer["sha256"], eval_prompt, job_prefix,
    )
    artifacts = base_artifacts + prepared_artifacts
    if prepared is None:
        details = {"eval_uuid": revision["eval_uuid"], "phase": "precompute", "prepared": False, "attempts": attempts, "remaining_case_count": len(rejection["rejected_verdicts"]), "completed_case_count": completed, "target_case_count": target}
        return {"state": "progressed", "identity": revision["revision_id"], "artifacts": _artifacts(store, artifacts), "inference_calls": inference_calls, "provider_calls": 0, "next": "eval", "details": details}

    accepted_cases, accepted_hashes, accepted_verdicts = prepared
    prior_hashes, unused_prior_ledger_body = _ledger(store, eval_prefix, completed)
    hash_by_id = {item["case_id"]: item for item in accepted_hashes}
    case_ids = [case["case_id"] for case in shard_plan["cases"]]
    oracle_by_id = {case["case_id"]: case["oracle"] for case in shard_plan["cases"]}
    duplicate_ids = [case_id for case_id in case_ids if hash_by_id[case_id]["input_sha256"] in prior_hashes]
    if duplicate_ids:
        duplicate_id_set = set(duplicate_ids)
        cases_by_id = {case["case_id"]: case for case in accepted_cases}
        verdicts_by_id = {item["case_id"]: item for item in accepted_verdicts["verdicts"]}
        retained_ids = [case_id for case_id in case_ids if case_id not in duplicate_id_set]
        retained = ([cases_by_id[case_id] for case_id in retained_ids], [hash_by_id[case_id] for case_id in retained_ids], {"schema_version": VERDICT_SCHEMA, "verdicts": [verdicts_by_id[case_id] for case_id in retained_ids]})
        rejection = {
            "attempt": -1,
            "rejected_verdicts": [
                {
                    "case_id": case_id,
                    "accepted": False,
                    "reason": "duplicate",
                    "guidance": "Change the task framing and several concrete details.",
                }
                for case_id in duplicate_ids
            ],
            "prior_generation": {"schema_version": "milk.eval-generation.v3", "cases": [_wire_case(cases_by_id[case_id], oracle_by_id[case_id]) for case_id in duplicate_ids]},
        }
        pending_plan = [case for case in shard_plan["cases"] if case["case_id"] in duplicate_id_set]
        pending, cases_by_id, hash_by_id, verdicts_by_id, rejection, reduce_attempts, calls, reduce_artifacts = _collect_attempts(
            store, revision, context, shard_plan, summary_pointer["sha256"], eval_prompt,
            pending_plan, rejection, prior_hashes, job_prefix + "reduce/", retained,
        )
        inference_calls += calls
        artifacts.extend(reduce_artifacts)
        if pending:
            if not calls:
                raise EvalError("eval duplicate reduction exhausted its bounded repairs")
            details = {"eval_uuid": revision["eval_uuid"], "phase": "reduce", "prepared": True, "repair_attempts": reduce_attempts, "remaining_case_count": len(pending), "completed_case_count": completed, "target_case_count": target}
            return {"state": "progressed", "identity": revision["revision_id"], "artifacts": _artifacts(store, artifacts), "inference_calls": inference_calls, "provider_calls": 0, "next": "eval", "details": details}
        accepted_cases = [cases_by_id[case_id] for case_id in case_ids]
        accepted_hashes = [hash_by_id[case_id] for case_id in case_ids]
        accepted_verdicts = {"schema_version": VERDICT_SCHEMA, "verdicts": [verdicts_by_id[case_id] for case_id in case_ids]}

    shard, shard_artifacts = _write_shard(store, revision, split, completed, end, accepted_cases, accepted_hashes, accepted_verdicts, prior_hashes)
    artifacts.extend(shard_artifacts)
    status_key = _advance_progress(store, settings, revision, end, shard)
    artifacts.append(status_key)
    next_job = "dataset" if end == target else "eval"
    result = {"schema_version": "milk.eval-shard-result.v3", "revision_id": revision["revision_id"], "split": split, "start": completed, "end": end, "state": "progressed", "artifact_keys": artifacts + [result_key], "details": {"eval_uuid": revision["eval_uuid"], "completed_case_count": end, "target_case_count": target}}
    store.create_same(result_key, summary.canonical(result))
    artifacts.append(result_key)
    if end == target:
        pointer, final_artifacts = _finalize(store, settings, revision, plan)
        artifacts.extend(final_artifacts)
        result["details"].update({"case_count": target, "shard_count": pointer["shard_count"]})
    else:
        result["details"]["next_range"] = [end, eval_plan.range_for(plan, end, target, shard_cases)[1]]
    return {"state": "progressed", "identity": revision["revision_id"], "artifacts": _artifacts(store, artifacts), "inference_calls": inference_calls, "provider_calls": 0, "next": next_job, "details": result["details"]}
