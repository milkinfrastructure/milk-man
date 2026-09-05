#!/usr/bin/env python3
"""Build a small native assistant dataset from a pinned summary; no inference."""

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
    key, expected = os.environ["MILK_CHECKPOINT_KEY"], os.environ["MILK_CHECKPOINT_SHA256"]
    prefix = settings.scope_prefix + "s/"
    if not key.startswith(prefix) or not key.endswith("/summary.json"):
        raise ValueError("checkpoint key must identify a summary in the configured scope")
    checkpoint_uuid = key[len(prefix):-len("/summary.json")]
    if str(uuid.UUID(checkpoint_uuid)) != checkpoint_uuid or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("checkpoint UUID or SHA-256 is invalid")
    per_group = int(os.environ.get("MILK_NATIVE_DATASET_PER_GROUP", "1"))
    if per_group < 1:
        raise ValueError("MILK_NATIVE_DATASET_PER_GROUP must be positive")
    student = config.load().student_base
    identity = {
        "schema_version": "milk.native-dataset-identity.v1", "scope_id": settings.scope_id,
        "profile": settings.profile, "parent_summary": {"key": key, "sha256": expected},
        "student_base": {"model_repo": student.model_repo, "model_revision": student.model_revision, "digest": student.digest},
        "policy": {"per_group": per_group, "selection": "earliest_supported_per_trajectory", "split_version": eval_plan.SPLIT_VERSION},
        "executor_sha256": summary.digest(Path(__file__).read_bytes()),
        "decoder_sha256": summary.digest(Path(native_capture.__file__).read_bytes()),
        "split_executor_sha256": summary.digest(Path(eval_plan.__file__).read_bytes()),
        "summary_executor_sha256": summary.digest(Path(summary.__file__).read_bytes()),
    }
    return identity, checkpoint_uuid


def prepare(store, settings, identity, checkpoint_uuid):
    parent = identity["parent_summary"]
    body = store.get(parent["key"]).body
    if summary.digest(body) != parent["sha256"]:
        raise ValueError("checkpoint digest differs")
    checkpoint = summary._json(body, "checkpoint")
    if not isinstance(checkpoint, dict) or any(checkpoint.get(key) != value for key, value in {
        "schema_version": "milk.summary.v2", "summary_uuid": checkpoint_uuid,
        "scope_id": settings.scope_id, "profile": settings.profile,
    }.items()):
        raise ValueError("checkpoint identity differs")
    sources, unused_keys = summary._ancestry(store, settings, checkpoint)
    if checkpoint.get("capture_count") != len(sources):
        raise ValueError("checkpoint count differs from its ancestry")
    rows = {split: [] for split in SPLITS}
    selected, unsupported, skipped = Counter(), Counter(), Counter()
    capture_reads = 0
    for entry in sorted(sources, key=lambda row: (summary._utc(row.get("completed_at"), "completed_at"), row["key"])):
        if not entry["key"].startswith(settings.scope_prefix + "c/"):
            raise ValueError("capture key is outside the configured scope")
        if entry["trajectory_id"] is None:
            skipped["trajectory_id_missing"] += 1
            continue
        group = eval_plan.source_group(entry["request_sha256"], entry["trajectory_id"], settings.scope_id)
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
            "split": eval_plan.split_for_group(group["sha256"], group["kind"]),
        }
        if any(source[name] != entry.get(name) for name in (
            "object_sha256", "request_sha256", "response_sha256", "content_sha256", "trajectory_id", "endpoint",
        )) or envelope.get("completed_at") != entry.get("completed_at"):
            raise ValueError("selected capture differs from summary ancestry")
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
            "parent_summary": identity["parent_summary"], "split_policy": SPLIT_POLICY,
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
                **{name: identity[name] for name in ("parent_summary", "student_base", "executor_sha256", "decoder_sha256")},
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
