from __future__ import annotations

from collections import Counter
import hashlib
import os


POLICY_VERSION = "milk.eval-plan.v2"
SPLIT_VERSION = "milk.split.v2"
OPERATIONS = ("answer", "summarize", "extract", "classify", "transform", "generate", "code", "plan_or_tool_use", "conversation", "other")
ORACLES = frozenset({"exact", "reference", "schema"})
SCHEMA_KINDS = ("object", "array", "string", "number", "integer", "boolean")
SPLITS = ("dev", "calibration", "sealed")
TAIL_REASONS = ("long_context", "rare", "error", "tool_use", "multimodal", "low_confidence")


class PlanError(ValueError):
    pass


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise PlanError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise PlanError(f"{name} must be in {minimum}..{maximum}")
    return value


def requested_counts(profile: str) -> tuple[int, int]:
    production = profile == "production"
    return (
        _integer("MILK_EVAL_REPRESENTATIVE_CASES", 24 if production else 4, 1, 1024),
        _integer("MILK_EVAL_TAIL_CASES", 8 if production else 0, 0, 1024),
    )


def generation_counts(profile: str) -> tuple[int, int]:
    representative, tail = requested_counts(profile)
    target = _integer("MILK_EVAL_TARGET_CASES", representative + tail, 1, 1_000_000)
    shard = _integer("MILK_EVAL_SHARD_CASES", min(target, 256), 1, 256)
    return target, min(target, shard)


def split_for(request_sha256: str) -> str:
    try:
        source = bytes.fromhex(request_sha256)
    except (TypeError, ValueError) as error:
        raise PlanError("request SHA-256 is invalid") from error
    if len(source) != 32:
        raise PlanError("request SHA-256 is invalid")
    bucket = int.from_bytes(hashlib.sha256(b"milk.split.v2\0" + source).digest()[:2], "big") % 10_000
    if bucket < 8_000:
        return "train"
    if bucket < 9_000:
        return "dev"
    if bucket < 9_500:
        return "calibration"
    return "sealed"


def _allocation(total: int) -> dict[str, int]:
    dev = (total + 1) // 2
    rest = total - dev
    calibration = (rest + 1) // 2
    return {"dev": dev, "calibration": calibration, "sealed": rest - calibration}


def contract(profile: str) -> dict:
    representative, tail = requested_counts(profile)
    return {
        "schema_version": POLICY_VERSION,
        "split_version": SPLIT_VERSION,
        "split_basis": "request_sha256",
        "split_buckets": {"train": [0, 7999], "dev": [8000, 8999], "calibration": [9000, 9499], "sealed": [9500, 9999]},
        "oracles": sorted(ORACLES),
        "representative": _allocation(representative),
        "tail": _allocation(tail),
        "total": representative + tail,
    }


def _eligible(label: dict) -> bool:
    modalities = label.get("modalities")
    return (
        label.get("abstain") is False
        and label.get("answerable") is True
        and label.get("safety") == "benign"
        and label.get("outcome") == "success"
        and label.get("oracle") in ORACLES
        and modalities == ["text"]
        and label.get("tool_definitions") == 0
        and label.get("tool_calls") == 0
        and label.get("success") is True
    )


def _ordered(values: list[dict], salt: str) -> list[dict]:
    return sorted(values, key=lambda value: hashlib.sha256((salt + value["request_sha256"] + value["content_sha256"]).encode()).digest())


def _round_robin(values: list[dict], count: int, names: tuple[str, ...], field) -> list[dict]:
    selected: list[dict] = []
    remaining = list(values)
    while remaining and len(selected) < count:
        progressed = False
        for name in names:
            match = next((value for value in remaining if name in field(value)), None)
            if match is not None:
                selected.append(match)
                remaining.remove(match)
                progressed = True
                if len(selected) == count:
                    break
        if not progressed:
            break
    if len(selected) < count:
        selected.extend(remaining[: count - len(selected)])
    return selected


def build(labels: list[dict], profile: str) -> dict:
    policy = contract(profile)
    distinct: dict[str, dict] = {}
    for label in labels:
        if not isinstance(label, dict) or not _eligible(label):
            continue
        request_sha256 = label.get("request_sha256")
        content_sha256 = label.get("content_sha256")
        if not isinstance(request_sha256, str) or not isinstance(content_sha256, str):
            continue
        try:
            split = split_for(request_sha256)
        except PlanError:
            continue
        if split == "train":
            continue
        candidate = {**label, "split": split}
        prior = distinct.get(request_sha256)
        if prior is None or content_sha256 < prior["content_sha256"]:
            distinct[request_sha256] = candidate

    cases: list[dict] = []
    missing: dict[str, int] = {}
    used: set[str] = set()
    for split in SPLITS:
        available = [value for value in distinct.values() if value["split"] == split]
        representatives = _ordered([value for value in available if "representative" in value.get("selection_reasons", [])], f"representative:{split}:")
        chosen = _round_robin(representatives, policy["representative"][split], OPERATIONS, lambda value: (value.get("operation"),))
        for value in chosen:
            used.add(value["request_sha256"])
            cases.append({**value, "selection": "representative", "tail_reason": None})
        short = policy["representative"][split] - len(chosen)
        if short:
            missing[f"{split}.representative"] = short

        tails = []
        for value in available:
            if value["request_sha256"] in used:
                continue
            reasons = [reason for reason in value.get("selection_reasons", []) if reason in TAIL_REASONS]
            if value.get("confidence_basis_points", 10_000) < 7_000:
                reasons.append("low_confidence")
            reasons = tuple(dict.fromkeys(reasons))
            if reasons:
                tails.append({**value, "tail_reasons": reasons})
        tails = _ordered(tails, f"tail:{split}:")
        chosen = _round_robin(tails, policy["tail"][split], TAIL_REASONS, lambda value: value["tail_reasons"])
        for value in chosen:
            used.add(value["request_sha256"])
            cases.append({**value, "selection": "tail", "tail_reason": value["tail_reasons"][0]})
        short = policy["tail"][split] - len(chosen)
        if short:
            missing[f"{split}.tail"] = short

    order = {(split, selection): index for index, (split, selection) in enumerate((
        ("dev", "representative"), ("dev", "tail"),
        ("calibration", "representative"), ("calibration", "tail"),
        ("sealed", "representative"), ("sealed", "tail"),
    ))}
    cases.sort(key=lambda value: (order[(value["split"], value["selection"])], hashlib.sha256((value["request_sha256"] + value["content_sha256"]).encode()).digest()))
    for index, value in enumerate(cases):
        value["order"] = index
        value["case_id"] = hashlib.sha256(
            (POLICY_VERSION + "\0" + value["split"] + "\0" + value["selection"] + "\0" + value["request_sha256"] + "\0" + value["content_sha256"]).encode()
        ).hexdigest()
    counts = Counter((value["split"], value["selection"]) for value in cases)
    return {
        "schema_version": POLICY_VERSION,
        "policy": policy,
        "cases": cases,
        "counts": {f"{split}.{selection}": counts[(split, selection)] for split in SPLITS for selection in ("representative", "tail")},
        "missing": missing,
        "ready": not missing and len(cases) == policy["total"],
    }


def target_allocation(target: int) -> dict[str, int]:
    return _allocation(target)


def range_for(start: int, target: int, shard_cases: int) -> tuple[str, int]:
    allocation = target_allocation(target)
    cursor = 0
    for split in SPLITS:
        boundary = cursor + allocation[split]
        if start < boundary:
            return split, min(start + shard_cases, boundary)
        cursor = boundary
    raise PlanError("eval shard start is outside the target")


def precompute_range(target: int, shard_cases: int) -> tuple[int, str, int, int] | None:
    raw = os.environ.get("MILK_EVAL_PRECOMPUTE_SHARD")
    if raw is None:
        return None
    try:
        selected = int(raw)
    except ValueError as error:
        raise PlanError("MILK_EVAL_PRECOMPUTE_SHARD must be a non-negative integer") from error
    if selected < 0:
        raise PlanError("MILK_EVAL_PRECOMPUTE_SHARD must be a non-negative integer")
    if selected >= target:
        raise PlanError("MILK_EVAL_PRECOMPUTE_SHARD is outside the eval target")
    start = 0
    for index in range(selected + 1):
        if start >= target:
            raise PlanError("MILK_EVAL_PRECOMPUTE_SHARD is outside the eval target")
        split, end = range_for(start, target, shard_cases)
        if index == selected:
            return index, split, start, end
        start = end
    raise AssertionError("unreachable")


def shard(plan: dict, eval_uuid: str, target: int, start: int, end: int) -> dict:
    seeds = plan.get("cases")
    if (
        not isinstance(seeds, list)
        or not seeds
        or not isinstance(eval_uuid, str)
        or not eval_uuid
        or type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= target
    ):
        raise PlanError("eval shard arguments are invalid")
    split, expected_end = range_for(start, target, end - start)
    if end != expected_end:
        raise PlanError("eval shard crosses a split boundary")
    seeds = [seed for seed in seeds if seed.get("split") == split]
    if not seeds:
        raise PlanError(f"eval shard has no {split} source seeds")
    offset = int.from_bytes(hashlib.sha256((eval_uuid + "\0" + split).encode()).digest()[:8], "big") % len(seeds)
    split_start = sum(target_allocation(target)[name] for name in SPLITS[:SPLITS.index(split)])
    cases = []
    for ordinal in range(start, end):
        seed = seeds[(offset + ordinal - split_start) % len(seeds)]
        cases.append(
            {
                **seed,
                "seed_case_id": seed["case_id"],
                "order": ordinal,
                "case_id": hashlib.sha256(f"{eval_uuid}\0{ordinal}".encode()).hexdigest(),
            }
        )
    schema_kind = SCHEMA_KINDS[
        int.from_bytes(hashlib.sha256(f"{eval_uuid}\0schema\0{split}\0{start}".encode()).digest()[:8], "big")
        % len(SCHEMA_KINDS)
    ]
    return {
        "schema_version": "milk.eval-shard-plan.v3",
        "split": split,
        "start": start,
        "end": end,
        "schema_kind": schema_kind,
        "cases": cases,
    }
