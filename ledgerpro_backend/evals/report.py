"""Human-readable markdown report for AI eval runs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from evals.config import THRESHOLDS
from evals.metrics import SuiteResult


def render_report(
    suites: list[SuiteResult],
    *,
    overall_passed: bool,
    thresholds: dict[str, float] | None = None,
) -> str:
    thresholds = thresholds or THRESHOLDS
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# LedgerPro AI Evaluation Report",
        "",
        f"**Generated:** {now}",
        f"**Overall:** {'PASS' if overall_passed else 'FAIL'}",
        "",
        "## Thresholds",
        "",
        "| Metric | Floor |",
        "| --- | ---: |",
    ]
    for k, v in thresholds.items():
        lines.append(f"| `{k}` | {v:.2f} |")

    lines.extend(["", "## Suite Summary", "", "| Suite | Key metrics | Status |", "| --- | --- | --- |"])
    for s in suites:
        metric_bits = ", ".join(f"{k}={v:.3f}" for k, v in s.metrics.items() if isinstance(v, float) and k not in ("tp", "fp", "fn", "passed", "total", "cases"))
        status = "PASS" if s.passed else "FAIL"
        lines.append(f"| `{s.name}` | {metric_bits or '-'} | **{status}** |")

    if any(s.failures for s in suites):
        lines.extend(["", "## Failures", ""])
        for s in suites:
            for f in s.failures:
                lines.append(f"- {f}")

    for s in suites:
        lines.extend(["", f"## Detail: `{s.name}`", ""])
        for row in s.details:
            case_id = row.get("case_id", "?")
            ok = row.get("ok")
            flag = "OK" if ok else "MISS"
            lines.append(f"### `{case_id}` — {flag}")
            lines.append("")
            lines.append("```json")
            import json

            lines.append(json.dumps(row, indent=2, default=str))
            lines.append("```")
            lines.append("")

    lines.extend(
        [
            "## How to interpret",
            "",
            "- **Risk precision/recall**: labeled duplicate / unusual / late detections vs RiskEngine output.",
            "- **Recon precision/recall**: labeled reconciliation exception causes vs ReconciliationEngine.",
            "- **Forecast accuracy**: share of labeled cash-flow cases meeting pressure/health/citation expectations.",
            "- **Grounding rate**: share of agent claims (evidence sources, numbers, entity refs) traceable to tool data or DB rows.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(text: str, output_dir: Path, filename: str = "ai-eval-report.md") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(text, encoding="utf-8")
    # Also write a machine-readable companion
    return path
