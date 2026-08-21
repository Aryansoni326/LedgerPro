"""Factual grounding checks for agent Evidence-Based AI responses."""
from __future__ import annotations

import re
from decimal import Decimal

from intelligence.models import Customer, RiskSignal, Transaction, Vendor

_AMOUNT_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+\.\d+)(?![\w.])")
_DAY_LABEL_RE = re.compile(
    r"\b\d{1,3}\s*-\s*day\b|\b(?:30|60|90)\s*days?\b|\bin\s+\d+\s+days?\b",
    re.IGNORECASE,
)
_FORECAST_WINDOW_NUMS = {"30", "60", "90"}


def _normalize_number(token: str) -> str:
    return str(Decimal(token.replace(",", "")))


def collect_tool_values(tool_results: dict) -> set[str]:
    """Flatten numeric / id strings present in tool payloads."""
    values: set[str] = set()

    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, bool):
            return
        elif isinstance(obj, (int, float, Decimal)):
            values.add(str(obj))
        elif isinstance(obj, str):
            if re.fullmatch(r"-?\d+(\.\d+)?", obj.replace(",", "")):
                values.add(_normalize_number(obj))

    walk(tool_results)
    return values


def extract_numeric_claims(text: str) -> list[str]:
    """Extract money-like numeric claims, ignoring forecast day-window labels."""
    scrubbed = _DAY_LABEL_RE.sub(" ", text or "")
    claims = []
    for match in _AMOUNT_RE.findall(scrubbed):
        try:
            norm = _normalize_number(match)
        except Exception:
            continue
        # Bare 30/60/90 almost always refer to forecast windows, not money.
        if norm in _FORECAST_WINDOW_NUMS and "." not in match:
            continue
        claims.append(norm)
    return claims


def entity_refs_grounded(entity_refs: list[dict], firm_id: int) -> tuple[int, int, list[str]]:
    """Return (grounded, total, failure_notes)."""
    grounded = 0
    failures: list[str] = []
    for ref in entity_refs or []:
        rtype = ref.get("type")
        rid = ref.get("id")
        ok = False
        if rtype == "transaction":
            ok = Transaction.objects.filter(firm_id=firm_id, id=rid).exists()
        elif rtype == "customer":
            ok = Customer.objects.filter(firm_id=firm_id, id=rid).exists()
        elif rtype == "vendor":
            ok = Vendor.objects.filter(firm_id=firm_id, id=rid).exists()
        elif rtype == "risk_signal":
            ok = RiskSignal.objects.filter(firm_id=firm_id, id=rid).exists()
        else:
            failures.append(f"unknown entity_ref type={rtype}")
            continue
        if ok:
            grounded += 1
        else:
            failures.append(f"missing {rtype}:{rid}")
    return grounded, len(entity_refs or []), failures


def score_response_grounding(
    response: dict,
    tool_results: dict,
    firm_id: int,
    *,
    require_evidence_sources: bool = True,
    require_entity_refs: bool = False,
    expected_entity_types: list[str] | None = None,
) -> dict:
    """
    Compute factual-grounding rate for one agent turn.

    A claim is grounded when:
      - numeric tokens in conclusion/reasoning appear in tool payloads, OR
      - entity_refs resolve to real firm-scoped rows
    Evidence items must cite a ``source`` tool name when required.
    """
    claims_total = 0
    claims_grounded = 0
    notes: list[str] = []

    evidence = response.get("evidence") or []
    if require_evidence_sources:
        claims_total += max(len(evidence), 1)
        if not evidence:
            notes.append("no evidence array")
        else:
            sourced = all("source" in ev for ev in evidence)
            if sourced:
                claims_grounded += len(evidence)
            else:
                notes.append("evidence missing source")
                claims_grounded += sum(1 for ev in evidence if "source" in ev)

    tool_values = collect_tool_values(tool_results)
    text = " ".join(
        [
            str(response.get("conclusion") or ""),
            str(response.get("reasoning") or ""),
        ]
    )
    numeric_claims = extract_numeric_claims(text)
    # Drop trivial confidence-like 0.xx already handled elsewhere; keep money-like
    for num in numeric_claims:
        # Skip very small decimals that are likely confidence
        try:
            d = Decimal(num)
            if Decimal("0") < d < Decimal("1"):
                continue
        except Exception:
            pass
        claims_total += 1
        if num in tool_values or any(
            num == v or num.endswith(v) or v.endswith(num) for v in tool_values
        ):
            claims_grounded += 1
        else:
            # Allow substring match for quantized money strings
            if any(num in v or v in num for v in tool_values):
                claims_grounded += 1
            else:
                notes.append(f"ungrounded number {num}")

    refs = response.get("entity_refs") or []
    if require_entity_refs or refs:
        g, total, fail_notes = entity_refs_grounded(refs, firm_id)
        claims_total += max(total, 1 if require_entity_refs else 0)
        claims_grounded += g
        notes.extend(fail_notes)
        if require_entity_refs and total == 0:
            notes.append("expected entity_refs but none present")
        if expected_entity_types:
            present = {r.get("type") for r in refs}
            for t in expected_entity_types:
                claims_total += 1
                if t in present:
                    claims_grounded += 1
                else:
                    notes.append(f"missing entity_ref type {t}")

    rate = (claims_grounded / claims_total) if claims_total else 1.0
    return {
        "grounding_rate": rate,
        "claims_grounded": claims_grounded,
        "claims_total": claims_total,
        "notes": notes,
    }
