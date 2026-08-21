"""
AI evaluation harness entrypoint.

Usage (from ledgerpro_backend/):
    python -m evals
    python -m evals --output-dir ./eval-reports
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.config import REPORT_DIR_NAME, THRESHOLDS
from evals.report import render_report, write_report
from evals.suites import run_agent_suite, run_forecast_suite, run_recon_suite, run_risk_suite


def run_all(output_dir: Path | None = None) -> int:
    suites = [
        run_risk_suite(),
        run_recon_suite(),
        run_forecast_suite(),
        run_agent_suite(),
    ]

    suites[0].check_thresholds(
        THRESHOLDS, {"precision": "risk_precision", "recall": "risk_recall"}
    )
    suites[1].check_thresholds(
        THRESHOLDS, {"precision": "recon_precision", "recall": "recon_recall"}
    )
    suites[2].check_thresholds(THRESHOLDS, {"accuracy": "forecast_accuracy"})
    suites[3].check_thresholds(THRESHOLDS, {"grounding_rate": "grounding_rate"})

    overall = all(s.passed for s in suites)
    report = render_report(suites, overall_passed=overall)

    out = output_dir or (Path.cwd() / REPORT_DIR_NAME)
    report_path = write_report(report, out)

    summary = {
        "passed": overall,
        "thresholds": THRESHOLDS,
        "suites": {
            s.name: {
                "passed": s.passed,
                "metrics": s.metrics,
                "failures": s.failures,
            }
            for s in suites
        },
        "report": str(report_path),
    }
    summary_path = out / "ai-eval-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(report)
    print(f"\nWrote report: {report_path}")
    print(f"Wrote summary: {summary_path}")
    if not overall:
        print("AI EVAL FAILED — metrics below threshold.", file=sys.stderr)
        return 1
    print("AI EVAL PASSED")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LedgerPro AI evaluation harness")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for markdown/JSON report artifacts",
    )
    args = parser.parse_args(argv)
    return run_all(output_dir=args.output_dir)
