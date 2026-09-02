from __future__ import annotations

import json
import os
from pathlib import Path
import re
import uuid

from . import eval_plan, semantic, summary


CODE_VERSION = "milk.eval.v2"


class EvalError(ValueError):
    pass


class BusyError(RuntimeError):
    def __init__(self, identity: str):
        super().__init__("an incomplete eval intent already exists")
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


def current_matches(store, settings) -> bool:
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
    if summary.digest(store.get(pointer.get("key", "")).body) != pointer.get("sha256"):
        raise EvalError("current eval object digest differs")
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
    except eval_plan.PlanError as error:
        raise EvalError(str(error)) from error
    expected = {"policy": value["policy"], "counts": value["counts"], "missing": value["missing"]}
    if readiness.get("eval_plan") != expected or not value["ready"] or readiness.get("ready") is not True:
        raise EvalError("current readiness does not admit the deterministic eval plan")
    return value


def _prefix(value: str, maximum: int = 2048) -> str:
    return value.encode()[:maximum].decode("utf-8", "ignore")


def _prepared_sources(store, settings, plan: dict) -> list[dict]:
    sources = []
    for case in plan["cases"]:
        row = summary.parse_capture(store, settings, case["source_key"])
        if row["object_sha256"] != case["source_object_sha256"] or row["content_sha256"] != case["content_sha256"] or row["request_sha256"] != case["request_sha256"] or row["response_sha256"] != case["response_sha256"]:
            raise EvalError("planned capture identity differs")
        sources.append({
            "case_id": case["case_id"],
            "order": case["order"],
            "split": case["split"],
            "selection": case["selection"],
            "tail_reason": case["tail_reason"],
            "operation": case["operation"],
            "oracle": case["oracle"],
            "source_request_sha256": case["request_sha256"],
            "source_content_sha256": case["content_sha256"],
            "request_excerpt": _prefix(row["request_text"]),
            "response_excerpt": _prefix(row["response_text"]),
        })
    return sources


def _generation_schema(count: int) -> dict:
    case = {
        "type": "object",
        "properties": {
            "case_id": {"type": "string"},
            "input": {"type": "string", "minLength": 1, "maxLength": 8192},
            "expected": {"oneOf": [{"type": "string", "minLength": 1, "maxLength": 8192}, {"type": "object"}]},
        },
        "required": ["case_id", "input", "expected"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["milk.eval-generation.v2"]},
            "cases": {"type": "array", "items": case, "minItems": count, "maxItems": count},
        },
        "required": ["schema_version", "cases"],
        "additionalProperties": False,
    }


def _generation_contract(value: dict, plan: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {"schema_version", "cases"} or value.get("schema_version") != "milk.eval-generation.v2" or not isinstance(value.get("cases"), list):
        raise ValueError("eval generation has invalid fields")
    expected_ids = [case["case_id"] for case in plan["cases"]]
    if len(value["cases"]) != len(expected_ids):
        raise ValueError("eval generation has the wrong case count")
    checked = []
    for expected_id, generated in zip(expected_ids, value["cases"]):
        if not isinstance(generated, dict) or set(generated) != {"case_id", "input", "expected"} or generated.get("case_id") != expected_id:
            raise ValueError("eval generation changed case identity or order")
        text = generated.get("input")
        output = generated.get("expected")
        if not isinstance(text, str) or not 1 <= len(text.encode()) <= 8192 or any(ord(character) < 9 for character in text):
            raise ValueError("eval generation has an invalid input")
        oracle = plan["cases"][len(checked)]["oracle"]
        if oracle in {"exact", "reference"}:
            if not isinstance(output, str) or not 1 <= len(output.encode()) <= 8192:
                raise ValueError("eval generation has an invalid reference answer")
        elif not isinstance(output, dict) or not output or len(summary.canonical(output)) > 16 * 1024:
            raise ValueError("eval generation has an invalid schema oracle")
        checked.append({"case_id": expected_id, "input": text, "expected": output})
    return {"schema_version": "milk.eval-generation.v2", "cases": checked}


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _cases(generation: dict, plan: dict, sources: list[dict], summary_sha256: str) -> list[dict]:
    source_by_id = {source["case_id"]: source for source in sources}
    cases = []
    for planned, generated in zip(plan["cases"], generation["cases"]):
        source = source_by_id[planned["case_id"]]
        input_normalized = _normalized(generated["input"])
        expected = generated["expected"]
        if isinstance(expected, str):
            expected_normalized = _normalized(expected)
            if len(expected_normalized) >= 8 and expected_normalized in input_normalized:
                raise ValueError(f"{planned['case_id']} leaks its reference answer")
        if input_normalized and input_normalized in {_normalized(source["request_excerpt"]), _normalized(source["response_excerpt"])}:
            raise ValueError(f"{planned['case_id']} copies its source verbatim")
        cases.append({
            "schema_version": "milk.eval-case.v2",
            "case_id": planned["case_id"],
            "order": planned["order"],
            "split": planned["split"],
            "selection": planned["selection"],
            "tail_reason": planned["tail_reason"],
            "operation": planned["operation"],
            "oracle": planned["oracle"],
            "input": generated["input"],
            "expected": expected,
            "source_key": planned["source_key"],
            "source_object_sha256": planned["source_object_sha256"],
            "source_request_sha256": planned["request_sha256"],
            "source_content_sha256": planned["content_sha256"],
            "summary_sha256": summary_sha256,
        })
    tokens = [set(_normalized(case["input"]).split()) for case in cases]
    for right in range(len(tokens)):
        for left in range(right):
            union = tokens[left] | tokens[right]
            if union and len(tokens[left] & tokens[right]) * 10 > len(union) * 9:
                raise ValueError(f"{cases[left]['case_id']} and {cases[right]['case_id']} are near duplicates")
    return cases


VERDICTS = ("accepted", "incorrect", "unanswerable", "vacuous", "unsupported", "copied", "leaked", "duplicate")


def _verdict_schema(count: int) -> dict:
    item = {
        "type": "object",
        "properties": {"case_id": {"type": "string"}, "accepted": {"type": "boolean"}, "reason": {"type": "string", "enum": list(VERDICTS)}},
        "required": ["case_id", "accepted", "reason"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"schema_version": {"type": "string", "enum": ["milk.eval-verdicts.v2"]}, "verdicts": {"type": "array", "items": item, "minItems": count, "maxItems": count}},
        "required": ["schema_version", "verdicts"],
        "additionalProperties": False,
    }


def _verdict_contract(value: dict, cases: list[dict]) -> dict:
    if not isinstance(value, dict) or set(value) != {"schema_version", "verdicts"} or value.get("schema_version") != "milk.eval-verdicts.v2" or not isinstance(value.get("verdicts"), list):
        raise ValueError("eval validator has invalid fields")
    expected_ids = [case["case_id"] for case in cases]
    if len(value["verdicts"]) != len(expected_ids):
        raise ValueError("eval validator has the wrong verdict count")
    checked = []
    for expected_id, verdict in zip(expected_ids, value["verdicts"]):
        if not isinstance(verdict, dict) or set(verdict) != {"case_id", "accepted", "reason"} or verdict.get("case_id") != expected_id:
            raise ValueError("eval validator changed case identity or order")
        if type(verdict.get("accepted")) is not bool or verdict.get("reason") not in VERDICTS or verdict["accepted"] != (verdict["reason"] == "accepted"):
            raise ValueError("eval validator returned an invalid verdict")
        checked.append(verdict)
    return {"schema_version": "milk.eval-verdicts.v2", "verdicts": checked}


def _binding(prefix: str) -> dict:
    return {"base_url": os.environ.get(f"MILK_{prefix}_BASE_URL", ""), "model": os.environ.get(f"MILK_{prefix}_MODEL", ""), "api_mode": os.environ.get(f"MILK_{prefix}_API_MODE", "chat_completions"), "reasoning_effort": os.environ.get("MILK_REASONING_EFFORT", "")}


def _artifacts(store, keys: list[str]) -> list[dict]:
    return [{"key": key, "sha256": summary.digest(store.get(key).body)} for key in keys]


def _status(store, settings, pointer: dict) -> str:
    key = settings.scope_prefix + "status/current.json"
    try:
        value, unused_body = _object(store, key)
    except FileNotFoundError:
        value = {"schema_version": "milk.status.v2", "scope_id": settings.scope_id, "profile": settings.profile}
    if value.get("schema_version") != "milk.status.v2" or value.get("scope_id") != settings.scope_id or value.get("profile") != settings.profile:
        raise EvalError("current status identity differs")
    summary._advance(store, key, {**value, "eval": pointer, "next_action": "dataset"})
    return key


def reconcile(store, settings, runtime) -> dict:
    summary_pointer, summary_value, readiness_pointer, readiness, readiness_pointer_sha256 = _current(store, settings)
    if readiness.get("ready") is not True:
        return {"state": "idle", "identity": readiness_pointer["sha256"], "artifacts": [], "inference_calls": 0, "provider_calls": 0, "next": "summary", "details": {"reason": "readiness_not_met"}}
    if current_matches(store, settings):
        pointer, pointer_body = _object(store, settings.scope_prefix + "e/current.json")
        status_key = _status(store, settings, pointer)
        return {"state": "idle", "identity": pointer["uuid"], "artifacts": [{"key": settings.scope_prefix + "e/current.json", "sha256": summary.digest(pointer_body)}, *_artifacts(store, [status_key])], "inference_calls": 0, "provider_calls": 0, "next": "dataset", "details": {"eval_uuid": pointer["uuid"], "case_count": pointer["case_count"]}}

    plan = _plan(store, settings, summary_value, readiness)
    sources = _prepared_sources(store, settings, plan)
    root = Path(__file__).resolve().parents[1]
    eval_prompt = (root / runtime.job("eval").system_prompt).read_text()
    validator_prompt = (root / "prompts" / "eval-validator.md").read_text()
    identity = {
        "schema_version": "milk.eval-job-identity.v2",
        "code_version": CODE_VERSION,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "summary_sha256": summary_pointer["sha256"],
        "readiness_sha256": readiness_pointer["sha256"],
        "readiness_pointer_sha256": readiness_pointer_sha256,
        "config_digest": runtime.digest,
        "plan": {"policy": plan["policy"], "cases": [{key: case[key] for key in ("case_id", "order", "split", "selection", "tail_reason", "source_key", "source_object_sha256", "request_sha256", "response_sha256", "content_sha256", "label_key", "label_sha256", "operation", "oracle")} for case in plan["cases"]]},
        "eval_prompt_sha256": summary.digest(eval_prompt.encode()),
        "validator_prompt_sha256": summary.digest(validator_prompt.encode()),
        "eval_binding_sha256": summary.digest(_binding("EVAL")),
        "validator_binding_sha256": summary.digest(_binding("VALIDATOR")),
    }
    job_id = summary.digest(identity)
    prefix = settings.scope_prefix + f"j/eval/{job_id}/"
    intent_key = prefix + "intent.json"
    result_key = prefix + "result.json"
    try:
        prior, unused_body = _object(store, result_key)
        if prior.get("schema_version") != "milk.eval-job-result.v2" or prior.get("job_id") != job_id:
            raise EvalError("stored eval result is invalid")
        return {"state": prior["state"], "identity": job_id, "artifacts": _artifacts(store, prior.get("artifact_keys", [])), "inference_calls": 0, "provider_calls": 0, "next": prior.get("next"), "details": prior.get("details", {})}
    except FileNotFoundError:
        pass
    if not store.create_same(intent_key, summary.canonical({**identity, "job_id": job_id})).created:
        raise BusyError(job_id)

    prepared = {"schema_version": "milk.eval-input.v2", "summary_sha256": summary_pointer["sha256"], "readiness_sha256": readiness_pointer["sha256"], "policy": plan["policy"], "sources": sources}
    artifacts = [intent_key]
    inference_calls = 0
    rejection = None
    accepted_cases = None
    accepted_verdicts = None
    for attempt in range(2):
        generator_input = prepared if attempt == 0 else {**prepared, "repair": rejection}
        generation, generation_receipt = semantic.call("eval", "EVAL", eval_prompt, generator_input, _generation_schema(len(plan["cases"])), lambda value: _generation_contract(value, plan))
        inference_calls += generation_receipt["inference_calls"]
        generation_key = prefix + f"generation-{attempt}.json"
        store.create_same(generation_key, summary.canonical({"schema_version": "milk.eval-generation-receipt.v2", "job_id": job_id, "attempt": attempt, "receipt": generation_receipt, "generation": generation}))
        artifacts.append(generation_key)
        local_error = None
        try:
            cases = _cases(generation, plan, sources, summary_pointer["sha256"])
        except ValueError as error:
            local_error = str(error)
            cases = []
        verdicts = None
        validator_receipt = None
        if local_error is None:
            validator_input = {"schema_version": "milk.eval-validation-input.v2", "sources": sources, "cases": cases}
            verdicts, validator_receipt = semantic.call("eval-validator", "VALIDATOR", validator_prompt, validator_input, _verdict_schema(len(cases)), lambda value: _verdict_contract(value, cases))
            inference_calls += validator_receipt["inference_calls"]
        rejected = [] if verdicts is None else [verdict for verdict in verdicts["verdicts"] if not verdict["accepted"]]
        validation = {"schema_version": "milk.eval-attempt-validation.v2", "job_id": job_id, "attempt": attempt, "local_accepted": local_error is None, "local_error": local_error, "validator_receipt": validator_receipt, "verdicts": verdicts, "accepted": local_error is None and not rejected}
        validation_key = prefix + f"validation-{attempt}.json"
        store.create_same(validation_key, summary.canonical(validation))
        artifacts.append(validation_key)
        if validation["accepted"]:
            accepted_cases, accepted_verdicts = cases, verdicts
            break
        rejection = {"attempt": attempt, "local_error": local_error, "rejected_verdicts": rejected, "prior_generation": generation}

    if accepted_cases is None or accepted_verdicts is None:
        result = {"schema_version": "milk.eval-job-result.v2", "job_id": job_id, "state": "failed", "next": "eval", "artifact_keys": artifacts + [result_key], "details": {"reason": "eval_validation_failed", "attempts": 2}}
        store.create_same(result_key, summary.canonical(result))
        return {"state": "failed", "identity": job_id, "artifacts": _artifacts(store, result["artifact_keys"]), "inference_calls": inference_calls, "provider_calls": 0, "next": "eval", "details": result["details"]}

    eval_plain = b"".join(summary.canonical(case) for case in accepted_cases)
    eval_body = summary._zstd(eval_plain, False)
    eval_content_sha256 = summary.digest(eval_plain)
    eval_object_sha256 = summary.digest(eval_body)
    eval_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:eval:" + summary.digest({"job_id": job_id, "eval_content_sha256": eval_content_sha256})))
    eval_prefix = settings.scope_prefix + f"e/{eval_uuid}/"
    source = {
        "schema_version": "milk.eval-source.v2",
        "code_version": CODE_VERSION,
        "eval_uuid": eval_uuid,
        "job_id": job_id,
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "summary_key": summary_pointer["key"],
        "summary_sha256": summary_pointer["sha256"],
        "readiness_key": readiness_pointer["key"],
        "readiness_sha256": readiness_pointer["sha256"],
        "readiness_pointer_sha256": readiness_pointer_sha256,
        "config_digest": runtime.digest,
        "policy": plan["policy"],
        "cases": [
            {
                **{key: case[key] for key in ("case_id", "order", "split", "selection", "tail_reason", "operation", "oracle", "source_key", "source_object_sha256", "source_request_sha256", "source_content_sha256")},
                "source_response_sha256": planned["response_sha256"],
                "label_key": planned["label_key"],
                "label_sha256": planned["label_sha256"],
            }
            for case, planned in zip(accepted_cases, plan["cases"])
        ],
    }
    source_body = summary._zstd(summary.canonical(source), False)
    validation = {"schema_version": "milk.eval-validation.v2", "eval_uuid": eval_uuid, "job_id": job_id, "accepted": True, "case_count": len(accepted_cases), "eval_content_sha256": eval_content_sha256, "eval_object_sha256": eval_object_sha256, "verdicts": accepted_verdicts["verdicts"]}
    source_key = eval_prefix + "source.json.zst"
    eval_key = eval_prefix + "eval.jsonl.zst"
    validation_key = eval_prefix + "validation.json"
    store.create_same(source_key, source_body)
    store.create_same(eval_key, eval_body)
    store.create_same(validation_key, summary.canonical(validation))
    pointer = {
        "schema_version": "milk.pointer.v2",
        "kind": "eval",
        "scope_id": settings.scope_id,
        "uuid": eval_uuid,
        "key": eval_key,
        "sha256": eval_object_sha256,
        "content_sha256": eval_content_sha256,
        "source_key": source_key,
        "source_sha256": summary.digest(source_body),
        "validation_key": validation_key,
        "validation_sha256": summary.digest(validation),
        "summary_sha256": summary_pointer["sha256"],
        "readiness_sha256": readiness_pointer["sha256"],
        "readiness_pointer_sha256": readiness_pointer_sha256,
        "case_count": len(accepted_cases),
    }
    pointer_key = settings.scope_prefix + "e/current.json"
    summary._advance(store, pointer_key, pointer)
    status_key = _status(store, settings, pointer)
    artifacts.extend((source_key, eval_key, validation_key, pointer_key, status_key))
    result = {"schema_version": "milk.eval-job-result.v2", "job_id": job_id, "state": "progressed", "next": "dataset", "artifact_keys": artifacts + [result_key], "details": {"eval_uuid": eval_uuid, "case_count": len(accepted_cases)}}
    store.create_same(result_key, summary.canonical(result))
    return {"state": "progressed", "identity": job_id, "artifacts": _artifacts(store, result["artifact_keys"]), "inference_calls": inference_calls, "provider_calls": 0, "next": "dataset", "details": result["details"]}
