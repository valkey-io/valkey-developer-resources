#!/usr/bin/env python3
"""Summarize one benchmark run as a Markdown table.

Reads results/<run>/<strategy>/stage_N_lifecycle_metrics.json (written by
inference-perf) and prints, for each strategy and concurrency level, the
time-to-first-token percentiles, throughput, and the share of prompt tokens
vLLM served from its prefix cache. Stage 0 is the warm-up and is skipped.

Usage: summarize.py results/<run>

Standard library only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

STRATEGY_ORDER = ("random", "approximate", "precise-memory", "precise-valkey")


def ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 1000:,.0f}"


def stage_rows(strategy_dir: Path):
    stage_files = sorted(
        strategy_dir.rglob("stage_*_lifecycle_metrics.json"),
        key=lambda p: int(p.name.split("_")[1]),
    )
    for path in stage_files:
        stage = int(path.name.split("_")[1])
        if stage == 0:
            continue
        report = json.loads(path.read_text())
        ok = report.get("successes") or {}
        failed = (report.get("failures") or {}).get("count", 0)
        ttft = (ok.get("latency") or {}).get("time_to_first_token") or {}
        prompt = ok.get("prompt_tokens") or {}
        total, cached = prompt.get("total") or 0, prompt.get("cached") or 0
        throughput = ok.get("throughput") or {}
        yield {
            "concurrency": (report.get("load_summary") or {}).get("concurrency", "?"),
            "requests": ok.get("count", 0),
            "failed": failed,
            "p50": ttft.get("median"),
            "p90": ttft.get("p90"),
            "p99": ttft.get("p99"),
            "hit": f"{100 * cached / total:.0f}%" if total else "n/a",
            "rps": throughput.get("requests_per_sec"),
        }


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    run_dir = Path(sys.argv[1])
    present = {p.name for p in run_dir.iterdir() if p.is_dir()}
    strategies = [s for s in STRATEGY_ORDER if s in present] + sorted(present - set(STRATEGY_ORDER))

    print("| Strategy | Concurrency | Requests (failed) | TTFT p50 ms | TTFT p90 ms | TTFT p99 ms | Prompt tokens from cache | Requests/s |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for strategy in strategies:
        for row in stage_rows(run_dir / strategy):
            rps = "n/a" if row["rps"] is None else f"{row['rps']:.2f}"
            print(
                f"| {strategy} | {row['concurrency']} | {row['requests']} ({row['failed']}) "
                f"| {ms(row['p50'])} | {ms(row['p90'])} | {ms(row['p99'])} | {row['hit']} | {rps} |"
            )


if __name__ == "__main__":
    main()
