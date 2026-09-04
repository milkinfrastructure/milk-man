from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random

import boto3
import torch
import torch.nn.functional as F
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


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


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


def reinforce_step(model, tokenizer, row: dict, optimizer, maximum: int) -> tuple[float, dict]:
    count = integer("MILK_TRAIN_ROLLOUTS", 4, 2, 16)
    new_tokens = integer("MILK_TRAIN_ROLLOUT_MAX_NEW_TOKENS", 256, 1, 1024)
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": row["input"]}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=maximum).to("cuda")
    if not isinstance(tokenizer.eos_token_id, int):
        raise ValueError("tokenizer has no usable EOS token")
    model.eval()
    model.config.use_cache = True
    with torch.no_grad():
        generated = model.generate(
            **encoded,
            do_sample=True,
            temperature=1.0,
            top_p=1.0,
            top_k=0,
            num_return_sequences=count,
            max_new_tokens=new_tokens,
            pad_token_id=tokenizer.eos_token_id,
        )
    model.config.use_cache = False
    prompt_tokens = encoded["input_ids"].shape[1]
    attention_mask = torch.zeros_like(generated)
    attention_mask[:, :prompt_tokens] = 1
    rewards = []
    rollouts = []
    for index, token_ids in enumerate(generated[:, prompt_tokens:]):
        values = token_ids.tolist()
        length = values.index(tokenizer.eos_token_id) + 1 if tokenizer.eos_token_id in values else len(values)
        attention_mask[index, prompt_tokens:prompt_tokens + length] = 1
        candidate = tokenizer.decode(values[:length], skip_special_tokens=True)
        reward_bps = int(similarity(row["target"], candidate) * 10_000)
        rewards.append(reward_bps / 10_000)
        rollouts.append({"response_sha256": sha256(candidate.encode()), "reward_bps": reward_bps, "output_tokens": length})

    logits = model(input_ids=generated, attention_mask=attention_mask, use_cache=False).logits[:, :-1].float()
    targets = generated[:, 1:]
    token_log_prob = F.log_softmax(logits, dim=-1).gather(-1, targets.unsqueeze(-1)).squeeze(-1)
    positions = torch.arange(1, generated.shape[1], device=generated.device)
    completion_mask = attention_mask[:, 1:].bool() & (positions >= prompt_tokens)
    sequence_log_prob = (token_log_prob * completion_mask).sum(1) / completion_mask.sum(1).clamp_min(1)
    reward = torch.tensor(rewards, dtype=torch.float32, device=generated.device)
    centered = reward - reward.mean()
    deviation = torch.sqrt(torch.mean(centered.square()))
    if deviation.item() == 0:
        loss_value = 0.0
        updated = False
        skip_reason = "zero_reward_variance"
    else:
        loss = -((centered / deviation).detach() * sequence_log_prob).mean()
        if not torch.isfinite(loss):
            raise RuntimeError("reinforce policy loss is not finite")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        loss_value = float(loss.detach().cpu())
        updated = True
        skip_reason = None
    return loss_value, {
        "source_request_sha256": row["source_request_sha256"],
        "prompt_sha256": sha256(prompt.encode()),
        "rollout_count": count,
        "rollouts": rollouts,
        "rollouts_sha256": sha256(canonical(rollouts)),
        "reward_mean_bps": round(sum(item["reward_bps"] for item in rollouts) / count, 3),
        "reward_std_bps": round(float(deviation.detach().cpu()) * 10_000, 3),
        "policy_loss": loss_value,
        "updated": updated,
        "skip_reason": skip_reason,
        "sampling": {"temperature": 1.0, "top_p": 1.0, "top_k": 0, "max_new_tokens": new_tokens},
    }


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
    recipe = os.environ.get("MILK_TRAIN_RECIPE", "sft")
    if recipe not in {"sft", "reinforce"}:
        raise ValueError("MILK_TRAIN_RECIPE must be sft or reinforce")
    steps = integer("MILK_TRAIN_STEPS", 1, 1, 1024)
    if recipe == "reinforce" and steps != 1:
        raise ValueError("MILK_TRAIN_STEPS must be 1 for reinforce")
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
    reinforce = None
    if recipe == "reinforce":
        loss, reinforce = reinforce_step(model, tokenizer, rows[0], optimizer, maximum)
        losses.append(loss)
    else:
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
        "parent": {"kind": "hf_base", "model_repo": MODEL_REPO, "model_revision": MODEL_REVISION},
        "recipe": recipe,
        "steps": steps,
        "examples": len(rows),
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "files": files,
    }
    if reinforce is not None:
        result["reinforce"] = reinforce
    (output / "milk-result.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    visible = {key: result[key] for key in ("schema_version", "job_id", "dataset_uuid", "recipe", "steps", "examples", "loss_first", "loss_last")}
    if reinforce is not None:
        visible["reinforce"] = {key: reinforce[key] for key in ("rollout_count", "rollouts_sha256", "reward_mean_bps", "reward_std_bps", "policy_loss")}
    print(json.dumps(visible, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
