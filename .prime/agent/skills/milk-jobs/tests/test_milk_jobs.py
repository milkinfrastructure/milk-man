from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import milk_jobs


ROOT = Path(__file__).parents[5]
HARNESS_REVISION = "1" * 40
SCOPE_ID = "01890f1e-2c40-7000-8000-000000000001"
SERIES_ID = "mechanics-v1"
CONFIG_RAW = json.dumps(
    {"scope_id": SCOPE_ID, "eval": {"series_id": SERIES_ID}},
    sort_keys=True,
    separators=(",", ":"),
).encode()
CONFIG_SHA256 = hashlib.sha256(CONFIG_RAW).hexdigest()
SOURCE_MANIFEST_SHA256 = "0" * 64
SUMMARY_SHA256 = "1" * 64
READINESS_SHA256 = "2" * 64
EVAL_SHA256 = "3" * 64
VALIDATION_SHA256 = "4" * 64
SCORE_SHA256 = "5" * 64
PROPOSAL_SHA256 = "6" * 64
CLASSIFIER_JOB_ID = "7" * 64
EVAL_JOB_ID = "8" * 64
VALIDATION_JOB_ID = "9" * 64
SCORE_JOB_ID = "a" * 64


def _node_ref(root: str, sha256: str | None) -> dict[str, str] | None:
    if sha256 is None:
        return None
    prefix = f"milk/v1/scopes/{SCOPE_ID}"
    return {
        "pointer_key": f"{prefix}/{root}/current.json",
        "version_key": f"{prefix}/{root}/versions/{sha256}.json",
    }


def _job_root(job_type: str, job_id: str | None) -> str | None:
    if job_id is None:
        return None
    return f"milk/v1/scopes/{SCOPE_ID}/jobs/{job_type}/{job_id}"


def _artifact_refs(report: dict[str, object]) -> dict[str, object]:
    prefix = f"milk/v1/scopes/{SCOPE_ID}"
    validation_sha256 = report["eval_validation_sha256"]
    score_sha256 = report["candidate_score_sha256"]
    return {
        "scope_prefix": prefix,
        "source_manifest_key": (
            f"{prefix}/pending-source/versions/"
            f"{report['source_manifest_sha256']}.json"
            if report["source_manifest_sha256"] is not None
            else None
        ),
        "nodes": {
            "summary": _node_ref("summaries", report["summary_sha256"]),
            "readiness": _node_ref("readiness", report["readiness_sha256"]),
            "eval": _node_ref(f"evals/{SERIES_ID}", report["eval_sha256"]),
            "validation": _node_ref(
                f"eval-validations/{SERIES_ID}", validation_sha256
            ),
            "score": _node_ref(
                f"candidate-scores/{SERIES_ID}", score_sha256
            ),
            "proposal": _node_ref(
                "route-proposals", report["route_proposal_sha256"]
            ),
        },
        "provider_jobs": {
            "classifier": _job_root("classify", report["classifier_job_id"]),
            "eval_generation": _job_root("generate-eval", report["eval_job_id"]),
            "eval_validation": _job_root("validate-eval", report["eval_validation_job_id"]),
            "candidate_score": _job_root("score-candidate", report["candidate_score_job_id"]),
        },
    }


class MilkJobsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "milk_harness").mkdir()
        (self.root / "milk_harness" / "__init__.py").write_text("")
        self.config = self.root / "run-config.json"
        self.config.write_bytes(CONFIG_RAW)
        self.environment = patch.dict(
            os.environ,
            {
                "MILK_HARNESS_ROOT": str(self.root),
                "MILK_HARNESS_REVISION": HARNESS_REVISION,
                "MILK_RUN_PROFILE": "mechanics",
                "MILK_RUN_ONCE_CONFIG": str(self.config),
            },
            clear=False,
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    async def test_reconcile_runs_only_the_fixed_command_and_parses_report(self) -> None:
        report = self._valid_report()
        self._write_main(
            f"""
            import json
            import pathlib
            import sys

            expected = ["run-once", "--config", {str(self.config.resolve())!r}]
            if sys.argv[1:] != expected:
                raise SystemExit(9)
            pathlib.Path({str(self.config)!r}).read_text()
            sys.stdout.write(json.dumps({report!r}))
            """
        )

        self.assertEqual(await milk_jobs.reconcile(), report)
        self.assertEqual(await milk_jobs.run(), report)

    async def test_bash_launcher_runs_from_an_unrelated_directory(self) -> None:
        if sys.version_info < (3, 10):
            self.skipTest("launcher requires Python 3.10 or newer")
        report = self._valid_report()
        self._write_report(report)
        environment = os.environ.copy()
        environment.update(
            {
                "MILK_MAN_PYTHON": sys.executable,
                "MILK_HARNESS_ROOT": str(self.root),
                "MILK_HARNESS_REVISION": HARNESS_REVISION,
                "MILK_RUN_PROFILE": "mechanics",
                "MILK_RUN_ONCE_CONFIG": str(self.config),
            }
        )
        environment.pop("PYTHONHOME", None)
        environment.pop("PYTHONPATH", None)

        process = await asyncio.to_thread(
            subprocess.run,
            [ROOT / "milk" / "jobs.sh"],
            cwd=self.root,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        self.assertEqual(
            process.stdout,
            json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        )

    async def test_reconcile_rejects_missing_operator_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(milk_jobs.MilkJobError, "MILK_HARNESS_ROOT is required"):
                await milk_jobs.reconcile()

    async def test_reconcile_stops_oversized_output(self) -> None:
        self._write_main(
            """
            import sys

            sys.stdout.write("x" * 256)
            """
        )

        with patch.object(milk_jobs, "_OUTPUT_LIMIT_BYTES", 64):
            with self.assertRaisesRegex(milk_jobs.MilkJobError, "output exceeded"):
                await milk_jobs.reconcile()

    async def test_reconcile_timeout_includes_child_after_pipes_close(self) -> None:
        self._write_main(
            """
            import sys
            import time

            sys.stdout.close()
            sys.stderr.close()
            time.sleep(10)
            """
        )

        with patch.object(milk_jobs, "_TIMEOUT_SECONDS", 0.05):
            with self.assertRaisesRegex(milk_jobs.MilkJobError, "timed out"):
                await milk_jobs.reconcile()

    async def test_reconcile_requires_route_activation_to_stay_disabled(self) -> None:
        report = self._valid_report(route_activation_attempted=True)
        self._write_main(
            f"""
            import json
            import sys

            sys.stdout.write(json.dumps({report!r}))
            """
        )

        with self.assertRaisesRegex(milk_jobs.MilkJobError, "activation stayed disabled"):
            await milk_jobs.reconcile()

    async def test_reconcile_requires_exact_harness_revision(self) -> None:
        report = self._valid_report(harness_revision="9" * 40)
        self._write_report(report)

        with self.assertRaisesRegex(milk_jobs.MilkJobError, "revision does not match"):
            await milk_jobs.reconcile()

    async def test_reconcile_requires_exact_config_and_profile(self) -> None:
        self._write_report(self._valid_report(config_sha256="9" * 64))
        with self.assertRaisesRegex(milk_jobs.MilkJobError, "config does not match"):
            await milk_jobs.reconcile()

        self._write_report(self._valid_report(profile="production"))
        with self.assertRaisesRegex(milk_jobs.MilkJobError, "profile does not match"):
            await milk_jobs.reconcile()

    async def test_reconcile_rejects_noncanonical_artifact_refs(self) -> None:
        cases = []

        wrong_prefix = copy.deepcopy(self._valid_report())
        wrong_prefix["artifact_refs"]["scope_prefix"] += "/model-authored"
        cases.append(("scope prefix", wrong_prefix))

        wrong_series = copy.deepcopy(self._valid_report())
        wrong_series["artifact_refs"]["nodes"]["eval"]["pointer_key"] = (
            wrong_series["artifact_refs"]["nodes"]["eval"]["pointer_key"].replace(
                SERIES_ID, "other-series"
            )
        )
        cases.append(("series", wrong_series))

        wrong_job_type = copy.deepcopy(self._valid_report())
        wrong_job_type["artifact_refs"]["provider_jobs"]["classifier"] = (
            wrong_job_type["artifact_refs"]["provider_jobs"]["classifier"].replace(
                "/jobs/classify/", "/jobs/model-choice/"
            )
        )
        cases.append(("job type", wrong_job_type))

        wrong_digest = copy.deepcopy(self._valid_report())
        wrong_digest["artifact_refs"]["nodes"]["summary"]["version_key"] = (
            wrong_digest["artifact_refs"]["nodes"]["summary"][
                "version_key"
            ].replace(SUMMARY_SHA256, "f" * 64)
        )
        cases.append(("digest", wrong_digest))

        for name, report in cases:
            with self.subTest(name=name):
                self._write_report(report)
                with self.assertRaises(milk_jobs.MilkJobError):
                    await milk_jobs.reconcile()

    async def test_reconcile_requires_scope_and_series_from_admitted_config(self) -> None:
        self.config.write_text('{"scope_id":"not-a-uuid","eval":{"series_id":"bad/series"}}')

        with self.assertRaisesRegex(milk_jobs.MilkJobError, "scope or series is invalid"):
            await milk_jobs.reconcile()

    async def test_reconcile_requires_validation_and_score_before_proposal(self) -> None:
        report = self._valid_report(candidate_score_sha256=None)
        self._write_report(report)

        with self.assertRaisesRegex(milk_jobs.MilkJobError, "artifact graph is incomplete"):
            await milk_jobs.reconcile()

    async def test_reconcile_accepts_an_idle_report_without_eval_artifacts(self) -> None:
        report = self._valid_report(
            eval_job_id=None,
            eval_sha256=None,
            eval_validation_sha256=None,
            candidate_score_sha256=None,
            route_proposal_sha256=None,
        )
        self._write_report(report)

        self.assertEqual(await milk_jobs.reconcile(), report)

    async def test_reconcile_does_not_return_process_errors(self) -> None:
        self._write_main(
            """
            import sys

            sys.stderr.write("provider-secret")
            raise SystemExit(7)
            """
        )

        with self.assertRaisesRegex(
            milk_jobs.MilkJobError, r"exited with status 7 \(stderr_bytes=15\)"
        ) as raised:
            await milk_jobs.reconcile()
        self.assertNotIn("provider-secret", str(raised.exception))

    def _write_main(self, source: str) -> None:
        (self.root / "milk_harness" / "__main__.py").write_text(
            textwrap.dedent(source).lstrip()
        )

    def _write_report(self, report: dict[str, object]) -> None:
        self._write_main(
            f"""
            import json
            import sys

            sys.stdout.write(json.dumps({report!r}))
            """
        )

    @staticmethod
    def _valid_report(**updates: object) -> dict[str, object]:
        report: dict[str, object] = {
            "schema_version": "milk.run-once-report.v2",
            "scope_id": SCOPE_ID,
            "profile": "mechanics",
            "trace_count": 12,
            "harness_revision": HARNESS_REVISION,
            "config_sha256": CONFIG_SHA256,
            "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "summary_sha256": SUMMARY_SHA256,
            "readiness_sha256": READINESS_SHA256,
            "classifier_job_id": CLASSIFIER_JOB_ID,
            "eval_job_id": EVAL_JOB_ID,
            "eval_validation_job_id": VALIDATION_JOB_ID,
            "candidate_score_job_id": SCORE_JOB_ID,
            "eval_sha256": EVAL_SHA256,
            "eval_validation_sha256": VALIDATION_SHA256,
            "candidate_score_sha256": SCORE_SHA256,
            "route_proposal_sha256": PROPOSAL_SHA256,
            "route_activation_attempted": False,
        }
        report.update(updates)
        if report["eval_validation_sha256"] is None and "eval_validation_job_id" not in updates:
            report["eval_validation_job_id"] = None
        if report["candidate_score_sha256"] is None and "candidate_score_job_id" not in updates:
            report["candidate_score_job_id"] = None
        if "artifact_refs" not in updates:
            report["artifact_refs"] = _artifact_refs(report)
        return report


if __name__ == "__main__":
    unittest.main()
