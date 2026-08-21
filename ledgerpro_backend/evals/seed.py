"""Seed labeled synthetic firms from eval dataset JSON."""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from accounts.models import User
from firms.models import Firm
from intelligence.models import Customer, RiskSignal, Transaction, Vendor

DATASET_DIR = Path(__file__).resolve().parent / "dataset"


def load_json(name: str) -> dict:
    with open(DATASET_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _resolve_date(token: str | None, as_of: date) -> date | None:
    if token is None or token == "":
        return None
    if isinstance(token, str) and (token.startswith("+") or token.startswith("-") or token == "0"):
        return as_of + timedelta(days=int(token))
    return date.fromisoformat(str(token))


def create_eval_firm(case_id: str, as_of: date) -> tuple[Firm, User]:
    suffix = uuid.uuid4().hex[:8]
    email = f"eval-{case_id}-{suffix}@ledgerpro.eval".replace("_", "-")[:100]
    user = User.objects.create_user(
        username=email,
        email=email,
        password="unused-eval",
    )
    firm = Firm.objects.create(
        name=f"Eval {case_id} {suffix}"[:100],
        state="Karnataka",
        city="Bengaluru",
        owner_email=email,
        created_by=user,
        status="active",
        base_currency="INR",
    )
    return firm, user


def seed_parties(firm: Firm, case: dict) -> tuple[dict[str, Vendor], dict[str, Customer]]:
    vendors: dict[str, Vendor] = {}
    customers: dict[str, Customer] = {}
    for v in case.get("vendors", []):
        vendors[v["key"]] = Vendor.objects.create(firm=firm, name=v["name"])
    for c in case.get("customers", []):
        customers[c["key"]] = Customer.objects.create(firm=firm, name=c["name"])
    return vendors, customers


def seed_transactions(
    firm: Firm,
    case: dict,
    vendors: dict[str, Vendor],
    customers: dict[str, Customer],
    as_of: date,
) -> dict[str, Transaction]:
    keyed: dict[str, Transaction] = {}
    for spec in case.get("transactions", []):
        kwargs = {
            "firm": firm,
            "txn_type": spec["txn_type"],
            "direction": spec["direction"],
            "status": spec.get("status", "pending"),
            "reference_number": spec.get("reference_number", ""),
            "amount": Decimal(str(spec["amount"])),
            "currency": spec.get("currency", "INR"),
            "txn_date": _resolve_date(spec["txn_date"], as_of),
            "description": spec.get("description", f"eval:{spec['key']}"),
        }
        if "due_date" in spec:
            kwargs["due_date"] = _resolve_date(spec["due_date"], as_of)
        if spec.get("vendor"):
            kwargs["vendor"] = vendors[spec["vendor"]]
        if spec.get("customer"):
            kwargs["customer"] = customers[spec["customer"]]
        keyed[spec["key"]] = Transaction.objects.create(**kwargs)
    return keyed


def seed_risk_signals(
    firm: Firm,
    specs: list[dict],
    txns: dict[str, Transaction],
) -> list[RiskSignal]:
    created = []
    for spec in specs:
        entity_id = txns[spec["entity_key"]].id if spec.get("entity_key") else spec.get("entity_id", 0)
        created.append(
            RiskSignal.objects.create(
                firm=firm,
                severity=spec.get("severity", "medium"),
                category=spec["category"],
                status=spec.get("status", "open"),
                title=spec["title"],
                description=spec["description"],
                confidence=Decimal(str(spec.get("confidence", "0.8500"))),
                entity_type=spec.get("entity_type", "transaction"),
                entity_id=entity_id,
            )
        )
    return created


def seed_case(case: dict, as_of: date | None = None) -> dict:
    """Seed one labeled case. Returns context dict used by runners."""
    as_of = as_of or date.today()
    firm, user = create_eval_firm(case["case_id"], as_of)
    seed_block = case.get("seed", case)
    vendors, customers = seed_parties(firm, seed_block)
    txns = seed_transactions(firm, seed_block, vendors, customers, as_of)
    signals = seed_risk_signals(firm, seed_block.get("risk_signals", []), txns)
    return {
        "case": case,
        "firm": firm,
        "user": user,
        "vendors": vendors,
        "customers": customers,
        "transactions": txns,
        "signals": signals,
        "as_of": as_of,
    }
