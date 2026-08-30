from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import milk_jobs


ROOT = Path(__file__).parents[5]
MAN_REVISION = "1" * 40
ADMITTED_CONFIG = json.loads((ROOT / "milk/jobs.mechanics.json").read_bytes())
PRODUCTION_CONFIG = json.loads((ROOT / "milk/jobs.production.json").read_bytes())
SCOPE_ID = ADMITTED_CONFIG["scope_id"]
SERIES_ID = ADMITTED_CONFIG["eval"]["series_id"]
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
    def test_mechanics_source_capacity_preserves_bounded_sampling(self):
        source = ADMITTED_CONFIG["source"]
        self.assertEqual(source["max_traces"], 999)
        self.assertEqual(source["max_total_trace_bytes"], 64 * 1024 * 1024)
        self.assertEqual(source["classifier_sample_sessions"], 32)

    def test_shipped_teacher_timeout_covers_large_bounded_requests(self):
        self.assertEqual(ADMITTED_CONFIG["teacher"]["timeout_seconds"], 120)
        self.assertEqual(PRODUCTION_CONFIG["teacher"]["timeout_seconds"], 120)

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.store = self.root / "store"
        self.config = self.root / "run-config.json"
        config = copy.deepcopy(ADMITTED_CONFIG)
        config["store"] = {"kind": "local", "root": str(self.store)}
        config_raw = (
            json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        self.config.write_bytes(config_raw)
        self.config_sha256 = hashlib.sha256(config_raw).hexdigest()
        self.environment = patch.dict(
            os.environ,
            {
                "MILK_MAN_REVISION": MAN_REVISION,
                "MILK_RUN_PROFILE": "mechanics",
                "MILK_RUN_ONCE_CONFIG": str(self.config),
            },
            clear=False,
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    async def test_reconcile_runs_only_the_in_repo_engine_and_validates_report(self) -> None:
        report = self._valid_report()
        with patch.object(milk_jobs, "_run_once", return_value=report) as engine:
            self.assertEqual(await milk_jobs.reconcile(), report)
            self.assertEqual(await milk_jobs.run(), report)
        self.assertEqual(engine.call_count, 2)
        for call in engine.call_args_list:
            self.assertEqual(call.args[0].config_sha256, self.config_sha256)

    async def test_bash_launcher_runs_from_an_unrelated_directory(self) -> None:
        if sys.version_info < (3, 10):
            self.skipTest("launcher requires Python 3.10 or newer")
        (self.root / "python").symlink_to(sys.executable)
        environment = os.environ.copy()
        environment.update(
            {
                "MILK_MAN_PYTHON": "./python",
                "MILK_MAN_REVISION": MAN_REVISION,
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
        report = json.loads(process.stdout)
        self.assertEqual(report["schema_version"], "milk.run-once-report.v2")
        self.assertEqual(report["harness_revision"], MAN_REVISION)
        self.assertEqual(report["config_sha256"], self.config_sha256)
        self.assertEqual(report["trace_count"], 0)
        self.assertIs(report["route_activation_attempted"], False)

    async def test_reconcile_rejects_missing_operator_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(milk_jobs.MilkJobError, "MILK_RUN_ONCE_CONFIG is required"):
                await milk_jobs.reconcile()

    async def test_reconcile_requires_route_activation_to_stay_disabled(self) -> None:
        report = self._valid_report(route_activation_attempted=True)
        with self.assertRaisesRegex(milk_jobs.MilkJobError, "activation stayed disabled"):
            await self._reconcile_report(report)

    async def test_reconcile_requires_exact_milk_man_revision(self) -> None:
        report = self._valid_report(harness_revision="9" * 40)
        with self.assertRaisesRegex(milk_jobs.MilkJobError, "revision does not match"):
            await self._reconcile_report(report)

    async def test_reconcile_requires_exact_config_and_profile(self) -> None:
        with self.assertRaisesRegex(milk_jobs.MilkJobError, "config does not match"):
            await self._reconcile_report(self._valid_report(config_sha256="9" * 64))

        with self.assertRaisesRegex(milk_jobs.MilkJobError, "profile does not match"):
            await self._reconcile_report(self._valid_report(profile="production"))

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
                with self.assertRaises(milk_jobs.MilkJobError):
                    await self._reconcile_report(report)

    async def test_reconcile_requires_scope_and_series_from_admitted_config(self) -> None:
        self.config.write_text('{"scope_id":"not-a-uuid","eval":{"series_id":"bad/series"}}')

        with patch.object(milk_jobs, "_run_once") as engine:
            with self.assertRaisesRegex(milk_jobs.MilkJobError, "reconciliation failed"):
                await milk_jobs.reconcile()
        engine.assert_not_called()

    async def test_reconcile_requires_validation_and_score_before_proposal(self) -> None:
        report = self._valid_report(candidate_score_sha256=None)
        with self.assertRaisesRegex(milk_jobs.MilkJobError, "artifact graph is incomplete"):
            await self._reconcile_report(report)

    async def test_reconcile_accepts_an_idle_report_without_eval_artifacts(self) -> None:
        report = self._valid_report(
            eval_job_id=None,
            eval_sha256=None,
            eval_validation_sha256=None,
            candidate_score_sha256=None,
            route_proposal_sha256=None,
        )
        self.assertEqual(await self._reconcile_report(report), report)

    async def test_reconcile_does_not_return_engine_errors(self) -> None:
        raw_message = "provider-secret"
        with patch.object(
            milk_jobs, "_run_once", side_effect=RuntimeError(raw_message)
        ), self.assertRaisesRegex(
            milk_jobs.MilkJobError, "Milk Man reconciliation failed"
        ) as raised:
            await milk_jobs.reconcile()
        diagnostic = str(raised.exception)
        self.assertNotIn(raw_message, diagnostic)
        self.assertIn("error_class=RuntimeError", diagnostic)
        self.assertIn("failure_stage=milk_jobs.reconcile", diagnostic)
        self.assertIn(
            "failure_message_sha256="
            + hashlib.sha256(raw_message.encode()).hexdigest(),
            diagnostic,
        )

    async def _reconcile_report(self, report: dict[str, object]) -> dict[str, object]:
        with patch.object(milk_jobs, "_run_once", return_value=report):
            return await milk_jobs.reconcile()

    def _valid_report(self, **updates: object) -> dict[str, object]:
        report: dict[str, object] = {
            "schema_version": "milk.run-once-report.v2",
            "scope_id": SCOPE_ID,
            "profile": "mechanics",
            "trace_count": 12,
            "harness_revision": MAN_REVISION,
            "config_sha256": self.config_sha256,
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
