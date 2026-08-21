#!/usr/bin/env python
"""CLI wrapper — see common.queue_isolation and docs/SCALING.md."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.queue_isolation import run_isolation_simulation


def main() -> int:
    isolated = run_isolation_simulation(shared_pool=False)
    coupled = run_isolation_simulation(shared_pool=True)

    print("=== Queue isolation simulation ===")
    print(f"Isolated workers (Compose model): {isolated}")
    print(f"Shared pool (anti-pattern):       {coupled}")

    if not isolated["sla_met"]:
        print("FAIL: isolated extraction p95 exceeded SLA")
        return 1
    print("PASS: extraction SLA held under concurrent agent load (isolated queues)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
