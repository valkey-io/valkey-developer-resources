#!/usr/bin/env python3
"""Render the router and load-generator configs for one benchmark run.

Fills the ${NAME} placeholders in epp/*.yaml and loadgen/shared-prefix.yaml
from environment variables and writes the results under rendered/. A missing
variable is an error, so a typo can't silently produce a broken config.

Standard library only.
"""

import os
import sys
from pathlib import Path
from string import Template

BENCH_DIR = Path(__file__).resolve().parent.parent
STRATEGIES = ("random", "approximate", "precise-memory", "precise-valkey")


def render(src: Path, dst: Path, values: dict[str, str]) -> None:
    try:
        text = Template(src.read_text()).substitute(values)
    except KeyError as exc:
        sys.exit(f"render: {src.relative_to(BENCH_DIR)} needs ${{{exc.args[0]}}}, which is not set")
    except ValueError as exc:
        sys.exit(f"render: bad placeholder in {src.relative_to(BENCH_DIR)}: {exc}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text)


def stages_yaml(warmup_requests: int, stage_requests: int, levels: list[int]) -> str:
    # Stage 0 warms the caches and is left out of the summary.
    lines = [f"    - {{num_requests: {warmup_requests}, concurrency_level: {levels[0]}}}"]
    lines += [f"    - {{num_requests: {stage_requests}, concurrency_level: {c}}}" for c in levels]
    return "\n".join(lines)


def main() -> None:
    env = dict(os.environ)
    levels = [int(x) for x in env.get("CONCURRENCY_LEVELS", "").split()]
    if not levels or any(c <= 0 for c in levels):
        sys.exit("render: CONCURRENCY_LEVELS must be a space-separated list of positive integers")
    env["STAGES"] = stages_yaml(int(env["WARMUP_REQUESTS"]), int(env["STAGE_REQUESTS"]), levels)

    out = BENCH_DIR / "rendered"
    render(BENCH_DIR / "epp" / "endpoints.yaml", out / "epp" / "endpoints.yaml", env)
    for strategy in STRATEGIES:
        render(BENCH_DIR / "epp" / f"{strategy}.yaml", out / "epp" / f"{strategy}.yaml", env)
        render(
            BENCH_DIR / "loadgen" / "shared-prefix.yaml",
            out / "loadgen" / f"{strategy}.yaml",
            {**env, "STRATEGY": strategy},
        )
    print(f"render: wrote configs to {out.relative_to(BENCH_DIR)}/")


if __name__ == "__main__":
    main()
