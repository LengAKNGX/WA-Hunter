"""Shared deterministic search primitives for the CLI and hosted service.

This module deliberately has no web, subprocess, database, or third-party
dependencies.  Keeping generation and minimization here prevents the local CLI
and production worker from silently developing different search semantics.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping


STRATEGIES = (
    "random", "boundary", "all_equal", "increasing", "decreasing",
    "many_duplicates", "extreme_mix",
)


def encode_case(values: list[int]) -> str:
    return f"{len(values)}\n{' '.join(map(str, values))}\n"


class ArrayGenerator:
    """Generate reproducible integer-array cases with feedback-adjusted weights."""

    STRATEGIES = list(STRATEGIES)
    strategies = STRATEGIES  # Backward-compatible hosted-service attribute.

    def __init__(self, config: Mapping, rng: random.Random | None = None):
        self.cfg = config
        self.lo, self.hi = config["min_value"], config["max_value"]
        self.min_n, self.max_n = config["min_n"], config["max_n"]
        self.rng = rng or random.Random(config["seed"])
        self.cursor = 0
        self.weights = {name: 1 for name in self.STRATEGIES}

    def next_case(self) -> tuple[str, list[int]]:
        # Cover every structural strategy before weighted exploration begins.
        if self.cursor < len(self.STRATEGIES):
            strategy = self.STRATEGIES[self.cursor]
            self.cursor += 1
        else:
            strategy = self.rng.choices(
                self.STRATEGIES,
                weights=[self.weights[name] for name in self.STRATEGIES],
                k=1,
            )[0]
        return strategy, self._make(strategy)

    def next(self) -> tuple[str, list[int]]:
        """Hosted-service compatibility alias."""
        return self.next_case()

    def feedback(self, strategy: str, interesting: bool) -> None:
        if interesting:
            self.weights[strategy] = min(8, self.weights[strategy] + 3)

    def _make(self, strategy: str) -> list[int]:
        lo, hi = self.lo, self.hi
        n = self.rng.randint(self.min_n, self.max_n)
        if strategy == "random":
            return [self.rng.randint(lo, hi) for _ in range(n)]
        if strategy == "boundary":
            # Prefer an all-negative boundary case when legal: it exposes a
            # common max-subarray initialization bug. extreme_mix still covers hi.
            negatives = [value for value in (lo, -1) if lo <= value <= hi and value < 0]
            pool = negatives or [lo, hi]
            return [pool[index % len(pool)] for index in range(n)]
        if strategy == "all_equal":
            pool = [lo, hi] + ([0] if lo <= 0 <= hi else [])
            return [self.rng.choice(pool)] * n
        if strategy == "increasing":
            return sorted(self.rng.randint(lo, hi) for _ in range(n))
        if strategy == "decreasing":
            return sorted((self.rng.randint(lo, hi) for _ in range(n)), reverse=True)
        if strategy == "many_duplicates":
            pool = [self.rng.randint(lo, hi) for _ in range(min(3, n))]
            return [self.rng.choice(pool) for _ in range(n)]
        pool = [lo, hi] + ([0] if lo <= 0 <= hi else [])
        return [pool[index % len(pool)] for index in range(n)]


def minimize(
    values: list[int],
    predicate: Callable[[list[int]], bool],
    min_value: int | None = None,
    max_value: int | None = None,
    *,
    max_checks: int | None = None,
) -> tuple[list[int], int]:
    """Shrink a failing case by deletion and value reduction.

    ``max_checks`` lets the hosted service enforce a hard resource budget while
    the local CLI may run the minimizer to its normal fixed point.
    """

    current, checks, granularity = values[:], 0, 2

    def budget_available() -> bool:
        return max_checks is None or checks < max_checks

    while len(current) >= 2 and budget_available():
        chunk = max(1, (len(current) + granularity - 1) // granularity)
        reduced = False
        for start in range(0, len(current), chunk):
            candidate = current[:start] + current[start + chunk:]
            if not candidate:
                continue
            checks += 1
            if predicate(candidate):
                current, reduced = candidate, True
                granularity = max(2, granularity - 1)
                break
            if not budget_available():
                break
        if not reduced:
            if granularity >= len(current):
                break
            granularity = min(len(current), granularity * 2)

    for index in range(len(current)):
        if not budget_available():
            break
        original = current[index]
        candidates = [0]
        if original != 0:
            candidates.append(1 if original > 0 else -1)
            value = original
            while abs(value) > 1:
                value = value // 2 if value >= 0 else -((-value) // 2)
                candidates.append(value)
        for value in dict.fromkeys(candidates):
            if min_value is not None and value < min_value:
                continue
            if max_value is not None and value > max_value:
                continue
            if value == current[index]:
                continue
            candidate = current[:]
            candidate[index] = value
            checks += 1
            if predicate(candidate):
                current = candidate
                break
            if not budget_available():
                break
    return current, checks
