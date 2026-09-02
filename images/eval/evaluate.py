from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time

import boto3
import torch
import zstandard
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_REPO = "Qwen/Qwen3.5-0.8B"
MODEL_REVISION = "2fc06364715b967f1860aea9cf38778875588b17"


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


def rows(split: str) -> tuple[dict, list[dict]]:
    store = client()
    manifest = json.loads(get(store, required("MILK_DATASET_MANIFEST_KEY"), required("MILK_DATASET_MANIFEST_SHA256")))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "milk.dataset.v2"
        or manifest.get("scope_id") != required("MILK_SCOPE_ID")
        or manifest.get("student_base", {}).get("model_repo") != MODEL_REPO
        or manifest.get("student_base", {}).get("model_revision") != MODEL_REVISION
    ):
        raise ValueError("dataset manifest identity differs")
    if split not in {"dev", "calibration", "sealed"}:
        raise ValueError("MILK_EVALUATE_SPLIT is invalid")
    source = manifest.get("objects", {}).get(split)
    if not isinstance(source, dict) or set(source) != {"key", "sha256", "content_sha256", "count"}:
        raise ValueError("dataset split object is invalid")
    compressed = get(store, source["key"], source["sha256"])
    plain = zstandard.ZstdDecompressor().decompress(compressed, max_output_size=64 * 1024 * 1024)
    if digest(plain) != source["content_sha256"]:
        raise ValueError("dataset split content digest differs")
    values = [json.loads(line) for line in plain.splitlines() if line]
    if len(values) != source["count"] or not values:
        raise ValueError("dataset split count differs")
    orders = [value.get("order") for value in values]
    if any(not isinstance(order, int) or isinstance(order, bool) or order < 0 for order in orders) or orders != sorted(set(orders)):
        raise ValueError("dataset split order differs")
    for value in values:
        if (
            value.get("schema_version") != "milk.eval-case.v2"
            or value.get("split") != split
            or value.get("oracle") not in {"exact", "reference", "schema"}
            or not isinstance(value.get("case_id"), str)
            or not isinstance(value.get("input"), str)
            or not value["input"]
        ):
            raise ValueError("dataset contains an invalid eval case")
    return manifest, values


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
        calibration_ids = []
        scale = None
    elif branch == "static_fp8":
        calibration_manifest, calibration = rows("calibration")
        if calibration_manifest["dataset_uuid"] != manifest["dataset_uuid"]:
            raise ValueError("calibration dataset identity differs")
        maxima = []
        hooks = [
            module.register_forward_pre_hook(lambda unused_module, args: maxima.append(args[0].detach().abs().amax().float()))
            for module in model.modules()
            if isinstance(module, torch.nn.Linear)
        ]
        try:
            for row in calibration:
                encoded = tokenizer(prompt(tokenizer, row["input"]), return_tensors="pt").to("cuda")
                with torch.inference_mode():
                    model(**encoded, use_cache=False)
        finally:
            for hook in hooks:
                hook.remove()
        if not maxima:
            raise ValueError("calibration observed no linear activations")
        maximum = torch.stack(maxima).amax()
        scale = torch.clamp(maximum / torch.finfo(torch.float8_e4m3fn).max, min=torch.finfo(torch.float32).eps)
        quantize_(model, Float8StaticActivationFloat8WeightConfig(scale=scale))
        calibration_ids = [row["case_id"] for row in calibration]
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
        "calibration_case_ids": calibration_ids,
        **({"activation_scale": float(scale.item())} if scale is not None else {}),
    }


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


def schema_match(schema: object, value: object) -> bool:
    if not isinstance(schema, dict):
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    expected_type = schema.get("type")
    type_matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if expected_type is not None and not type_matches.get(expected_type, False):
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


def score(row: dict, candidate: str) -> int:
    expected = row.get("expected")
    if row["oracle"] == "exact":
        return 10_000 if isinstance(expected, str) and candidate.strip() == expected.strip() else 0
    if row["oracle"] == "reference":
        return int(similarity(expected, candidate) * 10_000) if isinstance(expected, str) else 0
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return 0
    return 10_000 if schema_match(expected, value) else 0


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    job_id = required("MILK_EVALUATE_JOB_ID")
    branch = required("MILK_EVALUATE_BRANCH")
    if branch not in {"bf16", "dynamic_fp8", "static_fp8"}:
        raise ValueError("MILK_EVALUATE_BRANCH is invalid")
    maximum = integer("MILK_EVALUATE_MAX_NEW_TOKENS", 256, 1, 2048)
    split = required("MILK_EVALUATE_SPLIT")
    manifest, cases = rows(split)
    checkpoint = model_root()
    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(checkpoint, local_files_only=True, torch_dtype=torch.bfloat16).cuda().eval()
    quantization = quantize(model, tokenizer, branch, manifest)
    results = []
    started_all = time.monotonic()
    for row in cases:
        encoded = tokenizer(prompt(tokenizer, row["input"]), return_tensors="pt").to("cuda")
        torch.cuda.synchronize()
        started = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(**encoded, do_sample=False, max_new_tokens=maximum, pad_token_id=tokenizer.eos_token_id)
        torch.cuda.synchronize()
        latency_ms = max(1, int((time.monotonic() - started) * 1000))
        output_tokens = generated.shape[1] - encoded["input_ids"].shape[1]
        candidate = tokenizer.decode(generated[0, encoded["input_ids"].shape[1]:], skip_special_tokens=True)
        results.append(
            {
                "case_id": row["case_id"],
                "order": row["order"],
                "score_bps": score(row, candidate),
                "candidate": candidate,
                "response_sha256": digest(candidate.encode()),
                "latency_ms": latency_ms,
                "output_tokens": output_tokens,
            }
        )
    latencies = sorted(result["latency_ms"] for result in results)
    total_ms = max(1, int((time.monotonic() - started_all) * 1000))
    output_tokens = sum(result["output_tokens"] for result in results)
    output = {
        "schema_version": "milk.evaluation-output.v2",
        "job_id": job_id,
        "scope_id": required("MILK_SCOPE_ID"),
        "dataset_uuid": manifest["dataset_uuid"],
        "model_uuid": required("MILK_MODEL_UUID"),
        "student_base": {"model_repo": MODEL_REPO, "model_revision": MODEL_REVISION},
        "branch": branch,
        "split": split,
        "quantization": quantization,
        "case_ids": [row["case_id"] for row in cases],
        "rows": results,
        "metrics": {
            "mean_score_bps": sum(result["score_bps"] for result in results) // len(results),
            "errors": 0,
            "p95_latency_ms": latencies[(len(latencies) * 95 + 99) // 100 - 1],
            "total_latency_ms": sum(latencies),
            "output_tokens": output_tokens,
            "tokens_per_second": round(output_tokens * 1000 / total_ms, 3),
        },
    }
    destination = Path(os.environ.get("BT_CHECKPOINT_DIR", "/mnt/ckpts")) / "evaluation"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "milk-result.json").write_text(json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({key: output[key] for key in ("schema_version", "job_id", "dataset_uuid", "model_uuid", "branch", "split", "metrics")}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
