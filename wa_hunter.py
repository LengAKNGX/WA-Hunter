#!/usr/bin/env python3
"""WA Hunter: dependency-free differential testing for integer-array programs."""

from __future__ import annotations

import argparse
import json
import os
import random
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    status: str
    output: str
    stderr: str
    elapsed_ms: float


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    defaults = {
        "iterations": 500,
        "seed": 20261002,
        "timeout_seconds": 1.0,
        "min_n": 1,
        "max_n": 40,
        "min_value": -100,
        "max_value": 100,
        "compiler": "g++",
        "compile_flags": ["-std=c++17", "-O2", "-Wall", "-Wextra"],
        "report": "report.md",
        "counterexample": "counterexample.txt",
    }
    defaults.update(cfg)
    if defaults["min_n"] < 1 or defaults["max_n"] < defaults["min_n"]:
        raise ValueError("Require 1 <= min_n <= max_n")
    if defaults["min_value"] > defaults["max_value"]:
        raise ValueError("Require min_value <= max_value")
    return defaults


def compile_cpp(source: Path, output: Path, cfg: dict) -> None:
    command = [cfg["compiler"], str(source), "-o", str(output), *cfg["compile_flags"]]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Compilation failed: {source}\n{result.stderr}")


def encode_case(values: list[int]) -> str:
    return f"{len(values)}\n{' '.join(map(str, values))}\n"


def run_program(executable: Path, values: list[int], timeout: float) -> RunResult:
    start = time.perf_counter()
    try:
        result = subprocess.run(
            [str(executable.resolve())], input=encode_case(values), capture_output=True,
            text=True, timeout=timeout,
        )
        status = "ok" if result.returncode == 0 else f"runtime_error({result.returncode})"
        return RunResult(status, result.stdout.strip(), result.stderr.strip(),
                         (time.perf_counter() - start) * 1000)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return RunResult("timeout", stdout.strip(), stderr.strip(),
                         (time.perf_counter() - start) * 1000)


def differs(a: RunResult, b: RunResult) -> bool:
    return a.status != b.status or a.output.split() != b.output.split()


class ArrayGenerator:
    STRATEGIES = [
        "random", "boundary", "all_equal", "increasing", "decreasing",
        "many_duplicates", "extreme_mix",
    ]

    def __init__(self, cfg: dict, rng: random.Random):
        self.cfg, self.rng = cfg, rng
        self.weights = {name: 1 for name in self.STRATEGIES}
        self.cursor = 0

    def next_case(self) -> tuple[str, list[int]]:
        # Guarantee coverage first; later select strategies using feedback-adjusted weights.
        if self.cursor < len(self.STRATEGIES):
            strategy = self.STRATEGIES[self.cursor]
            self.cursor += 1
        else:
            strategy = self.rng.choices(
                self.STRATEGIES, weights=[self.weights[x] for x in self.STRATEGIES], k=1
            )[0]
        return strategy, self._make(strategy)

    def feedback(self, strategy: str, interesting: bool) -> None:
        # Agent feedback: favor strategies producing a failure or unusual execution status.
        self.weights[strategy] = min(8, self.weights[strategy] + (3 if interesting else 0))

    def _n(self) -> int:
        return self.rng.randint(self.cfg["min_n"], self.cfg["max_n"])

    def _make(self, strategy: str) -> list[int]:
        lo, hi, n = self.cfg["min_value"], self.cfg["max_value"], self._n()
        if strategy == "random":
            return [self.rng.randint(lo, hi) for _ in range(n)]
        if strategy == "boundary":
            # All-negative data catches a common max-subarray initialization bug.
            negatives = [x for x in (lo, -1) if lo <= x <= hi and x < 0]
            if negatives:
                return [self.rng.choice(negatives) for _ in range(n)]
            return [lo, hi][:n] if n <= 2 else [lo] + [hi] * (n - 1)
        if strategy == "all_equal":
            return [self.rng.choice([lo, hi, 0] if lo <= 0 <= hi else [lo, hi])] * n
        if strategy == "increasing":
            return sorted(self.rng.randint(lo, hi) for _ in range(n))
        if strategy == "decreasing":
            return sorted((self.rng.randint(lo, hi) for _ in range(n)), reverse=True)
        if strategy == "many_duplicates":
            pool = [self.rng.randint(lo, hi) for _ in range(min(3, n))]
            return [self.rng.choice(pool) for _ in range(n)]
        pool = [lo, hi]
        if lo <= 0 <= hi:
            pool.append(0)
        return [pool[i % len(pool)] for i in range(n)]


def minimize(values: list[int], predicate, min_value: int | None = None,
             max_value: int | None = None) -> tuple[list[int], int]:
    current, checks = values[:], 0
    # Delta debugging by chunks: remove increasingly small portions while failure remains.
    granularity = 2
    while len(current) >= 2:
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
        if not reduced:
            if granularity >= len(current):
                break
            granularity = min(len(current), granularity * 2)

    # Greedily shrink each value toward simple representatives.
    for i in range(len(current)):
        original = current[i]
        candidates = [0]
        if original != 0:
            candidates += [1 if original > 0 else -1]
            x = original
            while abs(x) > 1:
                x = int(x / 2)
                candidates.append(x)
        for value in dict.fromkeys(candidates):
            if min_value is not None and value < min_value:
                continue
            if max_value is not None and value > max_value:
                continue
            if value == current[i]:
                continue
            candidate = current[:]
            candidate[i] = value
            checks += 1
            if predicate(candidate):
                current = candidate
                break
    return current, checks


def fenced(text: str) -> str:
    return text if text else "(empty)"


def write_report(path: Path, original: list[int], minimized: list[int], strategy: str,
                 iteration: int, sol: RunResult, brute: RunResult, checks: int, cfg: dict) -> None:
    content = f"""# WA Hunter Report

## Result

Counterexample found on iteration **{iteration}** using strategy **{strategy}**.
The original case had {len(original)} element(s); minimization reduced it to {len(minimized)}.

## Minimized counterexample

```text
{encode_case(minimized).rstrip()}
```

## Program behavior

| Program | Status | Time | Output |
|---|---|---:|---|
| solution | {sol.status} | {sol.elapsed_ms:.2f} ms | `{fenced(sol.output)}` |
| brute | {brute.status} | {brute.elapsed_ms:.2f} ms | `{fenced(brute.output)}` |

## Minimization

- Deletion and value-shrinking checks: {checks}
- Random seed: {cfg['seed']}
- Run budget: {cfg['iterations']} iterations
- Output comparison ignores whitespace differences.

## Reproduce

Run the compiled programs with the contents of `{cfg['counterexample']}` as standard input.
"""
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Find and minimize counterexamples by differential testing.")
    parser.add_argument("--solution", default="examples/solution.cpp")
    parser.add_argument("--brute", default="examples/brute.cpp")
    parser.add_argument("--config", default="examples/config.json")
    args = parser.parse_args()

    root = Path.cwd()
    cfg = load_config(root / args.config)
    # Do not leave a counterexample from an earlier run beside a clean report.
    (root / cfg["counterexample"]).unlink(missing_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    build = root / ".wa_hunter_build"
    build.mkdir(exist_ok=True)
    solution_exe, brute_exe = build / f"solution{suffix}", build / f"brute{suffix}"
    print("[agent] compiling candidate and oracle...")
    compile_cpp(root / args.solution, solution_exe, cfg)
    compile_cpp(root / args.brute, brute_exe, cfg)

    rng, generator = random.Random(cfg["seed"]), ArrayGenerator(cfg, random.Random(cfg["seed"]))
    del rng  # generator owns the deterministic random stream
    for iteration in range(1, cfg["iterations"] + 1):
        strategy, values = generator.next_case()
        sol = run_program(solution_exe, values, cfg["timeout_seconds"])
        brute = run_program(brute_exe, values, cfg["timeout_seconds"])
        failed = differs(sol, brute)
        generator.feedback(strategy, failed or sol.status != "ok" or brute.status != "ok")
        print(f"[agent] iteration={iteration} strategy={strategy} n={len(values)} result={'DIFF' if failed else 'same'}")
        if not failed:
            continue

        def still_fails(candidate: list[int]) -> bool:
            return differs(run_program(solution_exe, candidate, cfg["timeout_seconds"]),
                           run_program(brute_exe, candidate, cfg["timeout_seconds"]))

        minimized, checks = minimize(
            values, still_fails, cfg["min_value"], cfg["max_value"]
        )
        final_sol = run_program(solution_exe, minimized, cfg["timeout_seconds"])
        final_brute = run_program(brute_exe, minimized, cfg["timeout_seconds"])
        counterexample = root / cfg["counterexample"]
        report = root / cfg["report"]
        counterexample.write_text(encode_case(minimized), encoding="utf-8")
        write_report(report, values, minimized, strategy, iteration, final_sol, final_brute, checks, cfg)
        print(f"[agent] minimized {len(values)} -> {len(minimized)} elements ({checks} checks)")
        print(f"[agent] saved {counterexample} and {report}")
        return 1

    report = root / cfg["report"]
    report.write_text(
        f"# WA Hunter Report\n\nNo discrepancy found in {cfg['iterations']} iterations "
        f"(seed `{cfg['seed']}`). This is not a proof of correctness.\n", encoding="utf-8"
    )
    print(f"[agent] no discrepancy found; saved {report}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"WA Hunter error: {exc}", file=sys.stderr)
        sys.exit(2)
