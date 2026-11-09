#!/usr/bin/env python3
"""Summarize one benchmark run as Markdown tables.

Usage: summarize.py results/<run> [--json results/<run>/summary.json]

Reads, for every configuration, run and concurrency level:

  <config>/run-<n>/c<level>/**/stage_0_lifecycle_metrics.json
      inference-perf's report: TTFT percentiles, requests/s, failures
  <config>/run-<n>/c<level>/counters-{before,after}.json
      vLLM's counters on every replica, read just before and just after the
      stage (benchctl.py snapshot). The difference gives the prompt tokens
      served from each replica's GPU prefix cache (local) and from LMCache,
      from its L1 memory or from Valkey (external), as shares of all prompt
      tokens. <config>/run-<n>/lmcache-server.log splits LMCache's lookups
      into L1 and Valkey chunks.
  <config>/run-<n>/valkey.json
      Valkey's memory and key counts after the run (benchctl.py valkey-stats)

For each configuration and concurrency level it prints the median of the
runs, with the spread (min-max) in brackets. The warm-up stage is skipped.
The metadata line (metadata.json) is printed above every table.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

from benchctl import CONFIGS, GIB
from metadata import metadata_line

METRICS = ("ttft_p50", "ttft_p90", "ttft_p99", "requests_per_s", "local_share", "valkey_share", "usage_cached_share")


# Files that couldn't be read or had the wrong shape. render() lists them
# under the tables, so a partial run directory still gets a summary.
SKIPPED: list[str] = []


def read_json(path: Path, what: str) -> dict | None:
    """Parse a JSON object, or record the file as skipped and return None."""
    try:
        data = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        SKIPPED.append(f"{path} ({what}): {exc}")
        return None
    if not isinstance(data, dict):
        SKIPPED.append(f"{path} ({what}): not a JSON object")
        return None
    return data


def counter_delta(before: dict, after: dict, name: str) -> float | None:
    """Sum over replicas of (after - before) for one counter; None if a
    snapshot is malformed (e.g. a replica missing from one of them)."""
    try:
        return sum(after["replicas"][r].get(name, 0.0) - before["replicas"][r].get(name, 0.0)
                   for r in after["replicas"])
    except (KeyError, TypeError, AttributeError):
        return None


def stage_metrics(stage_dir: Path) -> dict | None:
    reports = list(stage_dir.rglob("stage_0_lifecycle_metrics.json"))
    if not reports:
        return None
    report = read_json(reports[0], "inference-perf report")
    if report is None:
        return None  # treated like a missing report
    ok = report.get("successes") or {}
    ttft = (ok.get("latency") or {}).get("time_to_first_token") or {}
    prompt = ok.get("prompt_tokens") or {}
    row = {
        "requests": ok.get("count", 0),
        "failed": (report.get("failures") or {}).get("count", 0),
        "ttft_p50": ttft.get("median"),
        "ttft_p90": ttft.get("p90"),
        "ttft_p99": ttft.get("p99"),
        "requests_per_s": (ok.get("throughput") or {}).get("requests_per_sec"),
        # vLLM's per-response cached_tokens (local + external), as a check on
        # the counter-based split below.
        "usage_cached_share": (prompt.get("cached") or 0) / prompt["total"] if prompt.get("total") else None,
        "local_share": None,
        "valkey_share": None,
    }
    before, after = stage_dir / "counters-before.json", stage_dir / "counters-after.json"
    if before.exists() and after.exists():
        b, a = read_json(before, "counter snapshot"), read_json(after, "counter snapshot")
        if b is not None and a is not None:
            prompt_tokens = counter_delta(b, a, "vllm:prompt_tokens_total")
            local = counter_delta(b, a, "vllm:prefix_cache_hits_total")
            external = counter_delta(b, a, "vllm:external_prefix_cache_hits_total")
            if None in (prompt_tokens, local, external):
                SKIPPED.append(f"{stage_dir} (counter snapshots): malformed, no cache-hit split")
            elif prompt_tokens > 0:
                row["local_share"] = local / prompt_tokens
                row["valkey_share"] = external / prompt_tokens
    return row


def spread(values: list[float | None]) -> dict | None:
    """Median and min/max of the runs that produced a value."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    return {"median": statistics.median(present), "min": min(present), "max": max(present), "n": len(present)}


def _level(stage: str) -> int:
    return int(stage[1:])


def collect(run_dir: Path) -> dict:
    """{config: {level: {"runs": n, "failed": [..], metric: spread}}}"""
    present = {p.name for p in run_dir.iterdir() if p.is_dir()}
    configs = [c for c in CONFIGS if c in present] + sorted(present - set(CONFIGS))
    out: dict = {}
    for config in configs:
        per_level: dict[int, list[dict]] = {}
        for run in sorted((run_dir / config).glob("run-*")):
            for stage_dir in run.iterdir():
                if stage_dir.is_dir() and re.fullmatch(r"c\d+", stage_dir.name):
                    row = stage_metrics(stage_dir)
                    if row is not None:
                        per_level.setdefault(_level(stage_dir.name), []).append(row)
        if not per_level:
            continue
        out[config] = {}
        for level in sorted(per_level):
            rows = per_level[level]
            out[config][level] = {
                "runs": len(rows),
                "requests": [r["requests"] for r in rows],
                "failed": [r["failed"] for r in rows],
                **{m: spread([r[m] for r in rows]) for m in METRICS},
            }
    return out


def valkey_runs(run_dir: Path) -> list[dict]:
    rows = []
    for config in [c for c in CONFIGS if (run_dir / c).is_dir()] + sorted(
            p.name for p in run_dir.iterdir() if p.is_dir() and p.name not in CONFIGS):
        for run in sorted((run_dir / config).glob("run-*")):
            stats = run / "valkey.json"
            if not stats.exists():
                continue
            after = read_json(stats, "Valkey stats")
            if after is None or not isinstance(after.get("used_memory"), int | float):
                if after is not None:
                    SKIPPED.append(f"{stats} (Valkey stats): no used_memory")
                continue
            start = run / "valkey-before.json"
            before = (read_json(start, "Valkey stats") or {}) if start.exists() else {}
            # INFO keyspace omits empty databases, so a recorded snapshot
            # without db1 means the index was empty; no snapshot means unknown.
            rows.append({"config": config, "run": run.name.removeprefix("run-"), "after": after,
                         "index_keys_at_start": (before.get("keys_per_db") or {}).get("db1", 0) if before else None,
                         "lookups": lmcache_lookups(run / "lmcache-server.log")})
    return rows


# lmcache 0.5.5 logs one line per lookup prefetch, e.g.
#   Prefetch request completed (L1+L2): 16/17 retained keys (0 L1, 16 L2) in 239.4 ms
_PREFETCH = re.compile(r"Prefetch request completed \(L1\+L2\): \d+/\d+ retained keys "
                       r"\((\d+) L1, (\d+) L2\) in ([0-9.]+) ms")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def lmcache_lookups(log: Path) -> dict | None:
    """Chunks LMCache's lookups found in L1 vs loaded from Valkey (L2) during a
    run, warm-up included, and the median prefetch time. None without a log."""
    if not log.exists():
        return None
    l1 = l2 = 0
    times = []
    for match in _PREFETCH.finditer(_ANSI.sub("", log.read_text(errors="replace"))):
        l1 += int(match.group(1))
        l2 += int(match.group(2))
        times.append(float(match.group(3)))
    return {"lookups": len(times), "l1_chunks": l1, "valkey_chunks": l2,
            "prefetch_ms_p50": statistics.median(times) if times else None}


def fmt(cell: dict | None, kind: str) -> str:
    if cell is None:
        return "n/a"
    if kind == "ms":
        f = lambda v: f"{v * 1000:,.0f}"  # noqa: E731
    elif kind == "pct":
        f = lambda v: f"{v * 100:.0f}%"  # noqa: E731
    else:
        f = lambda v: f"{v:.2f}"  # noqa: E731
    if cell["n"] == 1 or cell["min"] == cell["max"]:
        return f(cell["median"])
    if kind == "pct":
        return f"{f(cell['median'])} ({cell['min'] * 100:.0f}–{f(cell['max'])})"
    return f"{f(cell['median'])} ({f(cell['min'])}–{f(cell['max'])})"


def results_table(summary: dict) -> list[str]:
    lines = [
        "| Configuration | Concurrency | Runs | TTFT p50 ms | TTFT p90 ms | TTFT p99 ms | Requests/s "
        "| Prompt tokens from GPU prefix cache | Prompt tokens from LMCache (L1 or Valkey) | Failed requests |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for config, levels in summary.items():
        for level, cell in levels.items():
            lines.append(
                f"| {config} | {level} | {cell['runs']} | {fmt(cell['ttft_p50'], 'ms')} "
                f"| {fmt(cell['ttft_p90'], 'ms')} | {fmt(cell['ttft_p99'], 'ms')} "
                f"| {fmt(cell['requests_per_s'], 'rate')} | {fmt(cell['local_share'], 'pct')} "
                f"| {fmt(cell['valkey_share'], 'pct')} | {sum(cell['failed'])} |")
    return lines


def valkey_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Configuration | Run | Valkey used_memory GiB | used_memory_peak GiB | maxmemory GiB "
        "| KV keys (db 0) | Index keys (db 1) | Index keys at start (db 1) | OOM rejections "
        "| Lookup chunks from L1 | Lookup chunks from Valkey | Prefetch p50 ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        a = row["after"]
        keys = a.get("keys_per_db") or {}
        at_start = row["index_keys_at_start"]
        lk = row.get("lookups")
        if lk and lk["lookups"]:
            lookup_cells = f"{lk['l1_chunks']:,} | {lk['valkey_chunks']:,} | {lk['prefetch_ms_p50']:.0f}"
        else:
            lookup_cells = "n/a | n/a | n/a"
        lines.append(
            f"| {row['config']} | {row['run']} | {a['used_memory'] / GIB:.1f} | {a['used_memory_peak'] / GIB:.1f} "
            f"| {a.get('maxmemory', 0) / GIB:.0f} | {keys.get('db0', 0)} | {keys.get('db1', 0)} "
            f"| {'n/a' if at_start is None else at_start} | {a.get('oom_errors', 0)} | {lookup_cells} |")
    return lines


def render(run_dir: Path) -> tuple[str, dict]:
    SKIPPED.clear()
    meta_path = run_dir / "metadata.json"
    meta = (read_json(meta_path, "run metadata") or {}) if meta_path.exists() else {}
    line = metadata_line(meta) if meta else "Measured on an unknown host (no metadata.json)."
    summary = collect(run_dir)
    vrows = valkey_runs(run_dir)
    out = [line, "", *results_table(summary), "",
           "Each cell is the median of the runs, with the spread (min–max) in brackets. "
           "Prompt-token shares come from vLLM's prefix_cache_hits (local) and "
           "external_prefix_cache_hits (LMCache: its L1 memory or Valkey) counters, as shares of "
           "prompt_tokens. The Valkey table below splits LMCache's lookups into chunks found in L1 and "
           "chunks loaded from Valkey.",
           ""]
    if vrows:
        out += ["### Valkey after each run", "", line, "", *valkey_table(vrows), "",
                "used_memory after a run is close to that run's peak: nothing is deleted during a run "
                "(noeviction), and database 0 is flushed before the next. used_memory_peak is since "
                "Valkey started, so it covers every run so far.", ""]
        full = [f"{r['config']} run {r['run']}" for r in vrows if r["after"].get("oom_errors")]
        if full:
            out += [f"Warning: Valkey rejected writes (OOM) in {', '.join(full)}. Those runs stored less KV "
                    "than the workload produced; raise VALKEY_MAXMEMORY or shrink the workload.", ""]
    if SKIPPED:
        out += ["Warning: these files were skipped, so the tables above leave them out:", "",
                *[f"- `{item}`" for item in SKIPPED], ""]
    # One trailing newline (print adds it): markdownlint rejects blank runs.
    return "\n".join(out).rstrip("\n"), {"metadata": meta, "results": summary, "valkey": vrows,
                                           "skipped": list(SKIPPED)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--json", type=Path, help="also write the numbers as JSON")
    args = parser.parse_args()
    if not args.run_dir.is_dir():
        sys.exit(f"summarize: {args.run_dir} is not a directory")
    text, data = render(args.run_dir)
    print(text)
    if args.json:
        args.json.write_text(json.dumps(data, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
