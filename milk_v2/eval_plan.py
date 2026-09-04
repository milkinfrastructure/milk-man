from __future__ import annotations

from collections import Counter
import hashlib
import os
import uuid


POLICY_VERSION = "milk.eval-plan.v4"
SPLIT_VERSION = "milk.split.v3"
SUPPORTED_SPLIT_VERSIONS = frozenset({"milk.split.v2", SPLIT_VERSION})
OPERATIONS = ("answer", "summarize", "extract", "classify", "transform", "generate", "code", "plan_or_tool_use", "conversation", "other")
ORACLES = frozenset({"exact", "reference", "schema"})
OPERATION_SCHEDULE_VERSION = "milk.eval-operation-schedule.v1"
GENERATION_OPERATIONS = ("answer", "classify", "extract", "summarize", "transform")
SCHEMA_KINDS = ("object", "array", "string", "number", "integer", "boolean")
SPLITS = ("dev", "calibration", "sealed")
TAIL_REASONS = ("long_context", "rare", "error", "tool_use", "multimodal", "low_confidence")
MAX_TARGET_CASES = 1_000_000


class PlanError(ValueError):
    pass


def _integer(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as error:
        raise PlanError(f"{name} must be an integer") from error
    if value < minimum or maximum is not None and value > maximum:
        suffix = f"..{maximum}" if maximum is not None else " or greater"
        raise PlanError(f"{name} must be {minimum}{suffix}")
    return value


def requested_counts(profile: str) -> tuple[int, int]:
    production = profile == "production"
    return (
        _integer("MILK_EVAL_REPRESENTATIVE_CASES", 24 if production else 4, 1, 1024),
        _integer("MILK_EVAL_TAIL_CASES", 8 if production else 0, 0, 1024),
    )


def cases_per_conversation() -> int:
    return _integer("MILK_CASES_PER_CONVERSATION", 100, 1)


def generation_counts(plan: dict) -> tuple[int, int]:
    sources = plan.get("sources")
    if not isinstance(sources, list) or not sources:
        raise PlanError("eval plan has no eligible held-out sources")
    target = len(sources) * cases_per_conversation()
    if target > MAX_TARGET_CASES:
        raise PlanError(f"derived eval target must be at most {MAX_TARGET_CASES}")
    shard = _integer("MILK_EVAL_SHARD_CASES", min(target, 256), 1, 256)
    return target, min(target, shard)


def source_group(request_sha256: str, trajectory_id: str | None = None, scope_id: str | None = None) -> dict[str, str]:
    try:
        source = bytes.fromhex(request_sha256)
    except (TypeError, ValueError) as error:
        raise PlanError("request SHA-256 is invalid") from error
    if len(source) != 32:
        raise PlanError("request SHA-256 is invalid")
    if trajectory_id is None:
        return {"kind": "request", "sha256": request_sha256}
    try:
        trajectory = uuid.UUID(trajectory_id)
        scope = uuid.UUID(scope_id)
    except (AttributeError, TypeError, ValueError) as error:
        raise PlanError("trajectory source group requires valid trajectory and scope UUIDs") from error
    if trajectory.int == 0 or scope.int == 0:
        raise PlanError("trajectory source group requires nonzero trajectory and scope UUIDs")
    group = hashlib.sha256(b"milk.source-group.v1\0" + scope.bytes + trajectory.bytes).hexdigest()
    return {"kind": "trajectory", "sha256": group}


def split_for_group(source_group_sha256: str, kind: str) -> str:
    try:
        source = bytes.fromhex(source_group_sha256)
    except (TypeError, ValueError) as error:
        raise PlanError("source-group SHA-256 is invalid") from error
    if len(source) != 32 or kind not in {"request", "trajectory"}:
        raise PlanError("source group is invalid")
    salt = b"milk.split.v2\0" if kind == "request" else b"milk.split.v3\0"
    bucket = int.from_bytes(hashlib.sha256(salt + source).digest()[:2], "big") % 10_000
    if bucket < 8_000:
        return "train"
    if bucket < 9_000:
        return "dev"
    if bucket < 9_500:
        return "calibration"
    return "sealed"


def split_for(request_sha256: str, trajectory_id: str | None = None, scope_id: str | None = None) -> str:
    group = source_group(request_sha256, trajectory_id, scope_id)
    return split_for_group(group["sha256"], group["kind"])


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
        "split_basis": "scope_trajectory_or_request_sha256",
        "untagged_split_version": "milk.split.v2",
        "split_buckets": {"train": [0, 7999], "dev": [8000, 8999], "calibration": [9000, 9499], "sealed": [9500, 9999]},
        "oracles": sorted(ORACLES),
        "representative": _allocation(representative),
        "tail": _allocation(tail),
        "total": representative + tail,
    }


def _eligible(label: dict) -> bool:
    modalities = label.get("modalities")
    return (
        modalities == ["text"]
        and label.get("tool_definitions") == 0
        and label.get("tool_calls") == 0
        and label.get("success") is True
        and label.get("model_completed") is True
        and label.get("has_request_response_text") is True
    )


def _group_sha256(value: dict) -> str:
    return value.get("source_group_sha256", value["request_sha256"])


def _ordered(values: list[dict], salt: str) -> list[dict]:
    return sorted(values, key=lambda value: hashlib.sha256((salt + _group_sha256(value) + value["content_sha256"]).encode()).digest())


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


def build(labels: list[dict], profile: str, scope_id: str) -> dict:
    policy = contract(profile)
    distinct: dict[str, dict] = {}
    for label in labels:
        if not isinstance(label, dict) or not _eligible(label):
            continue
        request_sha256 = label.get("request_sha256")
        content_sha256 = label.get("content_sha256")
        if not isinstance(request_sha256, str) or not isinstance(content_sha256, str):
            continue
        trajectory_id = label.get("trajectory_id")
        try:
            group = source_group(request_sha256, trajectory_id, scope_id)
            split = split_for_group(group["sha256"], group["kind"])
        except PlanError:
            continue
        if label.get("source_group_kind", group["kind"]) != group["kind"] or label.get("source_group_sha256", group["sha256"]) != group["sha256"]:
            continue
        if split == "train":
            continue
        oracle = label.get("oracle")
        candidate = {**label, "trajectory_id": trajectory_id, "source_group_kind": group["kind"], "source_group_sha256": group["sha256"], "oracle": oracle if oracle in ORACLES else "reference", "split": split}
        group_key = group["kind"] + ":" + group["sha256"]
        prior = distinct.get(group_key)
        if (
            prior is None
            or group["kind"] == "request" and content_sha256 < prior["content_sha256"]
            or group["kind"] == "trajectory" and (
                candidate.get("completed_at", "") > prior.get("completed_at", "")
                or candidate.get("completed_at", "") == prior.get("completed_at", "") and content_sha256 < prior["content_sha256"]
            )
        ):
            distinct[group_key] = candidate

    source_group_count = len(distinct)
    by_request: dict[str, dict] = {}
    for candidate in distinct.values():
        prior = by_request.get(candidate["request_sha256"])
        if prior is None or (candidate["source_group_sha256"], candidate["content_sha256"]) < (prior["source_group_sha256"], prior["content_sha256"]):
            by_request[candidate["request_sha256"]] = candidate
    distinct = {value["source_group_kind"] + ":" + value["source_group_sha256"]: value for value in by_request.values()}

    cases: list[dict] = []
    missing: dict[str, int] = {}
    used: set[str] = set()
    for split in SPLITS:
        available = [value for value in distinct.values() if value["split"] == split]
        representatives = _ordered([value for value in available if "representative" in value.get("selection_reasons", [])], f"representative:{split}:")
        chosen = _round_robin(representatives, policy["representative"][split], OPERATIONS, lambda value: (value.get("operation"),))
        for value in chosen:
            used.add(value["source_group_sha256"])
            cases.append({**value, "selection": "representative", "tail_reason": None})
        short = policy["representative"][split] - len(chosen)
        if short:
            missing[f"{split}.representative"] = short

        tails = []
        for value in available:
            if value["source_group_sha256"] in used:
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
            used.add(value["source_group_sha256"])
            cases.append({**value, "selection": "tail", "tail_reason": value["tail_reasons"][0]})
        short = policy["tail"][split] - len(chosen)
        if short:
            missing[f"{split}.tail"] = short

    order = {(split, selection): index for index, (split, selection) in enumerate((
        ("dev", "representative"), ("dev", "tail"),
        ("calibration", "representative"), ("calibration", "tail"),
        ("sealed", "representative"), ("sealed", "tail"),
    ))}
    cases.sort(key=lambda value: (order[(value["split"], value["selection"])], hashlib.sha256((value["source_group_sha256"] + value["content_sha256"]).encode()).digest()))
    for index, value in enumerate(cases):
        value["order"] = index
        value["case_id"] = hashlib.sha256(
            (POLICY_VERSION + "\0" + value["split"] + "\0" + value["selection"] + "\0" + value["source_group_sha256"] + "\0" + value["content_sha256"]).encode()
        ).hexdigest()
    sources = []
    for value in distinct.values():
        if value["split"] not in SPLITS:
            continue
        reasons = [reason for reason in value.get("selection_reasons", []) if reason in TAIL_REASONS]
        if value.get("confidence_basis_points", 10_000) < 7_000:
            reasons.append("low_confidence")
        reasons = list(dict.fromkeys(reasons))
        sources.append({
            **value,
            "selection": "tail" if reasons else "representative",
            "tail_reason": reasons[0] if reasons else None,
        })
    def source_key(value):
        return (
            SPLITS.index(value["split"]),
            hashlib.sha256(("generation-source:" + value["source_group_sha256"] + value["content_sha256"]).encode()).digest(),
        )
    sources.sort(key=source_key)
    counts = Counter((value["split"], value["selection"]) for value in cases)
    return {
        "schema_version": POLICY_VERSION,
        "policy": policy,
        "cases": cases,
        "sources": sources,
        "eligible_capture_count": sum(1 for label in labels if isinstance(label, dict) and _eligible(label)),
        "source_group_count": source_group_count,
        "counts": {f"{split}.{selection}": counts[(split, selection)] for split in SPLITS for selection in ("representative", "tail")},
        "missing": missing,
        "ready": not missing and len(cases) == policy["total"],
    }


def select_sources(plan: dict) -> dict:
    raw = os.environ.get("MILK_EVAL_SOURCE_CONVERSATIONS")
    if raw is None:
        return plan
    requested = _integer("MILK_EVAL_SOURCE_CONVERSATIONS", 1, 1)
    sources = plan.get("sources")
    if not isinstance(sources, list) or len(sources) < requested:
        available = len(sources) if isinstance(sources, list) else 0
        raise PlanError(f"MILK_EVAL_SOURCE_CONVERSATIONS requires {requested} eligible sources; found {available}")
    allocation = _allocation(requested)
    selected = []
    for split in SPLITS:
        available = sorted(
            (value for value in sources if value.get("split") == split),
            key=lambda value: hashlib.sha256(
                ("generation-selection:" + _group_sha256(value) + value["content_sha256"]).encode()
            ).digest(),
        )
        required = allocation[split]
        if len(available) < required:
            raise PlanError(
                f"MILK_EVAL_SOURCE_CONVERSATIONS requires {required} {split} sources; found {len(available)}"
            )
        selected.extend(available[:required])
    return {
        **plan,
        "sources": sorted(
            selected,
            key=lambda value: (
                SPLITS.index(value["split"]),
                hashlib.sha256(("generation-source:" + _group_sha256(value) + value["content_sha256"]).encode()).digest(),
            ),
        ),
    }


def target_allocation(plan: dict, target: int) -> dict[str, int]:
    sources = plan.get("sources")
    if not isinstance(sources, list) or not sources or type(target) is not int or target < 1 or target % len(sources):
        raise PlanError("eval target must be an exact multiple of its source count")
    ratio = target // len(sources)
    counts = Counter(source.get("split") for source in sources)
    if any(split not in SPLITS for split in counts):
        raise PlanError("eval plan contains an invalid source split")
    return {split: counts[split] * ratio for split in SPLITS}


def range_for(plan: dict, start: int, target: int, shard_cases: int) -> tuple[str, int]:
    allocation = target_allocation(plan, target)
    cursor = 0
    for split in SPLITS:
        boundary = cursor + allocation[split]
        if start < boundary:
            return split, min(start + shard_cases, boundary)
        cursor = boundary
    raise PlanError("eval shard start is outside the target")


def precompute_range(plan: dict, target: int, shard_cases: int) -> tuple[int, str, int, int] | None:
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
        split, end = range_for(plan, start, target, shard_cases)
        if index == selected:
            return index, split, start, end
        start = end
    raise AssertionError("unreachable")


def shard(plan: dict, eval_uuid: str, target: int, start: int, end: int) -> dict:
    seeds = plan.get("sources")
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
    split, expected_end = range_for(plan, start, target, end - start)
    if end != expected_end:
        raise PlanError("eval shard crosses a split boundary")
    seeds = [seed for seed in seeds if seed.get("split") == split]
    if not seeds:
        raise PlanError(f"eval shard has no {split} source seeds")
    offset = int.from_bytes(hashlib.sha256((eval_uuid + "\0" + split).encode()).digest()[:8], "big") % len(seeds)
    allocation = target_allocation(plan, target)
    split_start = sum(allocation[name] for name in SPLITS[:SPLITS.index(split)])
    example_count = target // len(plan["sources"])
    cases = []
    for ordinal in range(start, end):
        split_ordinal = ordinal - split_start
        seed = seeds[(offset + split_ordinal) % len(seeds)]
        source_example_index = split_ordinal // len(seeds)
        cases.append(
            {
                **seed,
                "oracle": "reference" if seed["oracle"] == "schema" else seed["oracle"],
                "order": ordinal,
                "case_id": hashlib.sha256(f"{eval_uuid}\0{ordinal}".encode()).hexdigest(),
                "source_operation": seed["operation"],
                "operation": GENERATION_OPERATIONS[source_example_index % len(GENERATION_OPERATIONS)],
                "source_example_index": source_example_index,
                "source_example_count": example_count,
            }
        )
    schema_kind = SCHEMA_KINDS[
        int.from_bytes(hashlib.sha256(f"{eval_uuid}\0schema\0{split}\0{start}".encode()).digest()[:8], "big")
        % len(SCHEMA_KINDS)
    ]
    return {
        "schema_version": "milk.eval-shard-plan.v4",
        "split": split,
        "start": start,
        "end": end,
        "schema_kind": schema_kind,
        "cases": cases,
    }
