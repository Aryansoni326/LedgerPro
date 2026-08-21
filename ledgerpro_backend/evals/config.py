"""Regression thresholds for the AI evaluation harness.

Build fails when any metric falls below its threshold.
"""

THRESHOLDS = {
    # Risk detection (duplicate / unusual / late + recon exception causes)
    "risk_precision": 0.80,
    "risk_recall": 0.80,
    # Reconciliation exception cause classification
    "recon_precision": 0.75,
    "recon_recall": 0.75,
    # Cash-flow forecast case accuracy (pressure / health / citation checks)
    "forecast_accuracy": 0.80,
    # Agent factual grounding: share of claims traceable to a real record
    "grounding_rate": 0.90,
}

REPORT_DIR_NAME = "eval-reports"
