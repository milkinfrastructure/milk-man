from __future__ import annotations

import hashlib
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import milk_jobs


HARNESS_REVISION = "1" * 40
CONFIG_SHA256 = hashlib.sha256(b"{}").hexdigest()
EVAL_SHA256 = "3" * 64
VALIDATION_SHA256 = "4" * 64
SCORE_SHA256 = "5" * 64
PROPOSAL_SHA256 = "6" * 64


class MilkJobsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "milk_harness").mkdir()
        (self.root / "milk_harness" / "__init__.py").write_text("")
        self.config = self.root / "run-config.json"
        self.config.write_text("{}")
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
        report = {
            "schema_version": "milk.run-once-report.v1",
            "scope_id": "00000000-0000-0000-0000-000000000001",
            "profile": "mechanics",
            "trace_count": 12,
            "harness_revision": HARNESS_REVISION,
            "config_sha256": CONFIG_SHA256,
            "eval_sha256": EVAL_SHA256,
            "eval_validation_sha256": VALIDATION_SHA256,
            "candidate_score_sha256": SCORE_SHA256,
            "route_proposal_sha256": PROPOSAL_SHA256,
            "route_activation_attempted": False,
        }
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

    async def test_reconcile_requires_validation_and_score_before_proposal(self) -> None:
        report = self._valid_report(candidate_score_sha256=None)
        self._write_report(report)

        with self.assertRaisesRegex(milk_jobs.MilkJobError, "proposal is missing candidate score"):
            await milk_jobs.reconcile()

    async def test_reconcile_accepts_an_idle_report_without_eval_artifacts(self) -> None:
        report = self._valid_report(
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
            "schema_version": "milk.run-once-report.v1",
            "scope_id": "00000000-0000-0000-0000-000000000001",
            "profile": "mechanics",
            "trace_count": 12,
            "harness_revision": HARNESS_REVISION,
            "config_sha256": CONFIG_SHA256,
            "eval_sha256": EVAL_SHA256,
            "eval_validation_sha256": VALIDATION_SHA256,
            "candidate_score_sha256": SCORE_SHA256,
            "route_proposal_sha256": PROPOSAL_SHA256,
            "route_activation_attempted": False,
        }
        report.update(updates)
        return report


if __name__ == "__main__":
    unittest.main()
