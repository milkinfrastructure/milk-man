#!/usr/bin/env python3
"""Build native assistant data from a pinned summary or capture list; no inference."""

from collections import Counter
import json
import os
from pathlib import Path
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from milk_v2 import config, eval_plan, native_capture, summary
from milk_v2.state import redact
from milk_v2.store import StoreError, open_store, settings_from_environment

VERSION = "milk.native-dataset.v1"
SPLITS = ("train", "dev", "calibration", "sealed")
SPLIT_POLICY = {"version": eval_plan.SPLIT_VERSION, "basis": "scope_trajectory",
                "train_bps": 8000, "dev_bps": 1000, "calibration_bps": 500, "sealed_bps": 500}


def configuration(settings):
    key, expected = os.environ.get("MILK_CHECKPOINT_KEY", ""), os.environ.get("MILK_CHECKPOINT_SHA256", "")
    captures_key, captures_sha = os.environ.get("MILK_NATIVE_CAPTURES_KEY", ""), os.environ.get("MILK_NATIVE_CAPTURES_SHA256", "")
    checkpoint_uuid = None
    if captures_key or captures_sha:
        if key or expected:
            raise ValueError("select a summary or an explicit capture list, not both")
        if not captures_key.startswith(settings.scope_prefix) or not re.fullmatch(r"[0-9a-f]{64}", captures_sha):
            raise ValueError("capture list requires a scoped object key and SHA-256")
        parent = {"capture_manifest": {"key": captures_key, "sha256": captures_sha}}
    else:
        prefix = settings.scope_prefix + "s/"
        if not key.startswith(prefix) or not key.endswith("/summary.json"):
            raise ValueError("checkpoint key must identify a summary in the configured scope")
        checkpoint_uuid = key[len(prefix):-len("/summary.json")]
        if str(uuid.UUID(checkpoint_uuid)) != checkpoint_uuid or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("checkpoint UUID or SHA-256 is invalid")
        parent = {"parent_summary": {"key": key, "sha256": expected}}
    per_group = int(os.environ.get("MILK_NATIVE_DATASET_PER_GROUP", "1"))
    if per_group < 1:
        raise ValueError("MILK_NATIVE_DATASET_PER_GROUP must be positive")
    student = config.load().student_base
    identity = {
        "schema_version": "milk.native-dataset-identity.v1", "scope_id": settings.scope_id,
        "profile": settings.profile, **parent,
        "student_base": {"model_repo": student.model_repo, "model_revision": student.model_revision, "digest": student.digest},
        "policy": {"per_group": per_group, "selection": "earliest_supported_per_trajectory", "split_version": eval_plan.SPLIT_VERSION},
        "executor_sha256": summary.digest(Path(__file__).read_bytes()),
        "decoder_sha256": summary.digest(Path(native_capture.__file__).read_bytes()),
        "split_executor_sha256": summary.digest(Path(eval_plan.__file__).read_bytes()),
        "summary_executor_sha256": summary.digest(Path(summary.__file__).read_bytes()),
    }
    outcomes_key = os.environ.get("MILK_NATIVE_TASK_OUTCOMES_KEY", "")
    outcomes_sha = os.environ.get("MILK_NATIVE_TASK_OUTCOMES_SHA256", "")
    if outcomes_key or outcomes_sha:
        if not outcomes_key.startswith(settings.scope_prefix) or not re.fullmatch(r"[0-9a-f]{64}", outcomes_sha):
            raise ValueError("task outcomes require a scoped object key and SHA-256")
        identity["task_outcomes"] = {"key": outcomes_key, "sha256": outcomes_sha}
    return identity, checkpoint_uuid


def task_outcomes(store, settings, reference):
    def read(ref):
        if (not isinstance(ref, dict) or not isinstance(ref.get("key"), str)
            or not ref["key"].startswith(settings.scope_prefix)
            or not isinstance(ref.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])):
            raise ValueError("task outcome evidence requires a scoped key and SHA-256")
        body = store.get(ref["key"]).body
        if summary.digest(body) != ref["sha256"]:
            raise ValueError("task outcome evidence digest differs")
        value = summary._json(body, "task outcome evidence")
        if not isinstance(value, dict):
            raise ValueError("task outcome evidence must be an object")
        return value

    index = read(reference)
    if (index.get("schema_version") != "milk.task-outcomes.v1"
        or index.get("scope_id") != settings.scope_id or not isinstance(index.get("outcomes"), list)):
        raise ValueError("task outcomes identity differs")
    outcomes = {}
    for item in index["outcomes"]:
        if not isinstance(item, dict) or not isinstance(item.get("trajectory_id"), str):
            raise ValueError("task outcome requires its executed trajectory")
        group = eval_plan.source_group("0" * 64, item["trajectory_id"], settings.scope_id)["sha256"]
        if group in outcomes:
            raise ValueError("duplicate task outcome trajectory")
        result = read(item.get("result"))
        correct = result.get("task_correct")
        if (result.get("schema_version") != "milk.agent-trial-result.v1"
            or result.get("trajectory_id") != item["trajectory_id"] or "task_correct" not in result
            or (correct is not None and type(correct) is not bool)):
            raise ValueError("task outcome must match the executed trajectory and its recorded verdict")
        if correct is not None:
            checker = result.get("checker")
            if (not isinstance(checker, dict) or checker.get("error") is not None or checker.get("exit_code") != 0
                or not isinstance(checker.get("verdict"), dict) or checker["verdict"].get("task_correct") is not correct):
                raise ValueError("scored task outcome requires its matching completed checker")
        outcomes[group] = correct
    return outcomes


def source_rows(store, settings, identity, checkpoint_uuid):
    parent = identity.get("parent_summary") or identity["capture_manifest"]
    body = store.get(parent["key"]).body
    if summary.digest(body) != parent["sha256"]:
        raise ValueError("dataset source digest differs")
    checkpoint = summary._json(body, "checkpoint")
    if "capture_manifest" in identity:
        if (not isinstance(checkpoint, dict) or checkpoint.get("schema_version") != "milk.native-capture-list.v1"
            or checkpoint.get("scope_id") != settings.scope_id or checkpoint.get("profile") != settings.profile
            or not isinstance(checkpoint.get("captures"), list) or not checkpoint["captures"]):
            raise ValueError("capture list identity differs")
        sources, seen = [], set()
        for ref in checkpoint["captures"]:
            if (not isinstance(ref, dict) or not isinstance(ref.get("key"), str)
                or not ref["key"].startswith(settings.scope_prefix + "c/") or ref["key"] in seen
                or not isinstance(ref.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])):
                raise ValueError("capture list requires unique scoped keys and SHA-256 values")
            seen.add(ref["key"])
            entry = summary.parse_capture(store, settings, ref["key"])
            if entry["object_sha256"] != ref["sha256"]:
                raise ValueError("capture list object digest differs")
            sources.append(entry)
        return sources, len(sources)
    if not isinstance(checkpoint, dict) or any(checkpoint.get(key) != value for key, value in {
        "schema_version": "milk.summary.v2", "summary_uuid": checkpoint_uuid,
        "scope_id": settings.scope_id, "profile": settings.profile,
    }.items()):
        raise ValueError("checkpoint identity differs")
    sources, unused_keys = summary._ancestry(store, settings, checkpoint)
    if checkpoint.get("capture_count") != len(sources):
        raise ValueError("checkpoint count differs from its ancestry")
    return sources, 0


def prepare(store, settings, identity, checkpoint_uuid):
    sources, capture_reads = source_rows(store, settings, identity, checkpoint_uuid)
    rows = {split: [] for split in SPLITS}
    selected, unsupported, skipped = Counter(), Counter(), Counter()
    outcomes = task_outcomes(store, settings, identity["task_outcomes"]) if "task_outcomes" in identity else None
    for entry in sorted(sources, key=lambda row: (summary._utc(row.get("completed_at"), "completed_at"), row["key"])):
        if not entry["key"].startswith(settings.scope_prefix + "c/"):
            raise ValueError("capture key is outside the configured scope")
        if entry["trajectory_id"] is None:
            skipped["trajectory_id_missing"] += 1
            continue
        group = eval_plan.source_group(entry["request_sha256"], entry["trajectory_id"], settings.scope_id)
        split = eval_plan.split_for_group(group["sha256"], group["kind"])
        if outcomes is not None and split == "train" and outcomes.get(group["sha256"]) is not True:
            skipped["task_failed" if outcomes.get(group["sha256"]) is False else "task_outcome_unknown"] += 1
            continue
        if selected[group["sha256"]] >= identity["policy"]["per_group"]:
            skipped["per_group_limit"] += 1
            continue
        if entry.get("streaming"):
            unsupported["streaming_not_supported"] += 1
            continue
        if entry.get("parse") is not True or entry.get("success") is not True or entry.get("model_completed") is not True:
            unsupported["incomplete_or_invalid_exchange"] += 1
            continue
        stored, envelope, request_body, response_body = summary.read_capture(store, settings, entry["key"])
        capture_reads += 1
        source = {
            "scope_id": settings.scope_id, "profile": settings.profile, "capture_key": entry["key"],
            "object_sha256": summary.digest(stored.body), "request_sha256": summary.digest(request_body),
            "response_sha256": summary.digest(response_body), "content_sha256": summary.digest(request_body + b"\0" + response_body),
            "trajectory_id": envelope.get("trajectory_id"), "endpoint": envelope.get("endpoint"),
            "source_group_kind": group["kind"], "source_group_sha256": group["sha256"],
            "split": split,
        }
        if any(source[name] != entry.get(name) for name in (
            "object_sha256", "request_sha256", "response_sha256", "content_sha256", "trajectory_id", "endpoint",
        )) or envelope.get("completed_at") != entry.get("completed_at"):
            raise ValueError("selected capture differs from its source record")
        try:
            native_capture.require(200 <= envelope["response"].get("status", 0) < 300, "upstream_failure")
            native = native_capture.decode(envelope, summary._json(request_body, "request"), summary._json(response_body, "response"))
        except native_capture.Unsupported as error:
            unsupported[str(error)] += 1
            continue
        row = {"schema_version": native_capture.VERSION, "split": source["split"], "source": source,
               "decoder_sha256": identity["decoder_sha256"], **native}
        rows[source["split"]].append(row)
        selected[group["sha256"]] += 1
    facts = {"source_exchanges": len(sources), "capture_reads": capture_reads, "selected_groups": len(selected),
             "unsupported_reasons": dict(sorted(unsupported.items())), "skipped_reasons": dict(sorted(skipped.items()))}
    return rows, facts


def emit(manifest, key, body, replay):
    print(json.dumps({"state": "complete", "identity": manifest["job_id"], "inference_calls": 0, "provider_calls": 0,
        "details": {"dataset_uuid": manifest["dataset_uuid"], "manifest_key": key, "manifest_sha256": summary.digest(body),
                    "counts": manifest["counts"], "replay": replay, "capture_reads": 0 if replay else manifest["capture_reads"],
                    "unsupported_reasons": manifest["unsupported_reasons"], "skipped_reasons": manifest["skipped_reasons"],
                    "task_success": None, "training_ready": False}}, separators=(",", ":")))


def main():
    if sys.argv[1:] not in ([], ["run"]):
        raise ValueError("usage: native_dataset.py [run]")
    settings = settings_from_environment()
    identity, checkpoint_uuid = configuration(settings)
    job_id = summary.digest(identity)
    dataset_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "milk:native-dataset:" + job_id))
    prefix = settings.scope_prefix + f"d/{dataset_uuid}/"
    key = prefix + "manifest.json"
    store = open_store(settings)
    try:
        body = store.get(key).body
    except FileNotFoundError:
        body = None
    if body is not None:
        manifest = summary._json(body, "native dataset manifest")
        if not isinstance(manifest, dict) or any(manifest.get(name) != value for name, value in {
            "schema_version": VERSION, "identity": identity, "job_id": job_id, "dataset_uuid": dataset_uuid,
            "scope_id": settings.scope_id, "profile": settings.profile, "student_base": identity["student_base"],
            "parent_summary": identity.get("parent_summary"), "capture_manifest": identity.get("capture_manifest"), "split_policy": SPLIT_POLICY,
            "executor_sha256": identity["executor_sha256"], "decoder_sha256": identity["decoder_sha256"],
        }.items()):
            raise ValueError("stored native dataset identity differs")
        objects, counts = manifest.get("objects"), manifest.get("counts")
        if not isinstance(objects, dict) or set(objects) != set(SPLITS) or not isinstance(counts, dict) or set(counts) != set(SPLITS):
            raise ValueError("stored native dataset splits differ")
        for split in SPLITS:
            item = objects[split]
            if (not isinstance(item, dict) or item.get("key") != prefix + f"{split}.jsonl.zst"
                or type(counts[split]) is not int or counts[split] < 0 or item.get("count") != counts[split]
                or any(not isinstance(item.get(name), str) or not re.fullmatch(r"[0-9a-f]{64}", item[name])
                       for name in ("sha256", "content_sha256"))):
                raise ValueError("stored native dataset object reference differs")
        emit(manifest, key, body, True)
        return
    rows, facts = prepare(store, settings, identity, checkpoint_uuid)
    objects, bodies = {}, {}
    for split in SPLITS:
        plain = b"".join(summary.canonical(row) for row in rows[split])
        if len(plain) > 64 * 1024 * 1024:
            raise ValueError("native split exceeds the existing dataset object size limit")
        bodies[split] = summary._zstd(plain, False)
        objects[split] = {"key": prefix + f"{split}.jsonl.zst", "sha256": summary.digest(bodies[split]),
                          "content_sha256": summary.digest(plain), "count": len(rows[split])}
    manifest = {"schema_version": VERSION, "identity": identity, "job_id": job_id, "dataset_uuid": dataset_uuid,
                "scope_id": settings.scope_id, "profile": settings.profile,
                **{name: identity[name] for name in ("parent_summary", "capture_manifest", "student_base", "executor_sha256", "decoder_sha256") if name in identity},
                "split_policy": SPLIT_POLICY, "objects": objects, "counts": {split: len(rows[split]) for split in SPLITS},
                "task_success": None, "training_ready": False, **facts}
    for split in SPLITS:
        store.create_same(objects[split]["key"], bodies[split])
    body = summary.canonical(manifest)
    store.create_same(key, body)
    emit(manifest, key, body, False)


if __name__ == "__main__":
    os.umask(0o077)
    try:
        main()
    except (KeyError, ValueError, OSError, StoreError, summary.SummaryError) as error:
        print(json.dumps({"state": "failed", "identity": "native-dataset", "inference_calls": 0, "provider_calls": 0,
                          "error": redact(str(error))}, separators=(",", ":")))
        raise SystemExit(1)
