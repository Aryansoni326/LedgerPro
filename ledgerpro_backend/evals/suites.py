"""Suite runners: risk, reconciliation, forecast, agent grounding."""
from __future__ import annotations

from decimal import Decimal

from agents.executor import execute_agent
from agents.models import AgentAction
from evals.grounding import score_response_grounding
from evals.metrics import ConfusionCounts, SuiteResult
from evals.seed import load_json, seed_case
from intelligence.forecasting import CashFlowForecaster
from intelligence.models import ReconciliationException
from intelligence.reconciliation import ReconciliationEngine
from intelligence.risk_engine import RiskEngine, RiskEngineConfig


def run_risk_suite() -> SuiteResult:
    data = load_json("risk_cases.json")
    counts = ConfusionCounts()
    details: list[dict] = []

    for case in data["cases"]:
        ctx = seed_case(case)
        firm = ctx["firm"]
        txns = ctx["transactions"]
        as_of = ctx["as_of"]

        engine = RiskEngine(RiskEngineConfig(persist=False))
        detections = engine.scan(firm.id, as_of=as_of)
        predicted = {(d.category, d.entity_id) for d in detections}

        expected_keys = set()
        for exp in case.get("expected_detections", []):
            expected_keys.add((exp["category"], txns[exp["txn_key"]].id))

        tp = predicted & expected_keys
        fp = predicted - expected_keys
        fn = expected_keys - predicted

        # must_not_detect → false positives if predicted
        for ban in case.get("must_not_detect", []):
            key = (ban["category"], txns[ban["txn_key"]].id)
            if key in predicted and key not in expected_keys:
                fp.add(key)

        counts.tp += len(tp)
        counts.fp += len(fp)
        counts.fn += len(fn)

        details.append(
            {
                "case_id": case["case_id"],
                "expected": sorted(list(expected_keys)),
                "predicted": sorted([(c, i) for c, i in predicted]),
                "tp": len(tp),
                "fp": len(fp),
                "fn": len(fn),
                "ok": not fp and not fn,
            }
        )

    result = SuiteResult(
        name="risk_engine",
        metrics={
            "precision": counts.precision,
            "recall": counts.recall,
            "f1": counts.f1,
            "tp": float(counts.tp),
            "fp": float(counts.fp),
            "fn": float(counts.fn),
        },
        details=details,
    )
    return result


def run_recon_suite() -> SuiteResult:
    data = load_json("recon_cases.json")
    counts = ConfusionCounts()
    details: list[dict] = []
    # Counterpart legs often get a secondary cause; don't treat as false positives.
    secondary_ok = {
        "incorrect_payment",
        "missing_counterpart",
        "other",
        "date_mismatch",
    }

    for case in data["cases"]:
        ctx = seed_case(case)
        firm = ctx["firm"]

        ReconciliationEngine().match(firm.id)
        exceptions = list(
            ReconciliationException.objects.filter(firm=firm).select_related("transaction")
        )
        predicted_causes = {exc.mismatch_cause for exc in exceptions}
        expected_causes = {exp["mismatch_cause"] for exp in case.get("expected_exceptions", [])}
        banned = set(case.get("must_not_exception_causes", []))

        tp = expected_causes & predicted_causes
        fn = expected_causes - predicted_causes

        if expected_causes:
            fp = (predicted_causes - expected_causes - secondary_ok) | (predicted_causes & banned)
        elif banned:
            fp = predicted_causes & banned
        else:
            # Negative control: any exception is a false positive
            fp = set(predicted_causes)

        counts.tp += len(tp)
        counts.fp += len(fp)
        counts.fn += len(fn)

        details.append(
            {
                "case_id": case["case_id"],
                "expected_causes": sorted(expected_causes),
                "predicted_causes": sorted(predicted_causes),
                "predicted": [
                    {
                        "cause": e.mismatch_cause,
                        "txn_id": e.transaction_id,
                        "reason": e.reason[:120],
                    }
                    for e in exceptions
                ],
                "tp": len(tp),
                "fp": len(fp),
                "fn": len(fn),
                "ok": not fp and not fn,
            }
        )

    return SuiteResult(
        name="reconciliation",
        metrics={
            "precision": counts.precision,
            "recall": counts.recall,
            "f1": counts.f1,
            "tp": float(counts.tp),
            "fp": float(counts.fp),
            "fn": float(counts.fn),
        },
        details=details,
    )


def run_forecast_suite() -> SuiteResult:
    data = load_json("forecast_cases.json")
    passed = 0
    total = 0
    details: list[dict] = []

    for case in data["cases"]:
        ctx = seed_case(case)
        firm = ctx["firm"]
        as_of = ctx["as_of"]
        exp = case["expectations"]
        result = CashFlowForecaster().forecast(firm.id, as_of=as_of)

        checks: list[tuple[str, bool, str]] = []
        if "pressure_expected" in exp:
            has_pressure = result.pressure_day is not None
            ok = has_pressure is bool(exp["pressure_expected"])
            checks.append(
                (
                    "pressure",
                    ok,
                    f"expected={exp['pressure_expected']} got={has_pressure} day={result.pressure_day}",
                )
            )
        if "min_health_score" in exp:
            ok = result.health_score >= Decimal(str(exp["min_health_score"]))
            checks.append(("min_health", ok, f"score={result.health_score}"))
        if "max_health_score" in exp:
            ok = result.health_score <= Decimal(str(exp["max_health_score"]))
            checks.append(("max_health", ok, f"score={result.health_score}"))
        if "expected_current_balance" in exp:
            ok = result.current_balance == Decimal(str(exp["expected_current_balance"]))
            checks.append(
                ("balance", ok, f"got={result.current_balance} expected={exp['expected_current_balance']}")
            )
        for needle in exp.get("explanation_must_contain", []):
            ok = needle in (result.risk_explanation or "")
            checks.append(("citation", ok, f"need '{needle}'"))

        case_ok = all(c[1] for c in checks) if checks else False
        total += 1
        if case_ok:
            passed += 1
        details.append(
            {
                "case_id": case["case_id"],
                "ok": case_ok,
                "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
                "health_score": str(result.health_score),
                "pressure_day": result.pressure_day,
            }
        )

    accuracy = (passed / total) if total else 0.0
    return SuiteResult(
        name="cashflow_forecast",
        metrics={"accuracy": accuracy, "passed": float(passed), "total": float(total)},
        details=details,
    )


def run_agent_suite() -> SuiteResult:
    data = load_json("agent_cases.json")
    rates: list[float] = []
    details: list[dict] = []

    for case in data["cases"]:
        ctx = seed_case(case)
        firm = ctx["firm"]
        user = ctx["user"]
        conv = execute_agent(firm_id=firm.id, user=user, query=case["query"])
        response = conv.response or {}

        actions = list(AgentAction.objects.filter(conversation=conv))
        tool_results = {
            a.tool_name: a.tool_result
            for a in actions
            if isinstance(a.tool_result, dict) and not a.tool_result.get("_requires_approval")
        }

        gcfg = case.get("grounding", {})
        score = score_response_grounding(
            response,
            tool_results,
            firm.id,
            require_evidence_sources=gcfg.get("require_evidence_sources", True),
            require_entity_refs=gcfg.get("require_entity_refs", False),
            expected_entity_types=gcfg.get("entity_ref_types"),
        )

        # Also verify expected tools were invoked when specified
        tools_ok = True
        for t in case.get("expected_tools", []):
            if t not in tool_results and t not in (response.get("tools_called") or []):
                tools_ok = False
                score["notes"].append(f"expected tool not called: {t}")

        rates.append(score["grounding_rate"] if tools_ok else min(score["grounding_rate"], 0.5))
        details.append(
            {
                "case_id": case["case_id"],
                "grounding_rate": score["grounding_rate"],
                "claims_grounded": score["claims_grounded"],
                "claims_total": score["claims_total"],
                "tools_called": response.get("tools_called"),
                "notes": score["notes"],
                "ok": tools_ok and score["grounding_rate"] >= 0.9,
            }
        )

    avg = sum(rates) / len(rates) if rates else 0.0
    return SuiteResult(
        name="agent_grounding",
        metrics={
            "grounding_rate": avg,
            "cases": float(len(rates)),
        },
        details=details,
    )
