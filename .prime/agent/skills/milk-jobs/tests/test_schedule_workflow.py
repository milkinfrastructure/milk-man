from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[5]
WORKFLOW = ROOT / ".github/workflows/milk-jobs.yml"


class MilkJobsWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_schedule_and_manual_profile_are_fixed(self) -> None:
        self.assertIn('cron: "17 * * * *"', self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("options: [production, mechanics]", self.text)
        self.assertIn("default: production", self.text)
        self.assertIn("group: milk-jobs-reconcile", self.text)
        self.assertIn("cancel-in-progress: false", self.text)
        jobs = self.text.split("\njobs:\n", 1)[1]
        self.assertEqual(
            re.findall(r"^  ([a-z][a-z0-9-]+):$", jobs, re.MULTILINE),
            ["reconcile"],
        )

    def test_engine_config_and_entry_point_are_in_repo(self) -> None:
        self.assertNotIn("milkinfrastructure/milk-harness", self.text)
        self.assertNotIn("MILK_HARNESS", self.text)
        self.assertEqual(self.text.count("MILK_MAN_REVISION: ${{ github.sha }}"), 1)
        self.assertIn("/milk/jobs.{1}.json", self.text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$MILK_MAN_REVISION"', self.text)
        self.assertEqual(self.text.count("./milk/jobs.sh"), 1)
        self.assertNotIn("await milk_jobs.reconcile()", self.text)
        self.assertNotIn("python -m milk_harness", self.text)
        self.assertNotIn("python3 -m milk_harness", self.text)

        for profile in ("production", "mechanics"):
            config = json.loads((ROOT / f"milk/jobs.{profile}.json").read_bytes())
            self.assertEqual(config["profile"], profile)

    def test_only_reconciliation_credentials_are_exposed(self) -> None:
        self.assertEqual(
            set(re.findall(r"secrets\.([A-Z0-9_]+)", self.text)),
            {
                "BASETEN_API_KEY",
                "BASETEN_TEACHER_API_KEY",
                "MILK_GATEWAY_API_KEY",
                "MILK_CONTROL_R2_ACCOUNT_ID",
                "MILK_CONTROL_R2_ACCESS_KEY_ID",
                "MILK_CONTROL_R2_BUCKET",
                "MILK_CONTROL_R2_SECRET_ACCESS_KEY",
                "MILK_CONTROL_R2_SESSION_TOKEN",
            },
        )
        self.assertEqual(
            self.text.count(
                "BASETEN_TEACHER_API_KEY: ${{ secrets.BASETEN_TEACHER_API_KEY }}"
            ),
            1,
        )
        self.assertEqual(
            self.text.count("BASETEN_API_KEY: ${{ secrets.BASETEN_API_KEY }}"),
            1,
        )
        self.assertEqual(set(re.findall(r"vars\.([A-Z0-9_]+)", self.text)), set())
        self.assertIn("environment: milk-provider-jobs-prod", self.text)
        self.assertIn("permissions:\n  contents: read", self.text)
        for forbidden in (
            "route-signing",
            "route signing",
            "route publication",
            "docker",
            "gpu",
            "inputs.command",
        ):
            self.assertNotIn(forbidden, self.text.casefold())


if __name__ == "__main__":
    unittest.main()
