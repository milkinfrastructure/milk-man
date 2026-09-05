from __future__ import annotations

import hashlib
from copy import deepcopy
import json
import os
from pathlib import Path
import random
import uuid


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
    import boto3

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


def dataset(split: str = "train") -> tuple[dict, list[dict]]:
    import zstandard

    if split not in {"train", "dev"}:
        raise ValueError("training reads only train or dev splits")
    client = s3()
    manifest = json.loads(
        get(client, required("MILK_DATASET_MANIFEST_KEY"), required("MILK_DATASET_MANIFEST_SHA256"))
    )
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") not in {"milk.dataset.v2", "milk.dataset.v3", "milk.native-dataset.v1"}
        or manifest.get("scope_id") != required("MILK_SCOPE_ID")
        or manifest.get("student_base", {}).get("model_repo") != MODEL_REPO
        or manifest.get("student_base", {}).get("model_revision") != MODEL_REVISION
    ):
        raise ValueError("dataset manifest identity differs")
    native = manifest["schema_version"] == "milk.native-dataset.v1"
    if split != "train" and not native:
        raise ValueError("held-out loading is only supported for native datasets")
    if native:
        identity = manifest.get("identity")
        job_id = manifest.get("job_id")
        if (
            not isinstance(identity, dict)
            or identity.get("schema_version") != "milk.native-dataset-identity.v1"
            or sha256(canonical(identity)) != job_id
            or manifest.get("dataset_uuid") != str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:native-dataset:" + str(job_id)))
            or manifest.get("profile") != required("MILK_SCOPE_PROFILE")
            or any(manifest.get(name) != identity.get(name) for name in (
                "scope_id", "profile", "student_base", "parent_summary", "decoder_sha256", "executor_sha256",
            ))
        ):
            raise ValueError("native dataset identity differs")
        prefix = f"milk/v2/scopes/{manifest['scope_id']}/d/{manifest['dataset_uuid']}/"
        if required("MILK_DATASET_MANIFEST_KEY") != prefix + "manifest.json":
            raise ValueError("native dataset manifest key differs")
    part = manifest.get("objects", {}).get(split)
    if not isinstance(part, dict) or set(part) != {"key", "sha256", "content_sha256", "count"}:
        raise ValueError(f"dataset {split} object is invalid")
    if native and (
        type(part["count"]) is not int or part["count"] < (1 if split == "train" else 0)
        or manifest.get("counts", {}).get(split) != part["count"]
        or part["key"] != prefix + f"{split}.jsonl.zst"
    ):
        raise ValueError(f"native dataset {split} reference differs")
    compressed = get(client, part["key"], part["sha256"])
    plain = zstandard.ZstdDecompressor().decompress(compressed, max_output_size=64 * 1024 * 1024)
    if sha256(plain) != part["content_sha256"]:
        raise ValueError(f"dataset {split} content digest differs")
    rows = [json.loads(line) for line in plain.splitlines() if line]
    if len(rows) != part["count"] or (split == "train" and not rows):
        raise ValueError(f"dataset {split} count differs")
    for row in rows:
        if native:
            source = row.get("source", {}) if isinstance(row, dict) else {}
            if (
                not isinstance(row, dict)
                or row.get("schema_version") != "milk.native-assistant-example.v1"
                or row.get("split", split) != split
                or not isinstance(source, dict)
                or source.get("split") != split
                or source.get("scope_id") != manifest["scope_id"]
                or source.get("profile") != manifest["profile"]
                or row.get("decoder_sha256") != manifest["decoder_sha256"]
                or row.get("training_target") != "visible_assistant_only"
                or not isinstance(row.get("messages"), list) or not row["messages"]
                or not isinstance(row.get("tools"), list)
                or not isinstance(row.get("next_assistant_targets"), list) or not row["next_assistant_targets"]
                or any(not isinstance(message, dict) or message.get("role") != "assistant" for message in row["next_assistant_targets"])
            ):
                raise ValueError("dataset contains an invalid native training example")
            continue
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


def native_messages(items: list[dict]) -> list[dict]:
    messages = deepcopy(items)
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ValueError("native message role is not supported by the student template")
        if message["role"] == "assistant":
            # Captures omit reasoning. Also stop the template treating visible </think> text as hidden reasoning.
            message["reasoning_content"] = ""
        for call in message.get("tool_calls", []):
            arguments = call["function"]["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(arguments, dict):
                raise ValueError("native tool arguments must be a JSON object")
            call["function"]["arguments"] = arguments
    return messages


def token_ids(tokenizer, row: dict, maximum: int) -> tuple[list[int], list[int]]:
    """Prepare CPU token IDs; native history, tools, and targets are never truncated."""
    if row.get("schema_version") == "milk.native-assistant-example.v1":
        if row.get("training_target") != "visible_assistant_only":
            raise ValueError("native training requires visible assistant targets")
        messages = native_messages(row["messages"])
        targets = native_messages(row["next_assistant_targets"])
        if not messages or not targets or any(message["role"] != "assistant" for message in targets):
            raise ValueError("native training requires context and new assistant targets")
        template = {"tools": row["tools"], "tokenize": False, "enable_thinking": False}
        prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, **template)
        full = tokenizer.apply_chat_template(messages + targets, add_generation_prompt=False, **template)
        if not full.startswith(prompt):
            raise ValueError("student template changed native context at the assistant boundary")
        encoded = tokenizer(full, add_special_tokens=False)["input_ids"]
        context_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        if encoded[:len(context_ids)] != context_ids:
            raise ValueError("student tokenizer changed native context at the assistant boundary")
        if len(encoded) > maximum:
            raise ValueError(f"native example needs {len(encoded)} tokens; MILK_TRAIN_MAX_TOKENS={maximum}; no truncation applied")
        labels = [-100] * len(context_ids) + encoded[len(context_ids):]
        if not labels or all(value == -100 for value in labels):
            raise ValueError("native example has no assistant target tokens")
        return encoded, labels
    messages = [{"role": "user", "content": row["input"]}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    full = prompt + row["target"] + (tokenizer.eos_token or "")
    encoded = tokenizer(full, truncation=True, max_length=maximum)["input_ids"]
    prompt_length = len(tokenizer(prompt, truncation=True, max_length=maximum)["input_ids"])
    labels = [-100] * min(prompt_length, len(encoded)) + encoded[prompt_length:]
    if all(value == -100 for value in labels):
        raise ValueError("training target was truncated")
    return encoded, labels


def tokens(tokenizer, row: dict, maximum: int):
    import torch

    encoded, labels = token_ids(tokenizer, row, maximum)
    return torch.tensor([encoded], dtype=torch.long), torch.tensor([labels], dtype=torch.long)


def heldout_loss(model, batches) -> dict:
    """Token-weighted teacher-forced loss on fixed DEV targets; no generated actions."""
    import torch

    model.eval()
    weighted_loss, target_tokens = 0.0, 0
    with torch.no_grad():
        for cpu_ids, cpu_labels in batches:
            count = int((cpu_labels[:, 1:] != -100).sum())
            if not count:
                raise ValueError("held-out example has no target tokens")
            input_ids, labels = cpu_ids.cuda(), cpu_labels.cuda()
            loss = model(input_ids=input_ids, labels=labels).loss
            if not torch.isfinite(loss):
                raise RuntimeError("held-out target loss is not finite")
            weighted_loss += float(loss.detach().cpu()) * count
            target_tokens += count
            del input_ids, labels, loss
    return {"examples": len(batches), "target_tokens": target_tokens,
            "mean_target_nll": weighted_loss / target_tokens if target_tokens else None}


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
    if row.get("schema_version") == "milk.native-assistant-example.v1":
        raise ValueError("native tool targets do not support the text-similarity reinforce reward")
    import torch
    import torch.nn.functional as F

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
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    job_id = required("MILK_TRAIN_JOB_ID")
    recipe = os.environ.get("MILK_TRAIN_RECIPE", "sft")
    if recipe not in {"sft", "reinforce"}:
        raise ValueError("MILK_TRAIN_RECIPE must be sft or reinforce")
    steps = integer("MILK_TRAIN_STEPS", 1, 1, 1024)
    if recipe == "reinforce" and steps != 1:
        raise ValueError("MILK_TRAIN_STEPS must be 1 for reinforce")
    maximum = integer("MILK_TRAIN_MAX_TOKENS", 2048, 128, 65536)
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
    if recipe == "reinforce" and manifest["schema_version"] == "milk.native-dataset.v1":
        raise ValueError("native tool targets require SFT; text-similarity reinforce is unsupported")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ROOT, local_files_only=True)
    batches = [tokens(tokenizer, row, maximum) for row in rows[:min(steps, len(rows))]] if recipe == "sft" else []
    heldout = None
    if manifest["schema_version"] == "milk.native-dataset.v1":
        unused_manifest, dev_rows = dataset("dev")
        train_groups = {row["source"]["source_group_sha256"] for row in rows}
        if any(row["source"]["source_group_sha256"] in train_groups for row in dev_rows):
            raise ValueError("native train and dev source groups overlap")
        dev_batches = [tokens(tokenizer, row, maximum) for row in dev_rows]
        heldout = {"metric": "teacher_forced_target_nll", "split": "dev",
                   "dataset_manifest_key": required("MILK_DATASET_MANIFEST_KEY"),
                   "dataset_manifest_sha256": required("MILK_DATASET_MANIFEST_SHA256"),
                   "object": manifest["objects"]["dev"],
                   "note": "Loss on saved assistant targets, not generated task success or a model-quality win. No DEV examples means loss is unmeasured."}
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ROOT,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    ).cuda()
    model.config.use_cache = False
    if heldout is not None:
        heldout["before"] = heldout_loss(model, dev_batches)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    losses = []
    reinforce = None
    if recipe == "reinforce":
        loss, reinforce = reinforce_step(model, tokenizer, rows[0], optimizer, maximum)
        losses.append(loss)
    else:
        for step in range(steps):
            input_ids, labels = (value.cuda() for value in batches[step % len(batches)])
            optimizer.zero_grad(set_to_none=True)
            loss = model(input_ids=input_ids, labels=labels).loss
            if not torch.isfinite(loss):
                raise RuntimeError("training loss is not finite")
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))

    if heldout is not None:
        optimizer.zero_grad(set_to_none=True)
        heldout["after"] = heldout_loss(model, dev_batches)

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
        "examples_used": min(steps, len(rows)),
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "files": files,
    }
    if reinforce is not None:
        result["reinforce"] = reinforce
    if heldout is not None:
        result["heldout"] = heldout
    (output / "milk-result.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    visible = {key: result[key] for key in ("schema_version", "job_id", "dataset_uuid", "recipe", "steps", "examples", "examples_used", "loss_first", "loss_last")}
    if reinforce is not None:
        visible["reinforce"] = {key: reinforce[key] for key in ("rollout_count", "rollouts_sha256", "reward_mean_bps", "reward_std_bps", "policy_loss")}
    if heldout is not None:
        visible["heldout"] = heldout
    print(json.dumps(visible, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
