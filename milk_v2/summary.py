from __future__ import annotations

from collections import Counter
import base64
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.parse
import tempfile
import time
import uuid

from . import eval_plan


CODE_VERSION = "milk.summary.v3"
TAXONOMY_VERSION = "milk.semantic-taxonomy.v2"
OPERATIONS = ("answer", "summarize", "extract", "classify", "transform", "generate", "code", "plan_or_tool_use", "conversation", "other")
DOMAINS = ("general", "software", "math_science", "business", "legal", "finance", "health", "creative", "other")
CAPABILITIES = ("knowledge", "reasoning", "instruction_following", "structured_output", "tool_use", "multimodal")
ORACLES = ("exact", "schema", "executable", "reference", "pairwise_judge", "human")
SENTIMENTS = ("positive", "neutral", "negative", "mixed", "unknown")
OUTCOMES = ("success", "refusal", "partial", "upstream_failure", "malformed", "unknown")
COMPLEXITIES = ("low", "medium", "high", "unknown")
SAFETY = ("benign", "sensitive", "unsafe", "unknown")
SUMMARY_BATCH_BYTES = 64 * 1024
UTC_RFC3339 = re.compile(
    r"(?P<seconds>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]{1,9}))?(?:Z|\+00:00)\Z"
)


class SummaryError(ValueError):
    pass


class ProviderError(RuntimeError):
    def __init__(self, message: str, inference_calls: int = 0):
        super().__init__(message)
        self.inference_calls = inference_calls


class BusyError(RuntimeError):
    def __init__(self, identity: str):
        super().__init__("another process owns this summary job")
        self.identity = identity


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def thresholds(profile: str) -> tuple[int, ...]:
    raw = os.environ.get("MILK_SUMMARY_THRESHOLDS", "1" if profile == "mechanics" else "100,1000,10000,100000")
    try:
        values = tuple(int(item) for item in raw.split(","))
    except ValueError as error:
        raise SummaryError("MILK_SUMMARY_THRESHOLDS must be comma-separated integers") from error
    if not values or any(value < 1 for value in values) or tuple(sorted(set(values))) != values:
        raise SummaryError("MILK_SUMMARY_THRESHOLDS must be strictly increasing positive integers")
    return values


def _integer_environment(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise SummaryError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise SummaryError(f"{name} must be in {minimum}..{maximum}")
    return value


def _json(raw: bytes, name: str):
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SummaryError(f"{name} is not valid JSON") from error


def _zstd(raw: bytes, decompress: bool) -> bytes:
    executable = shutil.which("zstd")
    if executable is None:
        raise SummaryError("zstd is required to process Milk capture objects")
    arguments = [executable, "-q", "--stdout"]
    arguments.insert(2, "-d" if decompress else "-3")
    process = subprocess.run(arguments, input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    if process.returncode != 0:
        raise SummaryError("zstd could not process a Milk object")
    if len(process.stdout) > 64 * 1024 * 1024:
        raise SummaryError("decompressed Milk object is oversized")
    return process.stdout


def _utc(value, name: str) -> dt.datetime:
    match = UTC_RFC3339.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise SummaryError(f"{name} must be a UTC timestamp")
    normalized = match.group("seconds")
    fraction = match.group("fraction")
    if fraction is not None:
        normalized += "." + fraction[:6].ljust(6, "0")
    try:
        parsed = dt.datetime.fromisoformat(normalized + "+00:00")
    except ValueError as error:
        raise SummaryError(f"{name} must be a UTC timestamp") from error
    return parsed


def _decode_side(side, name: str) -> bytes:
    if not isinstance(side, dict):
        raise SummaryError(f"capture {name} must be an object")
    encoded = side.get("body_base64")
    if not isinstance(encoded, str):
        raise SummaryError(f"capture {name} has no body")
    try:
        body = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise SummaryError(f"capture {name} body is not base64") from error
    if side.get("byte_len") != len(body) or side.get("sha256") != digest(body):
        raise SummaryError(f"capture {name} body identity differs")
    return body


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _texts(value) -> list[str]:
    output = []
    if isinstance(value, dict):
        for key in ("instructions", "input"):
            item = value.get(key)
            if isinstance(item, str) and item:
                output.append(item)
    for node in _walk(value):
        for key in ("content", "text", "output_text", "refusal"):
            item = node.get(key)
            if isinstance(item, str) and item:
                output.append(item)
    return output


def _sse(raw: bytes):
    events = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SummaryError("streaming response is not UTF-8") from error
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        events.append(_json(data.encode(), "streaming response event"))
    if not events:
        raise SummaryError("streaming response contains no JSON events")
    return events


def _usage(response_values) -> dict:
    found = {}
    for node in _walk(response_values):
        usage = node.get("usage")
        if isinstance(usage, dict):
            found = usage
    details = found.get("prompt_tokens_details") if isinstance(found.get("prompt_tokens_details"), dict) else {}
    output_details = found.get("completion_tokens_details") if isinstance(found.get("completion_tokens_details"), dict) else {}
    values = {
        "input_tokens": found.get("input_tokens", found.get("prompt_tokens")),
        "output_tokens": found.get("output_tokens", found.get("completion_tokens")),
        "cached_tokens": found.get("cached_tokens", details.get("cached_tokens")),
        "reasoning_tokens": found.get("reasoning_tokens", output_details.get("reasoning_tokens")),
    }
    return {key: value for key, value in values.items() if type(value) is int and value >= 0}


def parse_capture(store, settings, key: str) -> dict:
    stored = store.get(key)
    value = _json(_zstd(stored.body, True), key)
    if not isinstance(value, dict) or value.get("schema_version") != "milk.exchange.v2":
        raise SummaryError(f"{key} is not a Milk v2 exchange")
    if value.get("scope_id") != settings.scope_id or value.get("profile") != settings.profile or value.get("complete") is not True:
        raise SummaryError(f"{key} scope, profile, or completion differs")
    exchange_id = value.get("exchange_id")
    try:
        parsed_id = uuid.UUID(exchange_id)
    except (TypeError, ValueError) as error:
        raise SummaryError(f"{key} exchange_id is invalid") from error
    if parsed_id.version != 7 or not key.endswith(f"/{exchange_id}.json.zst"):
        raise SummaryError(f"{key} exchange identity differs")
    started = _utc(value.get("started_at"), "started_at")
    completed = _utc(value.get("completed_at"), "completed_at")
    if completed < started:
        raise SummaryError(f"{key} completes before it starts")
    request_body = _decode_side(value.get("request"), "request")
    response_body = _decode_side(value.get("response"), "response")
    request_value = None
    response_values = None
    request_ok = response_ok = True
    try:
        request_value = _json(request_body, "request body")
    except SummaryError:
        request_ok = False
    try:
        response_values = _sse(response_body) if value.get("streaming") is True else [_json(response_body, "response body")]
    except SummaryError:
        response_ok = False
    request_nodes = list(_walk(request_value)) if request_ok else []
    response_nodes = list(_walk(response_values)) if response_ok else []
    item_types = {node.get("type") for node in request_nodes + response_nodes if isinstance(node.get("type"), str)}
    modalities = set()
    for modality, names in {
        "image": {"input_image", "image_url"},
        "file": {"input_file", "file"},
        "audio": {"input_audio", "audio"},
    }.items():
        if item_types & names:
            modalities.add(modality)
    if _texts(request_value) or _texts(response_values):
        modalities.add("text")
    if not modalities:
        modalities.add("unknown")
    tools = request_value.get("tools") if isinstance(request_value, dict) else None
    tool_definitions = len(tools) if isinstance(tools, list) else 0
    tool_calls = sum(node.get("type") in {"function_call", "tool_call"} for node in response_nodes)
    tool_calls += sum(len(node["tool_calls"]) for node in response_nodes if isinstance(node.get("tool_calls"), list))
    tool_argument_total = tool_argument_valid = 0
    for node in response_nodes:
        arguments = node.get("arguments")
        if isinstance(arguments, str):
            tool_argument_total += 1
            try:
                json.loads(arguments)
                tool_argument_valid += 1
            except json.JSONDecodeError:
                pass
    response = value.get("response")
    status = response.get("status") if isinstance(response, dict) else None
    if type(status) is not int or not 100 <= status <= 599:
        raise SummaryError(f"{key} response status is invalid")
    route = value.get("route") if isinstance(value.get("route"), dict) else {}
    timing = value.get("timing") if isinstance(value.get("timing"), dict) else {}
    request_model = request_value.get("model") if isinstance(request_value, dict) and isinstance(request_value.get("model"), str) else "unknown"
    structured = isinstance(request_value, dict) and (
        isinstance(request_value.get("response_format"), dict)
        or isinstance(request_value.get("text"), dict) and isinstance(request_value["text"].get("format"), dict)
    )
    refusal = any(isinstance(node.get("refusal"), str) and node["refusal"] for node in response_nodes)
    finish = sorted({str(node["finish_reason"]) for node in response_nodes if isinstance(node.get("finish_reason"), str)})
    usage = _usage(response_values)
    total_ms = timing.get("total_ms")
    ttft_ms = timing.get("ttft_ms")
    if type(total_ms) is not int or total_ms < 0 or (ttft_ms is not None and (type(ttft_ms) is not int or ttft_ms < 0)):
        raise SummaryError(f"{key} timing is invalid")
    output_tokens = usage.get("output_tokens")
    tps_milli = None
    if output_tokens is not None and total_ms > 0:
        tps_milli = output_tokens * 1_000_000 // total_ms
    request_sha256 = digest(request_body)
    response_sha256 = digest(response_body)
    content_sha256 = digest(request_body + b"\0" + response_body)
    reasoning = request_value.get("reasoning_effort") if isinstance(request_value, dict) else None
    if not isinstance(reasoning, str) and isinstance(request_value, dict) and isinstance(request_value.get("reasoning"), dict):
        reasoning = request_value["reasoning"].get("effort")
    return {
        "key": key,
        "object_sha256": digest(stored.body),
        "exchange_id": exchange_id,
        "content_sha256": content_sha256,
        "request_sha256": request_sha256,
        "response_sha256": response_sha256,
        "started_at": value["started_at"],
        "completed_at": value["completed_at"],
        "endpoint": value.get("endpoint") if isinstance(value.get("endpoint"), str) else "other",
        "streaming": value.get("streaming") is True,
        "model": request_model,
        "status": status,
        "status_class": f"{status // 100}xx",
        "success": 200 <= status < 300,
        "request_parse": request_ok,
        "response_parse": response_ok,
        "parse": request_ok and response_ok,
        "route_target": route.get("target") if isinstance(route.get("target"), str) else "unknown",
        "fallback_reason": route.get("fallback_reason") if isinstance(route.get("fallback_reason"), str) else "none",
        "modalities": sorted(modalities),
        "tool_definitions": tool_definitions,
        "tool_calls": tool_calls,
        "tool_argument_total": tool_argument_total,
        "tool_argument_valid": tool_argument_valid,
        "structured_output": structured,
        "reasoning_effort": reasoning if isinstance(reasoning, str) else "none",
        "refusal": refusal,
        "outcome": "refusal" if refusal else "+".join(finish) if finish else "success" if 200 <= status < 300 else "upstream_failure",
        "request_bytes": len(request_body),
        "response_bytes": len(response_body),
        "message_count": len(request_value.get("messages", [])) if isinstance(request_value, dict) and isinstance(request_value.get("messages"), list) else 0,
        "input_item_count": len(request_value.get("input", [])) if isinstance(request_value, dict) and isinstance(request_value.get("input"), list) else int(isinstance(request_value, dict) and request_value.get("input") is not None),
        "ttft_ms": ttft_ms,
        "total_ms": total_ms,
        "tps_milli": tps_milli,
        "usage": usage,
        "request_text": "\n".join(_texts(request_value)),
        "response_text": "\n".join(_texts(response_values)),
    }


def _finish_series(value: dict) -> dict:
    count = value["count"]
    if count == 0:
        return value
    value["mean_milli"] = (value["sum"] * 1000 + count // 2) // count
    value["variance_milli2"] = max(0, value["sum_squares"] * 1_000_000 // count - value["mean_milli"] ** 2)
    for name, numerator in (("p50", 50), ("p95", 95), ("p99", 99)):
        target, seen = (count * numerator + 99) // 100, 0
        for upper, frequency in sorted(value["histogram"].items(), key=lambda item: int(item[0])):
            seen += frequency
            if seen >= target:
                value[name] = int(upper)
                break
    return value


def _series(values) -> dict:
    values = [value for value in values if type(value) is int and value >= 0]
    if not values:
        return {"count": 0, "sum": 0, "sum_squares": 0, "min": None, "max": None, "histogram": {}}
    histogram = Counter("0" if value == 0 else str(1 << (value - 1).bit_length()) for value in values)
    return _finish_series({"count": len(values), "sum": sum(values), "sum_squares": sum(value * value for value in values), "min": min(values), "max": max(values), "histogram": dict(sorted(histogram.items(), key=lambda item: int(item[0])))})


def _merge_series(left, right) -> dict:
    if not left:
        return right
    histogram = Counter(left.get("histogram", {})) + Counter(right.get("histogram", {}))
    count = left.get("count", 0) + right.get("count", 0)
    return _finish_series({
        "count": count,
        "sum": left.get("sum", 0) + right.get("sum", 0),
        "sum_squares": left.get("sum_squares", 0) + right.get("sum_squares", 0),
        "min": min(value for value in (left.get("min"), right.get("min")) if value is not None) if count else None,
        "max": max(value for value in (left.get("max"), right.get("max")) if value is not None) if count else None,
        "histogram": dict(sorted(histogram.items(), key=lambda item: int(item[0]))),
    })


def _wilson(successes: int, total: int) -> list[int]:
    if total <= 0:
        return [0, 0]
    with localcontext() as context:
        context.prec = 40
        n, p, z = Decimal(total), Decimal(successes) / Decimal(total), Decimal("1.959963984540054")
        denominator = Decimal(1) + z * z / n
        center = (p + z * z / (Decimal(2) * n)) / denominator
        margin = z * ((p * (Decimal(1) - p) / n + z * z / (Decimal(4) * n * n)).sqrt()) / denominator
        return [int(((center - margin).max(Decimal(0)) * 10000).to_integral_value(rounding=ROUND_HALF_UP)), int(((center + margin).min(Decimal(1)) * 10000).to_integral_value(rounding=ROUND_HALF_UP))]


def _rate(numerator: int, denominator: int) -> int:
    return 0 if denominator <= 0 else min(10000, (numerator * 10000 + denominator // 2) // denominator)


def structural(rows: list[dict]) -> dict:
    counters = {
        "captures": len(rows),
        "complete": len(rows),
        "request_parsed": sum(row["request_parse"] for row in rows),
        "response_parsed": sum(row["response_parse"] for row in rows),
        "parsed": sum(row["parse"] for row in rows),
        "successful": sum(row["success"] for row in rows),
        "refusals": sum(row["refusal"] for row in rows),
        "tool_argument_total": sum(row["tool_argument_total"] for row in rows),
        "tool_argument_valid": sum(row["tool_argument_valid"] for row in rows),
    }
    distributions = {
        "endpoint": Counter(row["endpoint"] for row in rows),
        "model": Counter(row["model"] for row in rows),
        "status": Counter(str(row["status"]) for row in rows),
        "status_class": Counter(row["status_class"] for row in rows),
        "streaming": Counter(str(row["streaming"]).lower() for row in rows),
        "route_target": Counter(row["route_target"] for row in rows),
        "fallback_reason": Counter(row["fallback_reason"] for row in rows),
        "modalities": Counter(modality for row in rows for modality in row["modalities"]),
        "structured_output": Counter(str(row["structured_output"]).lower() for row in rows),
        "reasoning_effort": Counter(str(row["reasoning_effort"]) for row in rows),
        "outcome": Counter(row["outcome"] for row in rows),
        "hour_utc": Counter(row["started_at"][11:13] for row in rows),
    }
    series_names = ("request_bytes", "response_bytes", "message_count", "input_item_count", "tool_definitions", "tool_calls", "ttft_ms", "total_ms", "tps_milli")
    series = {name: _series([row[name] for row in rows]) for name in series_names}
    for usage_name in ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens"):
        series[usage_name] = _series([row["usage"].get(usage_name) for row in rows])
    return {"schema_version": "milk.structural-stats.v2", "counters": counters, "distributions": {name: dict(sorted(values.items())) for name, values in distributions.items()}, "series": series}


def merge_structural(previous: dict | None, delta: dict, all_source_rows: list[dict]) -> dict:
    if previous is None:
        merged = delta
    else:
        merged = {
            "schema_version": "milk.structural-stats.v2",
            "counters": {key: previous["counters"].get(key, 0) + delta["counters"].get(key, 0) for key in set(previous["counters"]) | set(delta["counters"])},
            "distributions": {},
            "series": {key: _merge_series(previous["series"].get(key), delta["series"].get(key)) for key in set(previous["series"]) | set(delta["series"])},
        }
        for name in set(previous["distributions"]) | set(delta["distributions"]):
            merged["distributions"][name] = dict(sorted((Counter(previous["distributions"].get(name, {})) + Counter(delta["distributions"].get(name, {}))).items()))
    contents = [row["content_sha256"] for row in all_source_rows]
    merged["counters"]["unique_contents"] = len(set(contents))
    merged["counters"]["duplicates"] = len(contents) - len(set(contents))
    events = []
    for row in all_source_rows:
        events.append((_utc(row["started_at"], "started_at"), 1))
        events.append((_utc(row["completed_at"], "completed_at"), -1))
    active = maximum = 0
    for unused_time, change in sorted(events, key=lambda event: (event[0], event[1])):
        active += change
        maximum = max(maximum, active)
    merged["counters"]["max_concurrency"] = maximum
    total = merged["counters"]["captures"]
    parsed = merged["counters"]["parsed"]
    successful = merged["counters"]["successful"]
    duplicates = merged["counters"]["duplicates"]
    merged["quality"] = {
        "parse_basis_points": _rate(parsed, total),
        "parse_wilson_95_basis_points": _wilson(parsed, total),
        "success_basis_points": _rate(successful, total),
        "success_wilson_95_basis_points": _wilson(successful, total),
        "duplicate_basis_points": _rate(duplicates, total),
        "duplicate_wilson_95_basis_points": _wilson(duplicates, total),
        "capture_gap": False,
    }
    return merged


def _sampling(rows: list[dict]) -> list[dict]:
    representative_limit = _integer_environment("MILK_SUMMARY_REPRESENTATIVE_SAMPLE", 256, 1, 2048)
    tail_limit = _integer_environment("MILK_SUMMARY_TAIL_SAMPLE", 64, 0, 512)
    eligible = [row for row in rows if row["parse"] and row.get("has_text", bool(row.get("request_text") or row.get("response_text")))]
    representative = sorted(eligible, key=lambda row: digest(("representative:" + row["key"]).encode()))[:representative_limit]
    request_sizes = sorted(row["request_bytes"] for row in eligible)
    long_threshold = max(8192, request_sizes[(len(request_sizes) * 95 - 1) // 100]) if request_sizes else 8192
    cell_counts = Counter((row["endpoint"], row["model"], row["status_class"], tuple(row["modalities"])) for row in eligible)
    reasons = {
        "error": lambda row: not row["success"] or not row["parse"],
        "tool_use": lambda row: row["tool_definitions"] > 0 or row["tool_calls"] > 0,
        "multimodal": lambda row: any(item not in {"text", "unknown"} for item in row["modalities"]),
        "long_context": lambda row: row["request_bytes"] >= long_threshold,
        "rare": lambda row: cell_counts[(row["endpoint"], row["model"], row["status_class"], tuple(row["modalities"]))] == 1,
    }
    selected = {row["key"]: {"row": row, "reasons": ["representative"]} for row in representative}
    tail_reasons = {row["key"]: [reason for reason, predicate in reasons.items() if predicate(row)] for row in eligible}
    for key, entry in selected.items():
        entry["reasons"].extend(tail_reasons[key])
    if tail_limit:
        tail_only = sorted(
            (row for row in eligible if row["key"] not in selected and tail_reasons[row["key"]]),
            key=lambda row: digest(("tail:" + row["key"]).encode()),
        )[:tail_limit]
        for row in tail_only:
            selected[row["key"]] = {"row": row, "reasons": tail_reasons[row["key"]]}
    return [selected[key] for key in sorted(selected)]


def _label_contract(value, sampled: list[dict]) -> list[dict]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "labels"} or value.get("schema_version") != "milk.semantic-labels.v2" or not isinstance(value.get("labels"), list):
        raise ProviderError("summary model returned an invalid semantic object")
    expected = {entry["row"]["content_sha256"] for entry in sampled}
    labels = value["labels"]
    if len(labels) != len(expected):
        raise ProviderError("summary model returned the wrong label count")
    checked = []
    for label in labels:
        fields = {"row_id", "operation", "domain", "capabilities", "oracle", "sentiment", "outcome", "language", "complexity", "answerable", "safety", "confidence_basis_points", "abstain"}
        if not isinstance(label, dict) or set(label) != fields:
            raise ProviderError("summary model returned invalid label fields")
        if label["row_id"] not in expected or any(item["row_id"] == label["row_id"] for item in checked):
            raise ProviderError("summary model returned an unknown or duplicate row")
        if label["operation"] not in OPERATIONS or label["domain"] not in DOMAINS or label["oracle"] not in ORACLES or label["sentiment"] not in SENTIMENTS or label["outcome"] not in OUTCOMES or label["complexity"] not in COMPLEXITIES or label["safety"] not in SAFETY:
            raise ProviderError("summary model returned an unknown taxonomy value")
        if not isinstance(label["capabilities"], list) or len(label["capabilities"]) != len(set(label["capabilities"])) or any(item not in CAPABILITIES for item in label["capabilities"]):
            raise ProviderError("summary model returned invalid capabilities")
        if not isinstance(label["language"], str) or not 1 <= len(label["language"]) <= 32 or type(label["answerable"]) is not bool or type(label["abstain"]) is not bool or type(label["confidence_basis_points"]) is not int or not 0 <= label["confidence_basis_points"] <= 10000:
            raise ProviderError("summary model returned invalid label values")
        checked.append(label)
    return sorted(checked, key=lambda label: label["row_id"])


def _utf8_prefix(value: str, maximum: int) -> str:
    return value.encode("utf-8")[:maximum].decode("utf-8", "ignore")


def _prepared_batches(fixed: dict, rows: list[tuple[dict, dict]]) -> list[tuple[dict, list[dict]]]:
    batches = []
    current_rows: list[dict] = []
    current_entries: list[dict] = []
    for row, entry in rows:
        candidate = {**fixed, "rows": current_rows + [row]}
        if len(canonical(candidate)) > SUMMARY_BATCH_BYTES:
            if not current_rows:
                raise SummaryError("summary fixed metadata plus one row exceeds 64 KiB")
            batches.append(({**fixed, "rows": current_rows}, current_entries))
            candidate = {**fixed, "rows": [row]}
            if len(canonical(candidate)) > SUMMARY_BATCH_BYTES:
                raise SummaryError("summary fixed metadata plus one row exceeds 64 KiB")
            current_rows, current_entries = [row], [entry]
        else:
            current_rows.append(row)
            current_entries.append(entry)
    if current_rows:
        batches.append(({**fixed, "rows": current_rows}, current_entries))
    return batches


def _batch_claim(store, key: str, job_id: str, batch_id: str, input_sha256: str, timeout: int) -> tuple[str, int]:
    empty = {
        "schema_version": "milk.summary-batch-claim.v2",
        "job_id": job_id,
        "batch_id": batch_id,
        "input_sha256": input_sha256,
        "state": "retryable",
        "generation": 0,
    }
    try:
        current = store.get(key)
    except FileNotFoundError:
        try:
            store.create_same(key, canonical(empty))
        except ValueError:
            pass
        current = store.get(key)
    value = _json(current.body, key)
    required = {"schema_version", "job_id", "batch_id", "input_sha256", "state", "generation"}
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.get("schema_version") != empty["schema_version"]
        or value.get("job_id") != job_id
        or value.get("batch_id") != batch_id
        or value.get("input_sha256") != input_sha256
        or value.get("state") not in {"active", "retryable"}
        or type(value.get("generation")) is not int
        or value["generation"] < 0
    ):
        raise SummaryError("summary batch claim is invalid")
    now = dt.datetime.now(dt.timezone.utc)
    if value["state"] == "active" and _utc(value.get("expires_at"), "batch claim expires_at") > now:
        raise BusyError(digest({"job_id": job_id, "batch_id": batch_id}))
    owner = uuid.uuid4().hex
    generation = value["generation"] + 1
    active = {
        **empty,
        "state": "active",
        "generation": generation,
        "owner": owner,
        "acquired_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expires_at": (now + dt.timedelta(seconds=timeout + 30)).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    if store.replace_if_match(key, current.etag, canonical(active)) is None:
        raise BusyError(digest({"job_id": job_id, "batch_id": batch_id}))
    return owner, generation


def _release_batch_claim(store, key: str, owner: str) -> None:
    try:
        current = store.get(key)
        value = _json(current.body, key)
        if not isinstance(value, dict) or value.get("state") != "active" or value.get("owner") != owner:
            return
        retryable = {name: value[name] for name in ("schema_version", "job_id", "batch_id", "input_sha256", "generation")}
        retryable["state"] = "retryable"
        store.replace_if_match(key, current.etag, canonical(retryable))
    except Exception:
        return


def _session_tools(row_count: int) -> list[dict]:
    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    label_properties = {
        "row_id": {"type": "string"},
        "operation": {"type": "string", "enum": list(OPERATIONS)},
        "domain": {"type": "string", "enum": list(DOMAINS)},
        "capabilities": {"type": "array", "items": {"type": "string", "enum": list(CAPABILITIES)}, "uniqueItems": True},
        "oracle": {"type": "string", "enum": list(ORACLES)},
        "sentiment": {"type": "string", "enum": list(SENTIMENTS)},
        "outcome": {"type": "string", "enum": list(OUTCOMES)},
        "language": {"type": "string", "minLength": 1, "maxLength": 32},
        "complexity": {"type": "string", "enum": list(COMPLEXITIES)},
        "answerable": {"type": "boolean"},
        "safety": {"type": "string", "enum": list(SAFETY)},
        "confidence_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000},
        "abstain": {"type": "boolean"},
    }
    result = {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": ["milk.semantic-labels.v2"]},
            "labels": {
                "type": "array",
                "items": {"type": "object", "properties": label_properties, "required": list(label_properties), "additionalProperties": False},
                "minItems": row_count,
                "maxItems": row_count,
            },
        },
        "required": ["schema_version", "labels"],
        "additionalProperties": False,
    }
    return [
        {"type": "function", "function": {"name": "milk_job_read", "description": "Read the immutable prepared input for this summary job.", "parameters": empty}},
        {
            "type": "function",
            "function": {
                "name": "milk_job_commit",
                "description": "Commit the complete semantic-label result for this summary job.",
                "parameters": {
                    "type": "object",
                    "properties": {"result": result},
                    "required": ["result"],
                    "additionalProperties": False,
                },
            },
        },
        {"type": "function", "function": {"name": "milk_status", "description": "Read bounded status for this summary job.", "parameters": empty}},
    ]


def _provider_call(prompt: str, input_value: dict) -> tuple[dict, dict]:
    base = os.environ.get("MILK_SUMMARY_BASE_URL", "").rstrip("/")
    model = os.environ.get("MILK_SUMMARY_MODEL", "")
    api_key = os.environ.get("MILK_SUMMARY_API_KEY", "")
    if not base or not model or not api_key:
        raise SummaryError("MILK_SUMMARY_BASE_URL, MILK_SUMMARY_MODEL, and MILK_SUMMARY_API_KEY are required at a crossed threshold")
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SummaryError("MILK_SUMMARY_BASE_URL is invalid")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SummaryError("MILK_SUMMARY_BASE_URL must use HTTPS outside localhost")
    if parsed.path.rstrip("/") not in {"", "/v1"}:
        raise SummaryError("MILK_SUMMARY_BASE_URL must be an origin or end in /v1")
    api_mode = os.environ.get("MILK_SUMMARY_API_MODE", "chat_completions")
    if api_mode not in {"chat_completions", "responses"}:
        raise SummaryError("MILK_SUMMARY_API_MODE must be chat_completions or responses")
    endpoint = base + ("" if parsed.path.rstrip("/") == "/v1" else "/v1") + ("/responses" if api_mode == "responses" else "/chat/completions")
    timeout = _integer_environment("MILK_SUMMARY_TIMEOUT_SECONDS", 120, 1, 3600)
    input_sha256 = digest(input_value)
    rows = input_value.get("rows")
    if (
        not isinstance(rows, list)
        or any(not isinstance(row, dict) or not isinstance(row.get("row_id"), str) for row in rows)
        or len({row["row_id"] for row in rows}) != len(rows)
    ):
        raise SummaryError("summary session input has invalid rows")
    expected_sample = [{"row": {"content_sha256": row["row_id"]}} for row in rows]
    messages = [{
        "role": "user",
        "content": canonical({
            "schema_version": "milk.summary-session-turn.v2",
            "job": "summary",
            "input_sha256": input_sha256,
            "next": "milk_job_read",
        }).decode(),
    }]
    llm = Path(__file__).resolve().parents[1] / "vendor" / "headlong" / "bin" / "llm"
    usage = Counter()
    request_ids = []
    tool_calls_seen = 0
    read_seen = False
    last_tools: list[str] = []
    last_rejection = "none"
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="milk-summary-") as directory:
        root = Path(directory)
        system_file, messages_file, tools_file = (root / name for name in ("system", "messages.json", "tools.json"))
        system_file.write_text(prompt)
        tools_file.write_bytes(canonical(_session_tools(len(rows))))
        os.chmod(system_file, 0o600)
        os.chmod(tools_file, 0o600)
        for turn in range(1, 5):
            remaining = timeout - int(time.monotonic() - started)
            if remaining < 1:
                raise ProviderError("summary provider session timed out")
            messages_file.write_bytes(canonical(messages))
            os.chmod(messages_file, 0o600)
            environment = {
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "LLM_API_URL": endpoint,
                "LLM_MODEL": model,
                "LLM_API_KEY": api_key,
                "LLM_API_MODE": api_mode,
                "LLM_CONNECT_TIMEOUT": str(min(10, remaining)),
                "LLM_MAX_TIME": str(remaining),
            }
            if os.environ.get("MILK_REASONING_EFFORT"):
                environment["LLM_REASONING_EFFORT"] = os.environ["MILK_REASONING_EFFORT"]
            if os.environ.get("TMPDIR"):
                environment["TMPDIR"] = os.environ["TMPDIR"]
            try:
                process = subprocess.run(
                    [str(llm), "--system-file", str(system_file), "--messages-file", str(messages_file), "--tools-file", str(tools_file), "--json-response"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=environment,
                    timeout=remaining + 2,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise ProviderError("summary provider request failed") from error
            if process.returncode != 0:
                raise ProviderError("summary provider request failed")
            if len(process.stdout) > 4 * 1024 * 1024:
                raise ProviderError("summary provider response is oversized")
            try:
                response = json.loads(process.stdout)
                message = response["message"]
                tool_calls = message["tool_calls"]
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
                raise ProviderError("summary provider returned no Milk tool call") from error
            if not isinstance(message, dict) or message.get("role") != "assistant" or not isinstance(tool_calls, list) or not tool_calls:
                raise ProviderError("summary provider returned no Milk tool call")
            request_id = response.get("provider_request_id")
            if isinstance(request_id, str) and len(request_id) <= 256:
                request_ids.append(request_id)
            response_usage = response.get("usage")
            if isinstance(response_usage, dict):
                usage.update({key: value for key, value in response_usage.items() if type(value) is int and value >= 0})
            tool_calls_seen += len(tool_calls)
            if tool_calls_seen > 16:
                raise ProviderError("summary provider exceeded the Milk tool-call limit")
            assistant_message = {"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls}
            if isinstance(message.get("reasoning_content"), str):
                assistant_message["reasoning_content"] = message["reasoning_content"]
            messages.append(assistant_message)
            committed = None
            can_commit = read_seen
            last_tools = []
            for call in tool_calls:
                try:
                    call_id = call["id"]
                    function = call["function"]
                    name = function["name"]
                    arguments = json.loads(function["arguments"])
                except (KeyError, TypeError, json.JSONDecodeError) as error:
                    raise ProviderError("summary provider returned an invalid Milk tool call") from error
                if not isinstance(call_id, str) or not call_id or call.get("type") != "function" or not isinstance(arguments, dict):
                    raise ProviderError("summary provider returned an invalid Milk tool call")
                last_tools.append(name)
                if name == "milk_job_commit":
                    if set(arguments) != {"result"} or not isinstance(arguments["result"], dict) or committed is not None:
                        raise ProviderError("summary provider returned an invalid Milk commit")
                    if not can_commit:
                        last_rejection = "commit_before_read"
                        messages.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": canonical({"accepted": False, "error": "read the prepared input before committing"}).decode()})
                        continue
                    try:
                        labels = _label_contract(arguments["result"], expected_sample)
                    except ProviderError as error:
                        last_rejection = str(error)
                        messages.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": canonical({"accepted": False, "error": str(error)}).decode()})
                        continue
                    committed = {"schema_version": "milk.semantic-labels.v2", "labels": labels}
                    continue
                if arguments or name not in {"milk_job_read", "milk_status"}:
                    raise ProviderError("summary provider requested an unavailable tool")
                if name == "milk_job_read":
                    result = input_value if not read_seen else {"schema_version": "milk.job-input-reference.v2", "input_sha256": input_sha256, "already_read": True}
                    read_seen = True
                else:
                    result = {
                        "schema_version": "milk.job-status.v2",
                        "job": "summary",
                        "state": "active",
                        "input_sha256": input_sha256,
                        "turn": turn,
                    }
                messages.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": canonical(result).decode()})
            if committed is not None:
                receipt = {
                    "schema_version": "milk.summary-provider-receipt.v2",
                    "provider_request_id": request_ids[-1] if request_ids else None,
                    "provider_request_ids": request_ids,
                    "model": model,
                    "api_mode": api_mode,
                    "reasoning_effort": os.environ.get("MILK_REASONING_EFFORT", ""),
                    "usage": dict(usage),
                    "inference_calls": turn,
                    "output": committed,
                    "output_sha256": digest(committed),
                }
                return committed, receipt
    raise ProviderError(
        f"summary provider did not commit within four turns: tools={','.join(last_tools)} rejection={last_rejection}",
        inference_calls=4,
    )


def _semantic_counts(labels: list[dict], previous: dict | None) -> dict:
    current = {
        "classified": len(labels),
        "abstained": sum(label["abstain"] for label in labels),
        "operation": Counter(label["operation"] for label in labels),
        "domain": Counter(label["domain"] for label in labels),
        "capability": Counter(item for label in labels for item in label["capabilities"]),
        "oracle": Counter(label["oracle"] for label in labels),
        "sentiment": Counter(label["sentiment"] for label in labels),
        "outcome": Counter(label["outcome"] for label in labels),
        "language": Counter(label["language"] for label in labels),
    }
    prior = previous or {}
    cumulative = {"classified": current["classified"], "abstained": current["abstained"]}
    delta = {"classified": current["classified"] - prior.get("classified", 0), "abstained": current["abstained"] - prior.get("abstained", 0)}
    for name in ("operation", "domain", "capability", "oracle", "sentiment", "outcome", "language"):
        cumulative[name] = dict(sorted(current[name].items()))
        keys = set(current[name]) | set(prior.get(name, {}))
        delta[name] = {key: current[name].get(key, 0) - prior.get(name, {}).get(key, 0) for key in sorted(keys) if current[name].get(key, 0) != prior.get(name, {}).get(key, 0)}
    cumulative["abstain_basis_points"] = _rate(cumulative["abstained"], cumulative["classified"])
    cumulative["abstain_wilson_95_basis_points"] = _wilson(cumulative["abstained"], cumulative["classified"])
    return {"taxonomy_version": TAXONOMY_VERSION, "delta": delta, "cumulative": cumulative}


def _read_pointer(store, prefix: str):
    try:
        pointer_object = store.get(prefix + "s/current.json")
    except FileNotFoundError:
        return None, None, None
    pointer = _json(pointer_object.body, "s/current.json")
    if not isinstance(pointer, dict) or pointer.get("schema_version") != "milk.pointer.v2" or pointer.get("kind") != "summary":
        raise SummaryError("s/current.json is invalid")
    summary_object = store.get(pointer.get("key", ""))
    if digest(summary_object.body) != pointer.get("sha256"):
        raise SummaryError("current summary digest differs")
    summary = _json(summary_object.body, "current summary")
    if not isinstance(summary, dict) or summary.get("scope_id") != pointer.get("scope_id") or summary.get("summary_uuid") != pointer.get("uuid"):
        raise SummaryError("current summary identity differs")
    return pointer, pointer_object, summary


def _ancestry(store, settings, summary: dict | None) -> tuple[list[dict], set[str]]:
    source_rows, capture_keys, seen = [], set(), set()
    current = summary
    while current is not None:
        key = current.get("source_manifest_key")
        if not isinstance(key, str) or not key.startswith(settings.scope_prefix + "s/") or key in seen:
            raise SummaryError("summary ancestry is invalid")
        seen.add(key)
        source_object = store.get(key)
        if digest(source_object.body) != current.get("source_manifest_sha256"):
            raise SummaryError("summary source manifest digest differs")
        source = _json(_zstd(source_object.body, True), key)
        if not isinstance(source, dict) or source.get("scope_id") != settings.scope_id or source.get("profile") != settings.profile:
            raise SummaryError("summary source manifest identity differs")
        rows = source.get("captures") if isinstance(source, dict) else None
        if not isinstance(rows, list):
            raise SummaryError("summary source manifest is invalid")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("key"), str) or row["key"] in capture_keys:
                raise SummaryError("summary source manifest contains an invalid capture")
            capture_keys.add(row["key"])
            source_rows.append(row)
        parent_key = current.get("parent_summary_key")
        if parent_key is None:
            current = None
        else:
            if not isinstance(parent_key, str) or not parent_key.startswith(settings.scope_prefix + "s/"):
                raise SummaryError("parent summary key is outside the scope")
            parent = store.get(parent_key)
            if digest(parent.body) != current.get("parent_summary_sha256"):
                raise SummaryError("parent summary digest differs")
            current = _json(parent.body, parent_key)
    return source_rows, capture_keys


def inspect(store, settings) -> dict:
    keys = list(store_key for store_key in _list_all(store, settings.scope_prefix + "c/"))
    pointer, unused_object, summary = _read_pointer(store, settings.scope_prefix)
    unused_rows, processed = _ancestry(store, settings, summary) if summary else ([], set())
    next_threshold = next((value for value in thresholds(settings.profile) if value > len(processed)), None)
    try:
        readiness_pointer = _json(store.get(settings.scope_prefix + "readiness/current.json").body, "readiness/current.json")
    except FileNotFoundError:
        readiness_pointer = None
    return {"capture_keys": keys, "capture_count": len(keys), "processed_count": len(processed), "next_threshold": next_threshold, "summary_pointer": pointer, "summary": summary, "readiness_pointer": readiness_pointer}


def _list_all(store, prefix: str):
    cursor = None
    while True:
        page = store.list(prefix, cursor)
        yield from page.keys
        if page.next_cursor is None:
            return
        cursor = page.next_cursor


def _advance(store, key: str, value: dict) -> tuple[str, str]:
    body = canonical(value)
    try:
        current = store.get(key)
    except FileNotFoundError:
        put = store.create_same(key, body)
        return ("created" if put.created else "existing", digest(body))
    if current.body == body:
        return "existing", digest(body)
    updated = store.replace_if_match(key, current.etag, body)
    if updated is None:
        current = store.get(key)
        if current.body != body:
            raise BusyError(digest(value))
        return "existing", digest(body)
    return "updated", digest(body)


def _status(store, settings, state: dict) -> dict:
    summary = state.get("summary")
    metrics = None
    if summary is not None:
        structural = summary["structural"]
        series = structural["series"]
        metrics = {
            "quality": structural["quality"],
            "counters": structural["counters"],
            "distributions": structural["distributions"],
            "series": {
                name: series[name]
                for name in (
                    "total_ms",
                    "ttft_ms",
                    "tps_milli",
                    "input_tokens",
                    "output_tokens",
                    "message_count",
                    "tool_calls",
                )
            },
            "semantic": summary["semantic"]["cumulative"],
        }
    value = {
        "schema_version": "milk.status.v2",
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "capture_count": state["capture_count"],
        "processed_count": state["processed_count"],
        "next_summary_threshold": state["next_threshold"],
        "summary": state.get("summary_pointer"),
        "summary_metrics": metrics,
        "readiness": state.get("readiness_pointer"),
        "next_action": state.get("next_action", "summary"),
    }
    _advance(store, settings.scope_prefix + "status/current.json", value)
    return value


def _readiness(settings, summary: dict, summary_sha256: str, labels: list[dict]) -> dict:
    production = settings.profile == "production"
    minimum_captures = _integer_environment("MILK_EVAL_MIN_CAPTURES", 1000 if production else 1, 1, 10_000_000)
    minimum_unique = _integer_environment("MILK_EVAL_MIN_UNIQUE_SOURCES", 32 if production else 1, 1, 1_000_000)
    minimum_parse = _integer_environment("MILK_EVAL_MIN_PARSE_WILSON_BPS", 9500 if production else 0, 0, 10000)
    maximum_abstain = _integer_environment("MILK_EVAL_MAX_ABSTAIN_WILSON_BPS", 2000 if production else 10000, 0, 10000)
    structural_value = summary["structural"]
    semantic = summary["semantic"]["cumulative"]
    try:
        plan = eval_plan.build(labels, settings.profile)
    except eval_plan.PlanError as error:
        raise SummaryError(str(error)) from error
    checks = {
        "minimum_complete_captures": summary["capture_count"] >= minimum_captures,
        "parse_wilson_lower": structural_value["quality"]["parse_wilson_95_basis_points"][0] >= minimum_parse,
        "abstain_wilson_upper": semantic["abstain_wilson_95_basis_points"][1] <= maximum_abstain,
        "minimum_unique_sources": len(plan["sources"]) >= minimum_unique,
        "split_quotas": plan["ready"],
    }
    ready = all(checks.values())
    identity = {"schema_version": "milk.readiness.v3", "scope_id": settings.scope_id, "profile": settings.profile, "summary_sha256": summary_sha256, "checks": checks, "ready": ready, "statistically_qualified": ready and production, "eval_plan": {"policy": plan["policy"], "counts": plan["counts"], "missing": plan["missing"]}}
    readiness_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:readiness:" + digest(identity)))
    return {**identity, "readiness_uuid": readiness_uuid}


def _checkpoint(store, settings, runtime, parent_pointer, parent_summary, prior_rows, processed: set[str], selected_keys: list[str]):
    rows = [parse_capture(store, settings, key) for key in selected_keys]
    source_fields = ("key", "object_sha256", "content_sha256", "request_sha256", "response_sha256", "exchange_id", "started_at", "completed_at", "parse", "success", "endpoint", "model", "status", "status_class", "modalities", "tool_definitions", "tool_calls", "request_bytes", "response_bytes")
    source_rows = [{**{key: row[key] for key in source_fields}, "has_text": bool(row["request_text"] or row["response_text"])} for row in rows]
    all_rows = prior_rows + source_rows
    prompt_path = Path(__file__).resolve().parents[1] / runtime.job("summary").system_prompt
    prompt = prompt_path.read_text()
    prompt_sha256 = digest(prompt.encode())
    base = os.environ.get("MILK_SUMMARY_BASE_URL", "")
    model = os.environ.get("MILK_SUMMARY_MODEL", "")
    model_binding_sha256 = digest({"base_url": base, "model": model, "api_mode": os.environ.get("MILK_SUMMARY_API_MODE", "chat_completions"), "reasoning_effort": os.environ.get("MILK_REASONING_EFFORT", "")})
    classifier_config_sha256 = digest({"taxonomy": TAXONOMY_VERSION, "prompt_sha256": prompt_sha256, "model_binding_sha256": model_binding_sha256, "code_version": CODE_VERSION})
    sampled = _sampling(all_rows)
    parsed_by_key = {row["key"]: row for row in rows}
    for entry in sampled:
        source_row = entry["row"]
        parsed = parsed_by_key.get(source_row["key"])
        if parsed is None:
            parsed = parse_capture(store, settings, source_row["key"])
        if parsed["object_sha256"] != source_row["object_sha256"] or parsed["content_sha256"] != source_row["content_sha256"]:
            raise SummaryError("sampled capture identity differs from its source manifest")
        entry["row"] = parsed
    classification_sample = []
    seen_contents = set()
    for entry in sampled:
        if entry["row"]["content_sha256"] not in seen_contents:
            seen_contents.add(entry["row"]["content_sha256"])
            classification_sample.append(entry)
    cached_labels, missing = [], []
    for entry in classification_sample:
        row = entry["row"]
        label_key = settings.scope_prefix + f"l/{classifier_config_sha256}/{row['content_sha256']}.json"
        try:
            label = _json(store.get(label_key).body, label_key)
            cached_labels.append(label["label"])
        except FileNotFoundError:
            missing.append(entry)
    parent_sha256 = parent_pointer.get("sha256") if parent_pointer else None
    identity_value = {"schema_version": "milk.summary-job-identity.v2", "scope_id": settings.scope_id, "profile": settings.profile, "parent_summary_sha256": parent_sha256, "source_objects": [{"key": row["key"], "sha256": row["object_sha256"]} for row in rows], "config_digest": runtime.digest, "classifier_config_sha256": classifier_config_sha256}
    job_id = digest(identity_value)
    job_prefix = settings.scope_prefix + f"j/summary/{job_id}/"
    labels = list(cached_labels)
    inference_calls = 0
    if missing:
        intent = {**identity_value, "job_id": job_id}
        store.create_same(job_prefix + "intent.json", canonical(intent))
        try:
            result = _json(store.get(job_prefix + "result.json").body, "stored summary result")
            if not isinstance(result, dict) or result.get("schema_version") != "milk.summary-job-result.v2" or result.get("job_id") != job_id:
                raise SummaryError("stored summary result is invalid")
            labels.extend(_label_contract({"schema_version": "milk.semantic-labels.v2", "labels": result.get("labels")}, missing))
        except FileNotFoundError:
            limit = _integer_environment("MILK_CLASSIFIER_TEXT_BYTES", 2048, 128, 16384)
            fixed = {
                "schema_version": "milk.summary-input.v2",
                "taxonomy_version": TAXONOMY_VERSION,
                "prior_checkpoint": None if parent_summary is None else {"capture_count": parent_summary["capture_count"], "structural_quality": parent_summary["structural"]["quality"], "semantic": parent_summary["semantic"]["cumulative"]},
                "structural": merge_structural(parent_summary.get("structural") if parent_summary else None, structural(rows), all_rows),
            }
            prepared = []
            for entry in missing:
                row = entry["row"]
                prepared.append(({
                    "row_id": row["content_sha256"],
                    "endpoint": row["endpoint"],
                    "model": row["model"],
                    "status": row["status"],
                    "modalities": row["modalities"],
                    "selection_reasons": entry["reasons"],
                    "request_text": _utf8_prefix(row["request_text"], limit),
                    "response_text": _utf8_prefix(row["response_text"], limit),
                }, entry))
            batch_results = []
            completed_labels = []
            timeout = _integer_environment("MILK_SUMMARY_TIMEOUT_SECONDS", 120, 1, 3600)
            for index, (input_value, batch_entries) in enumerate(_prepared_batches(fixed, prepared)):
                input_sha256 = digest(input_value)
                batch_id = digest({"job_id": job_id, "index": index, "input_sha256": input_sha256})
                batch_prefix = job_prefix + f"b/{index:04d}-{batch_id}/"
                result_key = batch_prefix + "result.json"
                receipt_key = batch_prefix + "receipt.json"
                try:
                    batch_result_body = store.get(result_key).body
                    batch_result = _json(batch_result_body, result_key)
                    if (
                        not isinstance(batch_result, dict)
                        or batch_result.get("schema_version") != "milk.summary-batch-result.v2"
                        or batch_result.get("job_id") != job_id
                        or batch_result.get("batch_id") != batch_id
                        or batch_result.get("input_sha256") != input_sha256
                    ):
                        raise SummaryError("stored summary batch result is invalid")
                    checked = _label_contract({"schema_version": "milk.semantic-labels.v2", "labels": batch_result.get("labels")}, batch_entries)
                except FileNotFoundError:
                    try:
                        receipt_body = store.get(receipt_key).body
                        receipt = _json(receipt_body, receipt_key)
                    except FileNotFoundError:
                        claim_key = batch_prefix + "claim.json"
                        owner, generation = _batch_claim(store, claim_key, job_id, batch_id, input_sha256, timeout)
                        try:
                            receipt_body = store.get(receipt_key).body
                            receipt = _json(receipt_body, receipt_key)
                        except FileNotFoundError:
                            try:
                                output, provider_receipt = _provider_call(prompt, input_value)
                            except (ProviderError, SummaryError):
                                _release_batch_claim(store, claim_key, owner)
                                raise
                            calls = provider_receipt.get("inference_calls")
                            if type(calls) is not int or calls < 1:
                                _release_batch_claim(store, claim_key, owner)
                                raise SummaryError("summary provider receipt has invalid inference calls")
                            receipt = {**provider_receipt, "job_id": job_id, "batch_id": batch_id, "input_sha256": input_sha256, "generation": generation}
                            receipt_body = canonical(receipt)
                            store.create_same(receipt_key, receipt_body)
                            inference_calls += calls
                    if (
                        not isinstance(receipt, dict)
                        or receipt.get("schema_version") != "milk.summary-provider-receipt.v2"
                        or receipt.get("job_id") != job_id
                        or receipt.get("batch_id") != batch_id
                        or receipt.get("input_sha256") != input_sha256
                    ):
                        raise SummaryError("stored summary batch receipt is invalid")
                    checked = _label_contract(receipt.get("output"), batch_entries)
                    batch_result = {
                        "schema_version": "milk.summary-batch-result.v2",
                        "job_id": job_id,
                        "batch_id": batch_id,
                        "input_sha256": input_sha256,
                        "labels": checked,
                        "receipt_sha256": digest(receipt_body),
                    }
                    batch_result_body = canonical(batch_result)
                    store.create_same(result_key, batch_result_body)
                completed_labels.extend(checked)
                batch_results.append({"batch_id": batch_id, "input_sha256": input_sha256, "key": result_key, "sha256": digest(batch_result_body)})
            checked = _label_contract({"schema_version": "milk.semantic-labels.v2", "labels": completed_labels}, missing)
            result = {"schema_version": "milk.summary-job-result.v2", "job_id": job_id, "labels": checked, "batches": batch_results}
            store.create_same(job_prefix + "result.json", canonical(result))
            labels.extend(checked)
    labels = _label_contract({"schema_version": "milk.semantic-labels.v2", "labels": labels}, classification_sample)
    by_row = {label["row_id"]: label for label in labels}
    enriched_labels = []
    for entry in sampled:
        row, reasons = entry["row"], entry["reasons"]
        label = by_row.get(row["content_sha256"])
        if label is None:
            raise SummaryError("semantic result is missing a sampled row")
        label_key = settings.scope_prefix + f"l/{classifier_config_sha256}/{row['content_sha256']}.json"
        label_object = {"schema_version": "milk.semantic-label.v2", "scope_id": settings.scope_id, "profile": settings.profile, "content_sha256": row["content_sha256"], "classifier_config_sha256": classifier_config_sha256, "label": label}
        label_body = canonical(label_object)
        store.create_same(label_key, label_body)
        enriched_labels.append({**label, "source_key": row["key"], "source_object_sha256": row["object_sha256"], "content_sha256": row["content_sha256"], "request_sha256": row["request_sha256"], "response_sha256": row["response_sha256"], "modalities": row["modalities"], "tool_definitions": row["tool_definitions"], "tool_calls": row["tool_calls"], "success": row["success"], "label_key": label_key, "label_sha256": digest(label_body), "selection_reasons": reasons})
    delta_structural = structural(rows)
    cumulative_structural = merge_structural(parent_summary.get("structural") if parent_summary else None, delta_structural, all_rows)
    previous_semantic = parent_summary.get("semantic", {}).get("cumulative") if parent_summary else None
    semantic = _semantic_counts(labels, previous_semantic)
    semantic["sample"] = [{key: label[key] for key in ("source_key", "source_object_sha256", "content_sha256", "request_sha256", "response_sha256", "modalities", "tool_definitions", "tool_calls", "success", "label_key", "label_sha256", "selection_reasons")} for label in enriched_labels]
    summary_identity = {"scope_id": settings.scope_id, "profile": settings.profile, "parent_summary_sha256": parent_sha256, "source_manifest_logical_sha256": digest({"captures": source_rows}), "capture_count": len(processed) + len(rows), "config_digest": runtime.digest, "prompt_sha256": prompt_sha256, "model_binding_sha256": model_binding_sha256, "structural": cumulative_structural, "semantic": semantic}
    summary_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:summary:" + digest(summary_identity)))
    created_at = max(row["completed_at"] for row in rows)
    source = {"schema_version": "milk.summary-source.v2", "scope_id": settings.scope_id, "profile": settings.profile, "summary_uuid": summary_uuid, "parent_summary_sha256": parent_sha256, "captures": source_rows}
    source_body = _zstd(canonical(source), False)
    source_key = settings.scope_prefix + f"s/{summary_uuid}/source.json.zst"
    store.create_same(source_key, source_body)
    summary_value = {"schema_version": "milk.summary.v2", "code_version": CODE_VERSION, "summary_uuid": summary_uuid, "scope_id": settings.scope_id, "profile": settings.profile, "created_at": created_at, "capture_count": len(processed) + len(rows), "source_high_water_key": max(selected_keys), "source_manifest_key": source_key, "source_manifest_sha256": digest(source_body), "parent_summary_key": parent_pointer.get("key") if parent_pointer else None, "parent_summary_sha256": parent_sha256, "config_digest": runtime.digest, "prompt_sha256": prompt_sha256, "model_binding_sha256": model_binding_sha256, "structural": cumulative_structural, "semantic": semantic}
    summary_body = canonical(summary_value)
    summary_sha256 = digest(summary_body)
    summary_key = settings.scope_prefix + f"s/{summary_uuid}/summary.json"
    store.create_same(summary_key, summary_body)
    readiness = _readiness(settings, summary_value, summary_sha256, enriched_labels)
    readiness_body = canonical(readiness)
    readiness_sha256 = digest(readiness_body)
    readiness_key = settings.scope_prefix + f"readiness/{readiness['readiness_uuid']}.json"
    store.create_same(readiness_key, readiness_body)
    summary_pointer = {"schema_version": "milk.pointer.v2", "kind": "summary", "scope_id": settings.scope_id, "uuid": summary_uuid, "key": summary_key, "sha256": summary_sha256, "capture_count": summary_value["capture_count"], "source_manifest_sha256": summary_value["source_manifest_sha256"]}
    readiness_pointer = {"schema_version": "milk.pointer.v2", "kind": "readiness", "scope_id": settings.scope_id, "uuid": readiness["readiness_uuid"], "key": readiness_key, "sha256": readiness_sha256, "summary_sha256": summary_sha256, "ready": readiness["ready"], "statistically_qualified": readiness["statistically_qualified"]}
    _advance(store, settings.scope_prefix + "s/current.json", summary_pointer)
    _advance(store, settings.scope_prefix + "readiness/current.json", readiness_pointer)
    artifacts = [{"key": key, "sha256": sha} for key, sha in ((source_key, digest(source_body)), (summary_key, summary_sha256), (readiness_key, readiness_sha256), (settings.scope_prefix + "s/current.json", digest(summary_pointer)), (settings.scope_prefix + "readiness/current.json", digest(readiness_pointer)))]
    return summary_pointer, summary_value, readiness_pointer, all_rows, processed | set(selected_keys), artifacts, inference_calls, job_id


def reconcile(store, settings, runtime) -> dict:
    state = inspect(store, settings)
    parent_pointer, unused_pointer_object, parent_summary = _read_pointer(store, settings.scope_prefix)
    prior_rows, processed = _ancestry(store, settings, parent_summary) if parent_summary else ([], set())
    all_keys = state["capture_keys"]
    artifacts, calls, job_ids = [], 0, []
    while True:
        next_threshold = next((value for value in thresholds(settings.profile) if value > len(processed)), None)
        if next_threshold is None:
            break
        unprocessed = [key for key in all_keys if key not in processed]
        needed = next_threshold - len(processed)
        if len(unprocessed) < needed:
            break
        selected = unprocessed[:needed]
        parent_pointer, parent_summary, readiness_pointer, prior_rows, processed, checkpoint_artifacts, inference_calls, job_id = _checkpoint(store, settings, runtime, parent_pointer, parent_summary, prior_rows, processed, selected)
        artifacts.extend(checkpoint_artifacts)
        calls += inference_calls
        job_ids.append(job_id)
    next_threshold = next((value for value in thresholds(settings.profile) if value > len(processed)), None)
    try:
        readiness_pointer = _json(store.get(settings.scope_prefix + "readiness/current.json").body, "readiness/current.json")
    except FileNotFoundError:
        readiness_pointer = None
    final_state = {"capture_count": len(all_keys), "processed_count": len(processed), "next_threshold": next_threshold, "summary_pointer": parent_pointer, "summary": parent_summary, "readiness_pointer": readiness_pointer, "next_action": "eval" if readiness_pointer and readiness_pointer.get("ready") else "summary"}
    status_value = _status(store, settings, final_state)
    status_key = settings.scope_prefix + "status/current.json"
    artifacts.append({"key": status_key, "sha256": digest(status_value)})
    identity = digest({"schema_version": "milk.summary-reconcile.v2", "scope_id": settings.scope_id, "config_digest": runtime.digest, "capture_keys": all_keys, "processed_keys": sorted(processed), "job_ids": job_ids})
    return {"state": "progressed" if job_ids else "idle", "identity": identity, "artifacts": artifacts, "inference_calls": calls, "provider_calls": 0, "next": final_state["next_action"], "details": {"capture_count": len(all_keys), "processed_count": len(processed), "next_threshold": next_threshold, "checkpoints": len(job_ids), "ready": bool(readiness_pointer and readiness_pointer.get("ready")), "statistically_qualified": bool(readiness_pointer and readiness_pointer.get("statistically_qualified"))}}
