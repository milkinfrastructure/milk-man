from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re

import boto3
from botocore.exceptions import ClientError
import torch
import zstandard
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_REPO = "Qwen/Qwen3.5-0.8B"
MODEL_REVISION = "2fc06364715b967f1860aea9cf38778875588b17"
INFERENCE_BATCH_CASES = 64
RESULT_SHARD_CASES = 256
SCHEMA_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})
SCHEMA_MAX_DEPTH = 16


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} is required")
    return value


def integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in {minimum}..{maximum}")
    return value


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def client():
    return boto3.client(
        "s3",
        endpoint_url=required("MILK_STORE_ENDPOINT"),
        region_name=required("MILK_STORE_REGION"),
        aws_access_key_id=required("MILK_STORE_ACCESS_KEY_ID"),
        aws_secret_access_key=required("MILK_STORE_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("MILK_STORE_SESSION_TOKEN") or None,
    )


def get(store, key: str, expected: str) -> bytes:
    body = store.get_object(Bucket=required("MILK_STORE_BUCKET"), Key=key)["Body"].read()
    if digest(body) != expected:
        raise ValueError(f"{key} digest differs")
    return body


def create_same(store, key: str, body: bytes) -> None:
    bucket = required("MILK_STORE_BUCKET")
    try:
        store.put_object(Bucket=bucket, Key=key, Body=body, IfNoneMatch="*")
        return
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", ""))
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code not in {"PreconditionFailed", "ConditionalRequestConflict"} and status not in {409, 412}:
            raise
    if store.get_object(Bucket=bucket, Key=key)["Body"].read() != body:
        raise ValueError(f"{key} already contains different bytes")


def _hex_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _eval_normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _object_rows(store, source: dict, split: str, start: int | None = None, end: int | None = None, eval_uuid: str | None = None, validation: dict | None = None):
    compressed = get(store, source["key"], source["sha256"])
    try:
        plain = zstandard.ZstdDecompressor().decompress(compressed, max_output_size=64 * 1024 * 1024)
    except zstandard.ZstdError as error:
        raise ValueError("dataset split compression is invalid") from error
    if digest(plain) != source["content_sha256"]:
        raise ValueError("dataset split content digest differs")
    lines = [line for line in plain.splitlines() if line]
    if len(lines) != source["count"] or not lines:
        raise ValueError("dataset split count differs")
    previous_order = None
    for offset, line in enumerate(lines):
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("dataset contains invalid JSON") from error
        order = value.get("order") if isinstance(value, dict) else None
        oracle = value.get("oracle") if isinstance(value, dict) else None
        expected = value.get("expected") if isinstance(value, dict) else None
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != "milk.eval-case.v2"
            or value.get("split") != split
            or oracle not in {"exact", "reference", "schema"}
            or not isinstance(value.get("case_id"), str)
            or (eval_uuid is not None and value.get("case_id") != digest(f"{eval_uuid}\0{order}".encode()))
            or not isinstance(value.get("input"), str)
            or not value["input"]
            or (oracle in {"exact", "reference"} and not isinstance(expected, str))
            or (oracle == "schema" and not schema_oracle_valid(expected))
            or not isinstance(order, int)
            or isinstance(order, bool)
            or order < 0
            or (start is not None and order != start + offset)
            or (previous_order is not None and order <= previous_order)
        ):
            raise ValueError("dataset contains an invalid eval case")
        if validation is not None and validation["normalized_hashes"][offset] != {
            "case_id": value["case_id"],
            "input_sha256": digest(_eval_normalized(value["input"]).encode()),
        }:
            raise ValueError("dataset shard validation differs from its cases")
        previous_order = order
        yield value
    if start is not None and end != start + len(lines):
        raise ValueError("dataset shard range differs")


def _v3_shards(manifest: dict, split: str) -> list[dict]:
    objects = manifest.get("objects", {})
    source = objects.get(split) if isinstance(objects, dict) else None
    if not isinstance(source, dict) or set(source) != {"count", "root_sha256", "shards"}:
        raise ValueError("dataset split shards are invalid")
    count, root, shards = source["count"], source["root_sha256"], source["shards"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 1 or not _hex_digest(root) or not isinstance(shards, list) or not shards:
        raise ValueError("dataset split shards are invalid")
    preceding = [objects.get(name) for name in ("dev", "calibration", "sealed")[:("dev", "calibration", "sealed").index(split)]]
    if any(not isinstance(value, dict) or type(value.get("count")) is not int or value["count"] < 1 for value in preceding):
        raise ValueError("dataset split ranges are invalid")
    split_start = sum(value["count"] for value in preceding)
    expected_fields = {"split", "start", "end", "count", "key", "sha256", "content_sha256", "validation_key", "validation_sha256"}
    prior_end = split_start
    total = 0
    for shard in shards:
        if not isinstance(shard, dict) or set(shard) != expected_fields:
            raise ValueError("dataset shard descriptor is invalid")
        start, end, shard_count = shard["start"], shard["end"], shard["count"]
        prefix = (
            f"milk/v2/scopes/{manifest.get('scope_id', '')}/e/{manifest.get('eval_uuid', '')}/shards/{split}/{start:09d}-{end:09d}/"
            if isinstance(start, int) and not isinstance(start, bool) and isinstance(end, int) and not isinstance(end, bool)
            else ""
        )
        if (
            shard["split"] != split
            or not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or not isinstance(shard_count, int)
            or isinstance(shard_count, bool)
            or not 0 <= start < end
            or shard_count != end - start
            or start != prior_end
            or shard["key"] != prefix + "cases.jsonl.zst"
            or shard["validation_key"] != prefix + "validation.json"
            or not _hex_digest(shard["sha256"])
            or not _hex_digest(shard["content_sha256"])
            or not _hex_digest(shard["validation_sha256"])
        ):
            raise ValueError("dataset shard descriptor is invalid")
        prior_end = end
        total += shard_count
    if total != count or prior_end != split_start + count or digest(canonical(shards)) != root:
        raise ValueError("dataset split shard identity differs")
    return shards


def _v3_validation(store, manifest: dict, shard: dict) -> dict:
    try:
        value = json.loads(get(store, shard["validation_key"], shard["validation_sha256"]))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("dataset shard validation is invalid") from error
    case_ids = [digest(f"{manifest['eval_uuid']}\0{order}".encode()) for order in range(shard["start"], shard["end"])]
    hashes = value.get("normalized_hashes") if isinstance(value, dict) else None
    verdicts = value.get("verdicts") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "eval_uuid", "revision_sha256", "split", "start", "end", "accepted", "case_count", "cases_sha256", "cases_content_sha256", "normalized_hashes", "normalized_ledger_sha256", "verdicts"}
        or value.get("schema_version") != "milk.eval-validation-shard.v3"
        or value.get("eval_uuid") != manifest.get("eval_uuid")
        or value.get("revision_sha256") != manifest.get("eval_revision_sha256")
        or value.get("split") != shard["split"]
        or value.get("start") != shard["start"]
        or value.get("end") != shard["end"]
        or value.get("accepted") is not True
        or value.get("case_count") != shard["count"]
        or value.get("cases_sha256") != shard["sha256"]
        or value.get("cases_content_sha256") != shard["content_sha256"]
        or not _hex_digest(value.get("normalized_ledger_sha256"))
        or not isinstance(hashes, list)
        or len(hashes) != shard["count"]
        or [item.get("case_id") for item in hashes if isinstance(item, dict)] != case_ids
        or any(set(item) != {"case_id", "input_sha256"} or not _hex_digest(item.get("input_sha256")) for item in hashes if isinstance(item, dict))
        or len({item["input_sha256"] for item in hashes if isinstance(item, dict)}) != shard["count"]
        or not isinstance(verdicts, list)
        or len(verdicts) != shard["count"]
        or any(not isinstance(item, dict) or set(item) != {"case_id", "accepted", "reason"} for item in verdicts)
        or [item.get("case_id") for item in verdicts if isinstance(item, dict) and item.get("accepted") is True and item.get("reason") == "accepted"] != case_ids
    ):
        raise ValueError("dataset shard validation identity differs")
    return value


def rows(split: str):
    store = client()
    manifest = json.loads(get(store, required("MILK_DATASET_MANIFEST_KEY"), required("MILK_DATASET_MANIFEST_SHA256")))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") not in {"milk.dataset.v2", "milk.dataset.v3"}
        or manifest.get("scope_id") != required("MILK_SCOPE_ID")
        or manifest.get("student_base", {}).get("model_repo") != MODEL_REPO
        or manifest.get("student_base", {}).get("model_revision") != MODEL_REVISION
    ):
        raise ValueError("dataset manifest identity differs")
    if split not in {"dev", "calibration", "sealed"}:
        raise ValueError("MILK_EVALUATE_SPLIT is invalid")
    if manifest["schema_version"] == "milk.dataset.v2":
        source = manifest.get("objects", {}).get(split)
        if not isinstance(source, dict) or set(source) != {"key", "sha256", "content_sha256", "count"}:
            raise ValueError("dataset split object is invalid")
        return manifest, _object_rows(store, source, split)

    shards = _v3_shards(manifest, split)

    def values():
        for shard in shards:
            validation = _v3_validation(store, manifest, shard)
            yield from _object_rows(store, shard, split, shard["start"], shard["end"], manifest["eval_uuid"], validation)

    return manifest, values()


def prompt(tokenizer, value: str) -> str:
    return tokenizer.apply_chat_template(
        [{"role": "user", "content": value}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )


def quantize(model, tokenizer, branch: str, manifest: dict) -> dict:
    if branch == "bf16":
        return {"kind": "bf16", "quantized_linear_count": 0}
    from torchao.quantization import (
        Float8DynamicActivationFloat8WeightConfig,
        Float8StaticActivationFloat8WeightConfig,
        quantize_,
    )

    if branch == "dynamic_fp8":
        quantize_(model, Float8DynamicActivationFloat8WeightConfig())
        scale = None
        calibration = {}
    elif branch == "static_fp8":
        calibration_manifest, calibration = rows("calibration")
        if calibration_manifest["dataset_uuid"] != manifest["dataset_uuid"]:
            raise ValueError("calibration dataset identity differs")
        maximum = None

        def observe(unused_module, args):
            nonlocal maximum
            value = args[0].detach().abs().amax().float()
            maximum = value if maximum is None else torch.maximum(maximum, value)

        hooks = [
            module.register_forward_pre_hook(observe)
            for module in model.modules()
            if isinstance(module, torch.nn.Linear)
        ]
        calibration_ids = hashlib.sha256()
        calibration_count = 0
        try:
            for batch in _batches(calibration, INFERENCE_BATCH_CASES):
                for row in batch:
                    if not _hex_digest(row["case_id"]):
                        raise ValueError("calibration case ID is invalid")
                    calibration_ids.update(bytes.fromhex(row["case_id"]))
                    calibration_count += 1
                encoded = tokenizer([prompt(tokenizer, row["input"]) for row in batch], return_tensors="pt", padding=True).to("cuda")
                with torch.no_grad():
                    model(**encoded, use_cache=False)
        finally:
            for hook in hooks:
                hook.remove()
        if maximum is None:
            raise ValueError("calibration observed no linear activations")
        scale = torch.clamp(maximum / torch.finfo(torch.float8_e4m3fn).max, min=torch.finfo(torch.float32).eps)
        quantize_(model, Float8StaticActivationFloat8WeightConfig(scale=scale))
        calibration = {
            "calibration_case_count": calibration_count,
            "calibration_case_ids_sha256": calibration_ids.hexdigest(),
        }
    else:
        raise ValueError("MILK_EVALUATE_BRANCH is invalid")

    quantized = sum(
        1
        for module in model.modules()
        if isinstance(module, torch.nn.Linear) and module.weight.__class__.__module__.startswith("torchao.")
    )
    if quantized == 0:
        raise ValueError(f"{branch} quantized no linear modules")
    return {
        "kind": branch,
        "torchao_version": "0.15.0",
        "quantized_linear_count": quantized,
        **calibration,
        **({"activation_scale": float(scale.item())} if scale is not None else {}),
    }


def _write_result_shard(store, prefix: str, split: str, values: list[dict]) -> dict:
    if not values or len(values) > RESULT_SHARD_CASES:
        raise ValueError("evaluation result shard count is invalid")
    start = values[0].get("order")
    if type(start) is not int:
        raise ValueError("evaluation result shard order differs")
    end = start + len(values)
    if [value.get("order") for value in values] != list(range(start, end)):
        raise ValueError("evaluation result shard order differs")
    plain = b"".join(canonical(value) for value in values)
    body = zstandard.ZstdCompressor(level=3).compress(plain)
    key = prefix + f"{start:09d}-{end:09d}/rows.jsonl.zst"
    create_same(store, key, body)
    return _result_descriptor(key, split, start, end, body, plain)


def _result_descriptor(key: str, split: str, start: int, end: int, body: bytes, plain: bytes) -> dict:
    return {
        "split": split,
        "start": start,
        "end": end,
        "count": end - start,
        "key": key,
        "sha256": digest(body),
        "content_sha256": digest(plain),
    }


def _prior_result_shard(store, prefix: str, split: str, inputs: list[dict], maximum: int) -> tuple[dict, list[dict]] | None:
    start = inputs[0]["order"]
    if type(start) is not int:
        raise ValueError("evaluation input batch order differs")
    end = start + len(inputs)
    if [value.get("order") for value in inputs] != list(range(start, end)):
        raise ValueError("evaluation input batch order differs")
    key = prefix + f"{start:09d}-{end:09d}/rows.jsonl.zst"
    try:
        body = store.get_object(Bucket=required("MILK_STORE_BUCKET"), Key=key)["Body"].read()
    except ClientError as error:
        code = str(error.response.get("Error", {}).get("Code", ""))
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"NoSuchKey", "NotFound", "404"} or status == 404:
            return None
        raise
    try:
        plain = zstandard.ZstdDecompressor().decompress(body, max_output_size=64 * 1024 * 1024)
        values = [json.loads(line) for line in plain.splitlines()]
    except (zstandard.ZstdError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("stored evaluation result shard is invalid") from error
    if not values or len(values) != len(inputs) or b"".join(canonical(value) for value in values) != plain:
        raise ValueError("stored evaluation result shard content differs")
    fields = {"case_id", "order", "score_bps", "candidate", "response_sha256", "latency_ms", "output_tokens"}
    for source, value in zip(inputs, values):
        candidate = value.get("candidate") if isinstance(value, dict) else None
        if (
            not isinstance(value, dict)
            or set(value) != fields
            or value.get("case_id") != source["case_id"]
            or value.get("order") != source["order"]
            or not isinstance(candidate, str)
            or value.get("response_sha256") != digest(candidate.encode())
            or type(value.get("score_bps")) is not int
            or not 0 <= value["score_bps"] <= 10_000
            or value.get("score_bps") != score(source, candidate)
            or type(value.get("latency_ms")) is not int
            or value["latency_ms"] < 1
            or type(value.get("output_tokens")) is not int
            or not 0 <= value["output_tokens"] <= maximum
        ):
            raise ValueError("stored evaluation result row differs")
    return _result_descriptor(key, split, start, end, body, plain), values


def _batches(values, count: int):
    batch = []
    for value in values:
        batch.append(value)
        if len(batch) == count:
            yield batch
            batch = []
    if batch:
        yield batch


def _batch_latencies(elapsed_ms: float, count: int) -> list[int]:
    if count < 1 or not math.isfinite(elapsed_ms) or elapsed_ms < 0:
        raise ValueError("evaluation batch timing is invalid")
    total = max(count, math.ceil(elapsed_ms))
    quotient, remainder = divmod(total, count)
    return [quotient + (index < remainder) for index in range(count)]


def model_root() -> Path:
    root = Path(os.environ.get("BT_LOAD_CHECKPOINT_DIR", "/app/checkpoint"))
    candidates = []
    for config in root.glob("**/config.json"):
        try:
            relative = config.relative_to(root)
        except ValueError:
            continue
        parent = config.parent
        if len(relative.parts) <= 5 and (parent / "tokenizer_config.json").is_file() and any(parent.glob("*.safetensors")):
            candidates.append(parent)
    if len(candidates) != 1:
        raise ValueError("loaded checkpoint has no unique merged model")
    return candidates[0]


def normalized(value: str) -> list[str]:
    return "".join(character.lower() if character.isalnum() else " " for character in value).split()


def similarity(reference: str, candidate: str) -> float:
    left, right = normalized(reference), normalized(candidate)
    if len(left) * len(right) > 4_000_000:
        raise ValueError("reference comparison exceeds its work bound")
    prior = list(range(len(right) + 1))
    for row_index, left_token in enumerate(left, 1):
        current = [row_index]
        for column_index, right_token in enumerate(right, 1):
            current.append(min(current[-1] + 1, prior[column_index] + 1, prior[column_index - 1] + (left_token != right_token)))
        prior = current
    return max(0.0, 1.0 - prior[-1] / max(len(left), len(right), 1))


def schema_type_matches(expected: str, value: object) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and math.isfinite(value)),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }[expected]


def schema_oracle_valid(schema: object, depth: int = 0) -> bool:
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
        if expected in {"object", "array"} or not isinstance(options, list) or not options or any(not schema_type_matches(expected, value) for value in options):
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
            and all(isinstance(key, str) and schema_oracle_valid(value, depth + 1) for key, value in properties.items())
            and isinstance(required, list)
            and all(isinstance(key, str) for key in required)
            and len(set(required)) == len(required)
            and all(key in properties for key in required)
            and isinstance(additional, bool)
        )
    return expected != "array" or "items" not in schema or schema_oracle_valid(schema["items"], depth + 1)


def schema_match(schema: object, value: object) -> bool:
    if not schema_oracle_valid(schema) or not schema_type_matches(schema["type"], value):
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
        return all(key not in value or schema_match(child, value[key]) for key, child in properties.items())
    if isinstance(value, list) and "items" in schema:
        return all(schema_match(schema["items"], item) for item in value)
    return True


def unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def finite_json_float(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    return value


def invalid_json_constant(value: str):
    raise ValueError(f"invalid JSON constant: {value}")


def strict_json(value: str):
    return json.loads(value, object_pairs_hook=unique_json_object, parse_float=finite_json_float, parse_constant=invalid_json_constant)


def score(row: dict, candidate: str) -> int:
    expected = row.get("expected")
    if row["oracle"] == "exact":
        return 10_000 if isinstance(expected, str) and candidate.strip() == expected.strip() else 0
    if row["oracle"] == "reference":
        return int(similarity(expected, candidate) * 10_000) if isinstance(expected, str) else 0
    try:
        value = strict_json(candidate)
    except (UnicodeDecodeError, ValueError):
        return 0
    return 10_000 if schema_match(expected, value) else 0


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    scope_id = required("MILK_SCOPE_ID")
    job_id = required("MILK_EVALUATE_JOB_ID")
    branch = required("MILK_EVALUATE_BRANCH")
    if branch not in {"bf16", "dynamic_fp8", "static_fp8"}:
        raise ValueError("MILK_EVALUATE_BRANCH is invalid")
    maximum = integer("MILK_EVALUATE_MAX_NEW_TOKENS", 256, 1, 2048)
    split = required("MILK_EVALUATE_SPLIT")
    manifest, cases = rows(split)
    checkpoint = model_root()
    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    tokenizer.padding_side = "left"
    if type(tokenizer.eos_token_id) is not int:
        raise ValueError("tokenizer has no usable EOS token")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    model = AutoModelForCausalLM.from_pretrained(checkpoint, local_files_only=True, torch_dtype=torch.bfloat16).cuda().eval()
    quantization = quantize(model, tokenizer, branch, manifest)
    result_prefix = f"milk/v2/scopes/{scope_id}/j/evaluate/{job_id}/results/{split}/"
    result_store = client()
    result_shards = []
    case_ids = hashlib.sha256()
    case_count = score_total = latency_total = total_output_tokens = 0
    latencies = []
    for input_batch in _batches(cases, RESULT_SHARD_CASES):
        prior = _prior_result_shard(result_store, result_prefix, split, input_batch, maximum)
        if prior is None:
            result_buffer = []
            for inference_batch in _batches(input_batch, INFERENCE_BATCH_CASES):
                encoded = tokenizer([prompt(tokenizer, row["input"]) for row in inference_batch], return_tensors="pt", padding=True).to("cuda")
                torch.cuda.synchronize()
                started = torch.cuda.Event(enable_timing=True)
                finished = torch.cuda.Event(enable_timing=True)
                started.record()
                with torch.no_grad():
                    generated = model.generate(**encoded, do_sample=False, max_new_tokens=maximum, pad_token_id=tokenizer.pad_token_id)
                finished.record()
                torch.cuda.synchronize()
                batch_latencies = _batch_latencies(started.elapsed_time(finished), len(inference_batch))
                prompt_tokens = encoded["input_ids"].shape[1]
                for index, (row, latency_ms) in enumerate(zip(inference_batch, batch_latencies)):
                    token_ids = generated[index, prompt_tokens:].tolist()
                    generated_tokens = token_ids.index(tokenizer.eos_token_id) + 1 if tokenizer.eos_token_id in token_ids else len(token_ids)
                    candidate = tokenizer.decode(token_ids[:generated_tokens], skip_special_tokens=True)
                    result_buffer.append({
                        "case_id": row["case_id"],
                        "order": row["order"],
                        "score_bps": score(row, candidate),
                        "candidate": candidate,
                        "response_sha256": digest(candidate.encode()),
                        "latency_ms": latency_ms,
                        "output_tokens": generated_tokens,
                    })
            descriptor = _write_result_shard(result_store, result_prefix, split, result_buffer)
        else:
            descriptor, result_buffer = prior
        result_shards.append(descriptor)
        for result in result_buffer:
            if not _hex_digest(result["case_id"]):
                raise ValueError("evaluation case ID is invalid")
            case_ids.update(bytes.fromhex(result["case_id"]))
            case_count += 1
            score_total += result["score_bps"]
            latency_total += result["latency_ms"]
            total_output_tokens += result["output_tokens"]
            latencies.append(result["latency_ms"])
    expected_count = manifest.get("objects", {}).get(split, {}).get("count")
    if case_count != expected_count or case_count < 1:
        raise ValueError("evaluation result count differs")
    latencies.sort()
    output = {
        "schema_version": "milk.evaluation-output.v3",
        "job_id": job_id,
        "scope_id": scope_id,
        "dataset_uuid": manifest["dataset_uuid"],
        "model_uuid": required("MILK_MODEL_UUID"),
        "student_base": {"model_repo": MODEL_REPO, "model_revision": MODEL_REVISION},
        "branch": branch,
        "split": split,
        "case_count": case_count,
        "case_ids_sha256": case_ids.hexdigest(),
        "inference_batch_case_count": INFERENCE_BATCH_CASES,
        "result_shard_case_count": RESULT_SHARD_CASES,
        "result_shard_count": len(result_shards),
        "result_shards_sha256": digest(canonical(result_shards)),
        "result_shards": result_shards,
        "quantization": quantization,
        "metrics": {
            "mean_score_bps": score_total // case_count,
            "errors": 0,
            "p95_latency_ms": latencies[(len(latencies) * 95 + 99) // 100 - 1],
            "total_latency_ms": latency_total,
            "output_tokens": total_output_tokens,
            "tokens_per_second": round(total_output_tokens * 1000 / latency_total, 3),
        },
    }
    destination = Path(os.environ.get("BT_CHECKPOINT_DIR", "/mnt/ckpts")) / "evaluation"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "milk-result.json").write_text(json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({key: output[key] for key in ("schema_version", "job_id", "dataset_uuid", "model_uuid", "branch", "split", "metrics")}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
