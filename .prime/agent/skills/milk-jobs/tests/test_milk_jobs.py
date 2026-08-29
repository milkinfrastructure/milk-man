from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import milk_jobs


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
            "trace_count": 12,
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
        self._write_main(
            """
            import json
            import sys

            sys.stdout.write(json.dumps({
                "schema_version": "milk.run-once-report.v1",
                "route_activation_attempted": True,
            }))
            """
        )

        with self.assertRaisesRegex(milk_jobs.MilkJobError, "activation stayed disabled"):
            await milk_jobs.reconcile()

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


if __name__ == "__main__":
    unittest.main()
