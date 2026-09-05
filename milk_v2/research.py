#!/usr/bin/env python3
"""Record a small, evidence-linked research state for one Milk scope."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import sys
import uuid

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from milk_v2 import summary
from milk_v2.state import redact_message
from milk_v2.store import StoreError, open_store, settings_from_environment


MAX_INPUT_BYTES = 64 * 1024
MAX_EXPERIMENT_BYTES = 8 * 1024
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
POINTERS = ("s/current.json", "e/current.json", "d/current.json", "m/current.json", "v/current.json")
INPUT_FIELDS = {"parent_revision", "objective", "targets", "baseline", "evaluation", "best", "experiments", "next_action", "wake"}
RECORD_FIELDS = INPUT_FIELDS | {"schema_version", "research_uuid", "scope_id", "profile"}


class ResearchError(ValueError):
    pass


class BusyError(RuntimeError):
    pass


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ResearchError(f"duplicate JSON field: {key}")
        value[key] = item
    return value


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ResearchError("research JSON contains a non-finite number")
    return parsed


def _invalid_constant(unused_value: str):
    raise ResearchError("research JSON contains a non-finite number")


def _loads(body: bytes, name: str) -> dict:
    try:
        value = json.loads(
            body,
            object_pairs_hook=_unique_object,
            parse_float=_finite_float,
            parse_constant=_invalid_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ResearchError(f"{name} must contain valid finite JSON") from error
    if not isinstance(value, dict):
        raise ResearchError(f"{name} must contain a JSON object")
    return value


def _valid_payload(value: dict) -> None:
    if set(value) != INPUT_FIELDS:
        raise ResearchError("research input fields differ")
    parent = value.get("parent_revision")
    if parent is not None and (not isinstance(parent, str) or DIGEST.fullmatch(parent) is None):
        raise ResearchError("parent_revision must be null or a SHA-256 digest")
    objective = value.get("objective")
    next_action = value.get("next_action")
    if not isinstance(objective, str) or not objective.strip() or len(objective.encode()) > 16 * 1024:
        raise ResearchError("objective must be 1 byte to 16 KiB of text")
    if not isinstance(next_action, str) or not next_action.strip() or len(next_action.encode()) > 8 * 1024:
        raise ResearchError("next_action must be 1 byte to 8 KiB of text")
    if not isinstance(value.get("targets"), dict):
        raise ResearchError("targets must be an object")
    if any(value.get(name) is not None and not isinstance(value.get(name), dict) for name in ("baseline", "evaluation", "best", "wake")):
        raise ResearchError("baseline, evaluation, best, and wake must be objects or null")
    experiments = value.get("experiments")
    if not isinstance(experiments, list) or len(experiments) > 256 or any(
        not isinstance(item, dict) or len(summary.canonical(item)) > MAX_EXPERIMENT_BYTES
        for item in experiments
    ):
        raise ResearchError("experiments must contain at most 256 compact objects of at most 8 KiB each")


def _input() -> dict:
    name = os.environ.get("MILK_RESEARCH_FILE", "")
    if not name:
        raise ResearchError("MILK_RESEARCH_FILE is required for run")
    try:
        with Path(name).open("rb") as source:
            body = source.read(MAX_INPUT_BYTES + 1)
    except OSError as error:
        raise ResearchError("MILK_RESEARCH_FILE cannot be read") from error
    if not body or len(body) > MAX_INPUT_BYTES:
        raise ResearchError("MILK_RESEARCH_FILE must be 1 byte to 64 KiB")
    value = _loads(body, "MILK_RESEARCH_FILE")
    _valid_payload(value)
    if redact_message(value) != value:
        raise ResearchError("MILK_RESEARCH_FILE contains a credential")
    return value


def _record(settings, value: dict) -> tuple[dict, bytes, str, str]:
    identity = {"scope_id": settings.scope_id, "profile": settings.profile, **value}
    research_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:research:" + summary.digest(identity)))
    record = {"schema_version": "milk.research.v1", "research_uuid": research_uuid, **identity}
    body = summary.canonical(record)
    revision = summary.digest(body)
    key = settings.scope_prefix + f"research/{research_uuid}/record.json"
    return record, body, revision, key


def _current(store, settings):
    pointer_key = settings.scope_prefix + "research/current.json"
    try:
        pointer_object = store.get(pointer_key)
    except FileNotFoundError:
        return None, None, None, None
    pointer = _loads(pointer_object.body, "research/current.json")
    expected = {"schema_version", "kind", "scope_id", "profile", "uuid", "key", "sha256"}
    research_uuid = pointer.get("uuid")
    try:
        parsed_uuid = uuid.UUID(research_uuid)
    except (AttributeError, TypeError, ValueError) as error:
        raise ResearchError("research pointer UUID is invalid") from error
    expected_key = settings.scope_prefix + f"research/{research_uuid}/record.json"
    if (
        set(pointer) != expected
        or pointer.get("schema_version") != "milk.pointer.v2"
        or pointer.get("kind") != "research"
        or pointer.get("scope_id") != settings.scope_id
        or pointer.get("profile") != settings.profile
        or parsed_uuid.version != 5
        or str(parsed_uuid) != research_uuid
        or pointer.get("key") != expected_key
        or not isinstance(pointer.get("sha256"), str)
        or DIGEST.fullmatch(pointer["sha256"]) is None
    ):
        raise ResearchError("research pointer identity differs")
    record_object = store.get(expected_key)
    if summary.digest(record_object.body) != pointer["sha256"]:
        raise ResearchError("research record digest differs")
    record = _loads(record_object.body, expected_key)
    payload = {key: record.get(key) for key in INPUT_FIELDS}
    try:
        _valid_payload(payload)
    except ResearchError as error:
        raise ResearchError("research record fields are invalid") from error
    if (
        set(record) != RECORD_FIELDS
        or record.get("schema_version") != "milk.research.v1"
        or record.get("research_uuid") != research_uuid
        or record.get("scope_id") != settings.scope_id
        or record.get("profile") != settings.profile
        or str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:research:" + summary.digest({"scope_id": settings.scope_id, "profile": settings.profile, **payload}))) != research_uuid
    ):
        raise ResearchError("research record identity differs")
    return pointer, pointer_object, record, record_object


def _observed(store, settings) -> dict:
    observed = {}
    for suffix in POINTERS:
        try:
            observed[suffix] = summary.digest(store.get(settings.scope_prefix + suffix).body)
        except FileNotFoundError:
            observed[suffix] = None
    return observed


def _verify_objects(store, settings, value: dict) -> int:
    references = set()
    entries = [value[name] for name in ("baseline", "evaluation", "best") if value[name] is not None]
    for entry in entries + value["experiments"]:
        objects = entry.get("object_refs", {})
        if not isinstance(objects, dict):
            raise ResearchError("object_refs must map names to scoped key/sha256 pairs")
        for reference in objects.values():
            if (
                not isinstance(reference, dict) or set(reference) != {"key", "sha256"}
                or not isinstance(reference["key"], str) or not reference["key"].startswith(settings.scope_prefix)
                or reference["key"].endswith("/current.json")
                or not isinstance(reference["sha256"], str) or DIGEST.fullmatch(reference["sha256"]) is None
            ):
                raise ResearchError("research object reference needs an immutable scoped key and SHA-256, not a current pointer")
            references.add((reference["key"], reference["sha256"]))
    for key, expected in sorted(references):
        if summary.digest(store.get(key).body) != expected:
            raise ResearchError("research object digest differs; record was not published")
    return len(references)


def view(store, settings) -> dict:
    pointer, unused_pointer_object, record, unused_record_object = _current(store, settings)
    return {
        "record": record,
        "revision": pointer.get("sha256") if pointer else None,
        "observed": _observed(store, settings),
    }


def _result(state: str, identity: str, details: dict, *, artifacts=(), error: str | None = None) -> dict:
    value = {
        "state": state,
        "identity": identity,
        "artifacts": list(artifacts),
        "next": details["record"]["next_action"] if details.get("record") else "research",
        "details": details,
        "inference_calls": 0,
        "provider_calls": 0,
    }
    if error is not None:
        value["error"] = error
    return value


def run(store, settings) -> dict:
    value = _input()
    record, record_body, revision, record_key = _record(settings, value)
    pointer, pointer_object, unused_current_record, unused_record_object = _current(store, settings)
    if pointer and pointer["sha256"] == revision:
        details = {"record": record, "revision": revision, "observed": _observed(store, settings), "objects_checked": 0}
        return _result("idle", revision, details, artifacts=({"key": record_key, "sha256": revision},))
    parent = value["parent_revision"]
    current_revision = pointer.get("sha256") if pointer else None
    if parent != current_revision:
        raise BusyError("parent_revision differs from the current research revision")

    objects_checked = _verify_objects(store, settings, value)
    store.create_same(record_key, record_body)
    pointer_value = {
        "schema_version": "milk.pointer.v2",
        "kind": "research",
        "scope_id": settings.scope_id,
        "profile": settings.profile,
        "uuid": record["research_uuid"],
        "key": record_key,
        "sha256": revision,
    }
    pointer_key = settings.scope_prefix + "research/current.json"
    pointer_body = summary.canonical(pointer_value)
    if pointer_object is None:
        try:
            published = store.create_same(pointer_key, pointer_body)
        except StoreError as error:
            raise BusyError("research pointer changed before publication") from error
    else:
        published = store.replace_if_match(pointer_key, pointer_object.etag, pointer_body)
        if published is None:
            raise BusyError("research pointer changed before publication")
    details = {"record": record, "revision": revision, "observed": _observed(store, settings), "objects_checked": objects_checked}
    artifacts = ({"key": record_key, "sha256": revision}, {"key": pointer_key, "sha256": summary.digest(pointer_body)})
    return _result("progressed" if published.created or pointer_object is not None else "idle", revision, details, artifacts=artifacts)


def main() -> None:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    settings = None
    try:
        if action not in {"run", "status"}:
            raise ResearchError("action must be run or status")
        settings = settings_from_environment()
        store = open_store(settings)
        if action == "run":
            output = run(store, settings)
        else:
            details = view(store, settings)
            details["summary_threshold"] = summary.threshold_probe(store, settings)
            identity = details["revision"] or summary.digest({"scope_id": settings.scope_id, "profile": settings.profile, "research": None})
            output = _result("idle", identity, details)
        print(json.dumps(redact_message(output), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    except BusyError as error:
        identity = summary.digest({"scope_id": settings.scope_id if settings else None, "action": action, "state": "busy"})
        print(json.dumps(redact_message(_result("blocked", identity, {"record": None, "revision": None, "observed": {}}, error=str(error))), sort_keys=True, separators=(",", ":")))
        raise SystemExit(75) from error
    except (ResearchError, StoreError, OSError, ValueError) as error:
        identity = summary.digest({"scope_id": settings.scope_id if settings else None, "action": action, "error": type(error).__name__})
        print(json.dumps(redact_message(_result("failed", identity, {"record": None, "revision": None, "observed": {}}, error=str(error))), sort_keys=True, separators=(",", ":")))
        raise SystemExit(70) from error


if __name__ == "__main__":
    main()
