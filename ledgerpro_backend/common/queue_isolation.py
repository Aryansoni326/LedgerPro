"""
Simulate concurrent Celery-style queue isolation (no Redis required).

Used by ``scripts/test_queue_isolation.py`` and CI tests to prove extraction
latency stays under SLA while the agents queue is saturated.
"""
from __future__ import annotations

import statistics
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue

EXTRACTION_SLA_SEC = 0.50
AGENT_WORK_SEC = 0.40
EXTRACTION_WORK_SEC = 0.05
NUM_AGENT_JOBS = 24
NUM_EXTRACTION_JOBS = 20
AGENTS_WORKERS = 2
EXTRACTION_WORKERS = 4


@dataclass
class Job:
    kind: str
    job_id: int
    work_sec: float
    enqueued_at: float = field(default_factory=time.perf_counter)


@dataclass
class Result:
    kind: str
    job_id: int
    wait_sec: float
    run_sec: float


def _worker_loop(q: Queue, results: list, lock: threading.Lock, stop: threading.Event):
    while not stop.is_set():
        try:
            job: Job = q.get(timeout=0.05)
        except Empty:
            continue
        start = time.perf_counter()
        wait = start - job.enqueued_at
        time.sleep(job.work_sec)
        run = time.perf_counter() - start
        with lock:
            results.append(Result(job.kind, job.job_id, wait, run))
        q.task_done()


def run_isolation_simulation(*, shared_pool: bool = False) -> dict:
    """
    shared_pool=False — Compose model: separate extraction vs agents workers
    shared_pool=True  — anti-pattern: one pool prefers agents (starves extraction)
    """
    extraction_q: Queue = Queue()
    agents_q: Queue = Queue()
    results: list[Result] = []
    lock = threading.Lock()
    stop = threading.Event()
    threads: list[threading.Thread] = []

    if shared_pool:
        def shared_loop():
            while not stop.is_set():
                job = None
                try:
                    job = agents_q.get_nowait()
                except Empty:
                    try:
                        job = extraction_q.get_nowait()
                    except Empty:
                        time.sleep(0.01)
                        continue
                start = time.perf_counter()
                wait = start - job.enqueued_at
                time.sleep(job.work_sec)
                run = time.perf_counter() - start
                with lock:
                    results.append(Result(job.kind, job.job_id, wait, run))
                if job.kind == "agent":
                    agents_q.task_done()
                else:
                    extraction_q.task_done()

        for _ in range(AGENTS_WORKERS + EXTRACTION_WORKERS):
            t = threading.Thread(target=shared_loop, daemon=True)
            t.start()
            threads.append(t)
    else:
        for _ in range(EXTRACTION_WORKERS):
            t = threading.Thread(
                target=_worker_loop, args=(extraction_q, results, lock, stop), daemon=True,
            )
            t.start()
            threads.append(t)
        for _ in range(AGENTS_WORKERS):
            t = threading.Thread(
                target=_worker_loop, args=(agents_q, results, lock, stop), daemon=True,
            )
            t.start()
            threads.append(t)

    for i in range(NUM_AGENT_JOBS):
        agents_q.put(Job("agent", i, AGENT_WORK_SEC))
    time.sleep(0.02)
    for i in range(NUM_EXTRACTION_JOBS):
        extraction_q.put(Job("extraction", i, EXTRACTION_WORK_SEC))

    deadline = time.perf_counter() + 30
    while time.perf_counter() < deadline:
        with lock:
            done_ext = sum(1 for r in results if r.kind == "extraction")
            done_agent = sum(1 for r in results if r.kind == "agent")
        if done_ext >= NUM_EXTRACTION_JOBS and done_agent >= NUM_AGENT_JOBS:
            break
        time.sleep(0.02)

    stop.set()
    for t in threads:
        t.join(timeout=1)

    ext = [r for r in results if r.kind == "extraction"]
    waits = [r.wait_sec for r in ext]
    if not waits:
        raise RuntimeError("No extraction jobs completed — simulation broken")

    waits_sorted = sorted(waits)
    p95 = waits_sorted[max(0, int(len(waits_sorted) * 0.95) - 1)]
    return {
        "shared_pool": shared_pool,
        "extraction_count": len(ext),
        "extraction_wait_p50": statistics.median(waits),
        "extraction_wait_p95": p95,
        "extraction_wait_max": max(waits),
        "sla_sec": EXTRACTION_SLA_SEC,
        "sla_met": p95 <= EXTRACTION_SLA_SEC,
    }
