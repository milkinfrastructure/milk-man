"""Run the operator-configured deterministic Milk reconciliation job."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path

_HARNESS_ROOT_ENV = "MILK_HARNESS_ROOT"
_HARNESS_REVISION_ENV = "MILK_HARNESS_REVISION"
_RUN_CONFIG_ENV = "MILK_RUN_ONCE_CONFIG"
_RUN_PROFILE_ENV = "MILK_RUN_PROFILE"
_REPORT_SCHEMA = "milk.run-once-report.v2"
_TIMEOUT_SECONDS = 900.0
_OUTPUT_LIMIT_BYTES = 1_048_576
_READ_CHUNK_BYTES = 65_536
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")


class MilkJobError(RuntimeError):
    """Raised when the fixed Milk reconciliation job cannot produce a valid report."""


class _OutputLimitExceeded(Exception):
    pass


async def run() -> dict[str, object]:
    """Run one bounded deterministic Milk reconciliation pass."""
    return await reconcile()


async def reconcile() -> dict[str, object]:
    """Run the fixed operator-configured summary/eval/proposal reconciliation."""
    harness_root = _configured_path(_HARNESS_ROOT_ENV, directory=True)
    run_config = _configured_path(_RUN_CONFIG_ENV, directory=False)
    config_raw = run_config.read_bytes()
    config_sha256 = hashlib.sha256(config_raw).hexdigest()
    scope_id, series_id = _admitted_ids(config_raw)
    if not (harness_root / "milk_harness" / "__main__.py").is_file():
        raise MilkJobError(f"{_HARNESS_ROOT_ENV} is not a Milk Harness checkout")

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "milk_harness",
            "run-once",
            "--config",
            str(run_config),
            cwd=harness_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as error:
        raise MilkJobError("failed to start Milk Harness") from error

    assert process.stdout is not None
    assert process.stderr is not None
    readers = (
        asyncio.create_task(_read_bounded(process.stdout)),
        asyncio.create_task(_read_bounded(process.stderr)),
    )
    try:
        stdout, stderr, return_code = await asyncio.wait_for(
            asyncio.gather(*readers, process.wait()), timeout=_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError as error:
        await _stop(process, readers)
        raise MilkJobError("Milk Harness timed out") from error
    except _OutputLimitExceeded as error:
        await _stop(process, readers)
        raise MilkJobError("Milk Harness output exceeded its limit") from error
    except asyncio.CancelledError:
        await _stop(process, readers)
        raise

    if return_code != 0:
        raise MilkJobError(
            f"Milk Harness exited with status {return_code} "
            f"(stderr_bytes={len(stderr)})"
        )
    try:
        report = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MilkJobError("Milk Harness returned invalid JSON") from error
    _validate_report(report, config_sha256, scope_id, series_id)
    return report


def _validate_report(value: object, config_sha256: str, scope_id: str, series_id: str) -> None:
    if not isinstance(value, dict) or value.get("schema_version") != _REPORT_SCHEMA:
        raise MilkJobError(f"Milk Harness did not return {_REPORT_SCHEMA}")
    if value.get("scope_id") != scope_id:
        raise MilkJobError("Milk Harness report scope does not match the admitted config")
    if value.get("route_activation_attempted") is not False:
        raise MilkJobError("Milk Harness report did not prove route activation stayed disabled")

    expected_revision = os.environ.get(_HARNESS_REVISION_ENV)
    if expected_revision is None or _HEX40.fullmatch(expected_revision) is None:
        raise MilkJobError(f"{_HARNESS_REVISION_ENV} must be a 40-character lowercase SHA-1")
    if value.get("harness_revision") != expected_revision:
        raise MilkJobError("Milk Harness report revision does not match the admitted checkout")
    if value.get("config_sha256") != config_sha256:
        raise MilkJobError("Milk Harness report config does not match the admitted file")
    expected_profile = os.environ.get(_RUN_PROFILE_ENV)
    if expected_profile not in {"production", "mechanics"}:
        raise MilkJobError(f"{_RUN_PROFILE_ENV} must be production or mechanics")
    if value.get("profile") != expected_profile:
        raise MilkJobError("Milk Harness report profile does not match the admitted profile")

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
        raise MilkJobError("Milk Harness artifact graph is incomplete")
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
        raise MilkJobError("Milk Harness artifact refs are invalid")


def _admitted_ids(raw: bytes) -> tuple[str, str]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MilkJobError("MILK_RUN_ONCE_CONFIG is not valid JSON") from error
    scope_id = value.get("scope_id") if isinstance(value, dict) else None
    eval_config = value.get("eval") if isinstance(value, dict) else None
    series_id = eval_config.get("series_id") if isinstance(eval_config, dict) else None
    if not isinstance(scope_id, str) or _UUID.fullmatch(scope_id) is None or (
        not isinstance(series_id, str) or _SAFE_ID.fullmatch(series_id) is None
    ):
        raise MilkJobError("MILK_RUN_ONCE_CONFIG scope or series is invalid")
    return scope_id, series_id


def _optional_digest(value: dict[str, object], name: str) -> str | None:
    if name not in value:
        raise MilkJobError(f"Milk Harness report is missing {name}")
    digest = value[name]
    if digest is None:
        return None
    if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
        raise MilkJobError(f"Milk Harness report {name} is invalid")
    return digest


def _configured_path(name: str, *, directory: bool) -> Path:
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
    if directory and not path.is_dir():
        raise MilkJobError(f"{name} must name a directory")
    if not directory and not path.is_file():
        raise MilkJobError(f"{name} must name a file")
    return path


async def _read_bounded(stream: asyncio.StreamReader) -> bytes:
    output = bytearray()
    while chunk := await stream.read(_READ_CHUNK_BYTES):
        output.extend(chunk)
        if len(output) > _OUTPUT_LIMIT_BYTES:
            raise _OutputLimitExceeded
    return bytes(output)


async def _stop(
    process: asyncio.subprocess.Process,
    readers: tuple[asyncio.Task[bytes], asyncio.Task[bytes]],
) -> None:
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    await process.wait()
    for reader in readers:
        reader.cancel()
    await asyncio.gather(*readers, return_exceptions=True)


__all__ = ["MilkJobError", "reconcile", "run"]
