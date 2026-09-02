from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random

import boto3
import torch
import zstandard
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_REPO = "Qwen/Qwen3.5-0.8B"
MODEL_REVISION = "2fc06364715b967f1860aea9cf38778875588b17"
MODEL_ROOT = "/models/qwen3.5-0.8b"


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


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def s3():
    return boto3.client(
        "s3",
        endpoint_url=required("MILK_STORE_ENDPOINT"),
        region_name=required("MILK_STORE_REGION"),
        aws_access_key_id=required("MILK_STORE_ACCESS_KEY_ID"),
        aws_secret_access_key=required("MILK_STORE_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("MILK_STORE_SESSION_TOKEN") or None,
    )


def get(client, key: str, expected: str) -> bytes:
    body = client.get_object(Bucket=required("MILK_STORE_BUCKET"), Key=key)["Body"].read()
    if sha256(body) != expected:
        raise ValueError(f"{key} digest differs")
    return body


def dataset() -> tuple[dict, list[dict]]:
    client = s3()
    manifest = json.loads(
        get(client, required("MILK_DATASET_MANIFEST_KEY"), required("MILK_DATASET_MANIFEST_SHA256"))
    )
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") not in {"milk.dataset.v2", "milk.dataset.v3"}
        or manifest.get("scope_id") != required("MILK_SCOPE_ID")
        or manifest.get("student_base", {}).get("model_repo") != MODEL_REPO
        or manifest.get("student_base", {}).get("model_revision") != MODEL_REVISION
    ):
        raise ValueError("dataset manifest identity differs")
    train = manifest.get("objects", {}).get("train")
    if not isinstance(train, dict) or set(train) != {"key", "sha256", "content_sha256", "count"}:
        raise ValueError("dataset train object is invalid")
    compressed = get(client, train["key"], train["sha256"])
    plain = zstandard.ZstdDecompressor().decompress(compressed, max_output_size=64 * 1024 * 1024)
    if sha256(plain) != train["content_sha256"]:
        raise ValueError("dataset train content digest differs")
    rows = [json.loads(line) for line in plain.splitlines() if line]
    if len(rows) != train["count"] or not rows:
        raise ValueError("dataset train count differs")
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("schema_version") != "milk.training-example.v2"
            or row.get("split") != "train"
            or not isinstance(row.get("input"), str)
            or not isinstance(row.get("target"), str)
            or not row["input"]
            or not row["target"]
        ):
            raise ValueError("dataset contains an invalid training example")
    return manifest, rows


def tokens(tokenizer, row: dict, maximum: int) -> tuple[torch.Tensor, torch.Tensor]:
    messages = [{"role": "user", "content": row["input"]}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    full = prompt + row["target"] + (tokenizer.eos_token or "")
    encoded = tokenizer(full, return_tensors="pt", truncation=True, max_length=maximum)
    prompt_length = len(tokenizer(prompt, truncation=True, max_length=maximum)["input_ids"])
    labels = encoded["input_ids"].clone()
    labels[:, : min(prompt_length, labels.shape[1])] = -100
    if torch.all(labels == -100):
        raise ValueError("training target was truncated")
    return encoded["input_ids"].cuda(), labels.cuda()


def inventory(root: Path) -> list[dict]:
    result = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                digest.update(block)
        result.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    return result


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    job_id = required("MILK_TRAIN_JOB_ID")
    steps = integer("MILK_TRAIN_STEPS", 1, 1, 1024)
    maximum = integer("MILK_TRAIN_MAX_TOKENS", 2048, 128, 8192)
    try:
        learning_rate = float(os.environ.get("MILK_TRAIN_LEARNING_RATE", "2e-6"))
    except ValueError as error:
        raise ValueError("MILK_TRAIN_LEARNING_RATE must be numeric") from error
    if not 0 < learning_rate <= 1e-3:
        raise ValueError("MILK_TRAIN_LEARNING_RATE is outside the reviewed range")

    seed = int(job_id[:16], 16)
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    manifest, rows = dataset()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ROOT, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ROOT,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    ).cuda()
    model.config.use_cache = False
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    losses = []
    for step in range(steps):
        input_ids, labels = tokens(tokenizer, rows[step % len(rows)], maximum)
        optimizer.zero_grad(set_to_none=True)
        loss = model(input_ids=input_ids, labels=labels).loss
        if not torch.isfinite(loss):
            raise RuntimeError("training loss is not finite")
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))

    output = Path(os.environ.get("BT_CHECKPOINT_DIR", "/mnt/ckpts")) / "merged"
    output.mkdir(parents=True, exist_ok=True)
    model.eval()
    model.save_pretrained(output, safe_serialization=True, max_shard_size="4GB")
    tokenizer.save_pretrained(output)
    files = inventory(output)
    result = {
        "schema_version": "milk.training-output.v2",
        "job_id": job_id,
        "dataset_uuid": manifest["dataset_uuid"],
        "student_base": {"model_repo": MODEL_REPO, "model_revision": MODEL_REVISION},
        "steps": steps,
        "examples": len(rows),
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "files": files,
    }
    (output / "milk-result.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({key: result[key] for key in ("schema_version", "job_id", "dataset_uuid", "steps", "examples", "loss_first", "loss_last")}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
