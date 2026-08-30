"""Run the operator-configured deterministic Milk reconciliation job."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from .engine import RunConfig, run_once as _run_once

_MAN_REVISION_ENV = "MILK_MAN_REVISION"
_RUN_CONFIG_ENV = "MILK_RUN_ONCE_CONFIG"
_RUN_PROFILE_ENV = "MILK_RUN_PROFILE"
_REPORT_SCHEMA = "milk.run-once-report.v2"
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class MilkJobError(RuntimeError):
    """Raised when the fixed Milk job cannot produce a valid report."""


async def run() -> dict[str, object]:
    """Run one bounded deterministic Milk reconciliation pass."""
    return await reconcile()


async def reconcile() -> dict[str, object]:
    """Run the fixed operator-configured summary/eval/proposal reconciliation."""
    run_config = _configured_path(_RUN_CONFIG_ENV)
    try:
        config = RunConfig.load(run_config)
        report = await asyncio.to_thread(
            _run_once,
            config,
        )
    except asyncio.CancelledError:
        raise
    except Exception as error:
        raise MilkJobError("Milk Man reconciliation failed") from error
    _validate_report(
        report,
        config.config_sha256,
        config.scope_id,
        config.eval.series_id,
    )
    return report


def _validate_report(value: object, config_sha256: str, scope_id: str, series_id: str) -> None:
    if not isinstance(value, dict) or value.get("schema_version") != _REPORT_SCHEMA:
        raise MilkJobError(f"Milk job did not return {_REPORT_SCHEMA}")
    if value.get("scope_id") != scope_id:
        raise MilkJobError("Milk job report scope does not match the admitted config")
    if value.get("route_activation_attempted") is not False:
        raise MilkJobError("Milk job report did not prove route activation stayed disabled")

    expected_revision = os.environ.get(_MAN_REVISION_ENV)
    if expected_revision is None or _HEX40.fullmatch(expected_revision) is None:
        raise MilkJobError(f"{_MAN_REVISION_ENV} must be a 40-character lowercase SHA-1")
    if value.get("harness_revision") != expected_revision:
        raise MilkJobError("Milk job report revision does not match the admitted checkout")
    if value.get("config_sha256") != config_sha256:
        raise MilkJobError("Milk job report config does not match the admitted file")
    expected_profile = os.environ.get(_RUN_PROFILE_ENV)
    if expected_profile not in {"production", "mechanics"}:
        raise MilkJobError(f"{_RUN_PROFILE_ENV} must be production or mechanics")
    if value.get("profile") != expected_profile:
        raise MilkJobError("Milk job report profile does not match the admitted profile")

    node_fields = (
        ("summary", "summaries", "summary_sha256"),
        ("readiness", "readiness", "readiness_sha256"),
        ("eval", f"evals/{series_id}", "eval_sha256"),
        ("validation", f"eval-validations/{series_id}", "eval_validation_sha256"),
        ("score", f"candidate-scores/{series_id}", "candidate_score_sha256"),
        ("proposal", "route-proposals", "route_proposal_sha256"),
    )
    job_fields = (
        ("classifier", "classify", "classifier_job_id"),
        ("eval_generation", "generate-eval", "eval_job_id"),
        ("eval_validation", "validate-eval", "eval_validation_job_id"),
        ("candidate_score", "score-candidate", "candidate_score_job_id"),
    )
    source_sha256 = _optional_digest(value, "source_manifest_sha256")
    versions = {name: _optional_digest(value, field) for name, _, field in node_fields}
    job_ids = {name: _optional_digest(value, field) for name, _, field in job_fields}
    incomplete = any(versions[child] is not None and versions[parent] is None for child, parent in (
        ("validation", "eval"), ("score", "validation"), ("proposal", "score")
    )) or (versions["summary"] is not None and source_sha256 is None) or any(
        versions[node] is not None and job_ids[job] is None for node, job in (
            ("eval", "eval_generation"), ("validation", "eval_validation"),
            ("score", "candidate_score"),
        )
    )
    if incomplete:
        raise MilkJobError("Milk job artifact graph is incomplete")
    prefix = f"milk/v1/scopes/{scope_id}"
    expected_refs = {
        "scope_prefix": prefix,
        "source_manifest_key": (
            f"{prefix}/pending-source/versions/{source_sha256}.json"
            if source_sha256 is not None
            else None
        ),
        "nodes": {
            name: None if versions[name] is None else {
                "pointer_key": f"{prefix}/{root}/current.json",
                "version_key": f"{prefix}/{root}/versions/{versions[name]}.json",
            }
            for name, root, _ in node_fields
        },
        "provider_jobs": {
            name: None if job_ids[name] is None else (
                f"{prefix}/jobs/{job_type}/{job_ids[name]}"
            )
            for name, job_type, _ in job_fields
        },
    }
    if value.get("artifact_refs") != expected_refs:
        raise MilkJobError("Milk job artifact refs are invalid")


def _optional_digest(value: dict[str, object], name: str) -> str | None:
    if name not in value:
        raise MilkJobError(f"Milk job report is missing {name}")
    digest = value[name]
    if digest is None:
        return None
    if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
        raise MilkJobError(f"Milk job report {name} is invalid")
    return digest


def _configured_path(name: str) -> Path:
    raw = os.environ.get(name)
    if not raw:
        raise MilkJobError(f"{name} is required")
    path = Path(raw)
    if not path.is_absolute():
        raise MilkJobError(f"{name} must be an absolute path")
    try:
        path = path.resolve(strict=True)
    except OSError as error:
        raise MilkJobError(f"{name} does not exist") from error
    if not path.is_file():
        raise MilkJobError(f"{name} must name a file")
    return path


__all__ = ["MilkJobError", "reconcile", "run"]
