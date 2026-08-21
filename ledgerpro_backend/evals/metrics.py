"""Metric helpers for non-deterministic / detection-style evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfusionCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add_tp(self, n: int = 1) -> None:
        self.tp += n

    def add_fp(self, n: int = 1) -> None:
        self.fp += n

    def add_fn(self, n: int = 1) -> None:
        self.fn += n

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return (self.tp / denom) if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return (self.tp / denom) if denom else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r / (p + r)) if (p + r) else 0.0


@dataclass
class SuiteResult:
    name: str
    metrics: dict[str, float] = field(default_factory=dict)
    details: list[dict] = field(default_factory=list)
    passed: bool = True
    failures: list[str] = field(default_factory=list)

    def check_thresholds(self, thresholds: dict[str, float], metric_map: dict[str, str]) -> None:
        """metric_map: suite_metric_key -> threshold_key."""
        for metric_key, threshold_key in metric_map.items():
            value = self.metrics.get(metric_key)
            floor = thresholds[threshold_key]
            if value is None:
                self.passed = False
                self.failures.append(f"{self.name}: missing metric '{metric_key}'")
                continue
            if value < floor:
                self.passed = False
                self.failures.append(
                    f"{self.name}: {metric_key}={value:.3f} < threshold {floor:.3f} ({threshold_key})"
                )
