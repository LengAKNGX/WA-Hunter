#!/usr/bin/env python3
"""WA Hunter: dependency-free differential testing for integer-array programs."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from server.core import ArrayGenerator, HuntEngine, SearchStats, encode_case, minimize


@dataclass
class RunResult:
    status: str
    output: str
    stderr: str
    elapsed_ms: float


HuntStats = SearchStats  # Backward-compatible public name used by existing reports/tests.


def coverage_markdown(stats: HuntStats, elapsed_ms: float) -> str:
    rows = "\n".join(
        f"| {name} | {stats.strategy_counts.get(name, 0)} |"
        for name in ArrayGenerator.STRATEGIES
    )
    average_n = stats.total_elements / stats.cases if stats.cases else 0
    return f"""## Test coverage

- Executed cases: {stats.cases}
- Generated elements: {stats.total_elements}
- Average / maximum n: {average_n:.1f} / {stats.max_n}
- Total hunt time: {elapsed_ms:.2f} ms
- Non-OK runs: solution {stats.solution_non_ok}, brute {stats.brute_non_ok}

| Strategy | Cases |
|---|---:|
{rows}
"""


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
        "progress_interval": 25,
    }
    defaults.update(cfg)
    if defaults["min_n"] < 1 or defaults["max_n"] < defaults["min_n"]:
        raise ValueError("Require 1 <= min_n <= max_n")
    if defaults["min_value"] > defaults["max_value"]:
        raise ValueError("Require min_value <= max_value")
    if defaults["progress_interval"] < 1:
        raise ValueError("Require progress_interval >= 1")
    return defaults


def compile_cpp(source: Path, output: Path, cfg: dict) -> None:
    command = [cfg["compiler"], str(source), "-o", str(output), *cfg["compile_flags"]]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Compilation failed: {source}\n{result.stderr}")


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


def should_log_iteration(iteration: int, failed: bool, progress_interval: int) -> bool:
    """Keep logs readable while always showing initial strategy coverage and failures."""
    return failed or iteration <= len(ArrayGenerator.STRATEGIES) or iteration % progress_interval == 0


def fenced(text: str) -> str:
    return text if text else "(empty)"


def write_report(path: Path, original: list[int], minimized: list[int], strategy: str,
                 iteration: int, sol: RunResult, brute: RunResult, checks: int, cfg: dict,
                 stats: HuntStats, elapsed_ms: float) -> None:
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

{coverage_markdown(stats, elapsed_ms)}

## Minimization

- Deletion and value-shrinking checks: {checks}
- Random seed: {cfg['seed']}
- Run budget: {cfg['iterations']} iterations
- Output comparison ignores whitespace differences.

## Reproduce

Run the compiled programs with the contents of `{cfg['counterexample']}` as standard input.
"""
    path.write_text(content, encoding="utf-8")


def write_no_difference_report(path: Path, cfg: dict, stats: HuntStats, elapsed_ms: float) -> None:
    content = f"""# WA Hunter Report

## Result

No discrepancy was found within the configured test budget. This means only that
the candidate and oracle behaved the same on the generated cases; it is **not a
proof of correctness**.

{coverage_markdown(stats, elapsed_ms)}

## Reproduce

- Random seed: {cfg['seed']}
- Requested run budget: {cfg['iterations']} iterations
- n range: [{cfg['min_n']}, {cfg['max_n']}]
- value range: [{cfg['min_value']}, {cfg['max_value']}]

Increase the budget, adjust the legal range, or add problem-specific strategies
before drawing a stronger conclusion.
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

    def run_pair(values: list[int]) -> tuple[RunResult, RunResult]:
        return (
            run_program(solution_exe, values, cfg["timeout_seconds"]),
            run_program(brute_exe, values, cfg["timeout_seconds"]),
        )

    def log_case(iteration, strategy, values, _solution, _brute, failed):
        if should_log_iteration(iteration, failed, cfg["progress_interval"]):
            print(
                f"[agent] iteration={iteration} strategy={strategy} "
                f"n={len(values)} result={'DIFF' if failed else 'same'}"
            )

    outcome = HuntEngine(cfg, run_pair, differs).run(cfg["iterations"], log_case)
    if outcome.found:
        counterexample = root / cfg["counterexample"]
        report = root / cfg["report"]
        counterexample.write_text(encode_case(outcome.minimized), encoding="utf-8")
        write_report(
            report, outcome.original, outcome.minimized, outcome.strategy,
            outcome.iteration, outcome.solution, outcome.brute,
            outcome.minimize_checks, cfg, outcome.stats, outcome.stats.elapsed_ms,
        )
        print(
            f"[agent] minimized {len(outcome.original)} -> {len(outcome.minimized)} "
            f"elements ({outcome.minimize_checks} checks)"
        )
        print(f"[agent] saved {counterexample} and {report}")
        return 1

    report = root / cfg["report"]
    write_no_difference_report(report, cfg, outcome.stats, outcome.stats.elapsed_ms)
    print(f"[agent] no discrepancy found; saved {report}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"WA Hunter error: {exc}", file=sys.stderr)
        sys.exit(2)
