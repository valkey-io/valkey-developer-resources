#!/usr/bin/env python3
"""Render the router and load-generator configs for one benchmark run.

  render.py epp
      Fill epp/*.yaml (MODEL, PEAK_PREFILL_THROUGHPUT) into rendered/epp/.
  render.py loadgen --config NAME --run N
      Write one inference-perf config per stage (warmup, c<level> for each
      level in CONCURRENCY_LEVELS) into rendered/loadgen/, with each stage's
      output going to /results/$RUN_ID/NAME/run-N/<stage>/.

Values come from environment variables. A missing variable is an error, so
a typo can't silently produce a broken config.

Standard library only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from string import Template

from benchctl import CONFIGS

BENCH_DIR = Path(__file__).resolve().parent.parent
RENDERED = BENCH_DIR / "rendered"


def render(src: Path, dst: Path, values: dict[str, str]) -> None:
    try:
        text = Template(src.read_text()).substitute(values)
    except KeyError as exc:
        sys.exit(f"render: {src.relative_to(BENCH_DIR)} needs ${{{exc.args[0]}}}, which is not set")
    except ValueError as exc:
        sys.exit(f"render: bad placeholder in {src.relative_to(BENCH_DIR)}: {exc}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text)


def concurrency_levels(env: dict[str, str]) -> list[int]:
    try:
        levels = [int(x) for x in env.get("CONCURRENCY_LEVELS", "").split()]
    except ValueError:
        levels = []
    if not levels or any(c <= 0 for c in levels):
        sys.exit("render: CONCURRENCY_LEVELS must be a space-separated list of positive integers")
    return levels


def stages(env: dict[str, str]) -> list[tuple[str, int, int]]:
    """(stage name, requests, concurrency). The warm-up runs at the first
    concurrency level and is left out of the summary."""
    levels = concurrency_levels(env)
    out = [("warmup", int(env["WARMUP_REQUESTS"]), levels[0])]
    out += [(f"c{c}", int(env["STAGE_REQUESTS"]), c) for c in levels]
    return out


def render_epp(env: dict[str, str], out: Path = RENDERED) -> None:
    render(BENCH_DIR / "epp" / "endpoints.yaml", out / "epp" / "endpoints.yaml", env)
    for epp in sorted({c["epp"] for c in CONFIGS.values()}):
        render(BENCH_DIR / "epp" / f"{epp}.yaml", out / "epp" / f"{epp}.yaml", env)


def render_loadgen(env: dict[str, str], config: str, run: int, out: Path = RENDERED) -> list[str]:
    if config not in CONFIGS:
        sys.exit(f"render: unknown configuration {config}")
    names = []
    for name, requests, concurrency in stages(env):
        values = {
            **env,
            "NUM_REQUESTS": str(requests),
            "CONCURRENCY": str(concurrency),
            "OUTPUT_DIR": f"/results/{env['RUN_ID']}/{config}/run-{run}/{name}",
        }
        render(BENCH_DIR / "loadgen" / "shared-prefix.yaml", out / "loadgen" / f"{name}.yaml", values)
        names.append(name)
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("epp")
    p = sub.add_parser("loadgen")
    p.add_argument("--config", required=True)
    p.add_argument("--run", type=int, required=True)
    args = parser.parse_args()

    env = dict(os.environ)
    try:
        if args.command == "epp":
            render_epp(env)
            print(f"render: wrote router configs to {(RENDERED / 'epp').relative_to(BENCH_DIR)}/", file=sys.stderr)
        else:
            # Stage names on stdout, one per line, for run-benchmark.sh.
            print("\n".join(render_loadgen(env, args.config, args.run)))
    except KeyError as exc:
        sys.exit(f"render: {exc.args[0]} is not set")


if __name__ == "__main__":
    main()
