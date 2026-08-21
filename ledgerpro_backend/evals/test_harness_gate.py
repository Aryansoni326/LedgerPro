"""
CI gate for the AI evaluation harness.

Uses Django's TestCase DB so labeled synthetic data is isolated.
Fails the build when any suite metric falls below ``evals.config.THRESHOLDS``.
Writes ``eval-reports/ai-eval-report.md`` for the workflow artifact.
"""
from pathlib import Path

from django.test import TestCase, override_settings

from evals.harness import run_all


@override_settings(USE_SQLITE=True, CELERY_TASK_ALWAYS_EAGER=True)
class AIEvalHarnessGateTests(TestCase):
    def test_ai_eval_meets_thresholds_and_writes_report(self):
        out = Path(__file__).resolve().parent.parent / "eval-reports"
        code = run_all(output_dir=out)
        self.assertEqual(
            code,
            0,
            "AI eval harness failed thresholds — see eval-reports/ai-eval-report.md",
        )
        self.assertTrue((out / "ai-eval-report.md").is_file())
        self.assertTrue((out / "ai-eval-summary.json").is_file())
