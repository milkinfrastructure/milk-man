"""Run the operator-configured deterministic Milk reconciliation job."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

_HARNESS_ROOT_ENV = "MILK_HARNESS_ROOT"
_RUN_CONFIG_ENV = "MILK_RUN_ONCE_CONFIG"
_REPORT_SCHEMA = "milk.run-once-report.v1"
_TIMEOUT_SECONDS = 900.0
_OUTPUT_LIMIT_BYTES = 1_048_576
_READ_CHUNK_BYTES = 65_536


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
    if not isinstance(report, dict) or report.get("schema_version") != _REPORT_SCHEMA:
        raise MilkJobError(f"Milk Harness did not return {_REPORT_SCHEMA}")
    if report.get("route_activation_attempted") is not False:
        raise MilkJobError("Milk Harness report did not prove route activation stayed disabled")
    return report


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
