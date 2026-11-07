#!/usr/bin/env bash
# Run the llm-d serving GPU benchmark end to end.
#
#   1. Check that the host has enough RAM for Valkey's maxmemory, the
#      replicas and the LMCache server.
#   2. Build the vLLM + lmcache image, download the model, start Valkey,
#      Envoy, the LMCache server and four vLLM replicas.
#   3. Measure peak prefill throughput, unless PEAK_PREFILL_THROUGHPUT is set,
#      render the router configs, and write results/<run>/metadata.json.
#   4. For each configuration in STRATEGIES, RUNS times: stop the router and
#      the replicas, restart the LMCache server, flush Valkey database 0 (the
#      KV store), recreate the replicas with or without LMCache, start the
#      router, then run the warm-up and one stage per concurrency level,
#      reading vLLM's cache-hit counters before and after each stage.
#      Record Valkey's memory and key counts after each run.
#   5. Write results/<run>/summary.md and summary.json.
#
# Settings come from the environment or from a .env file next to compose.yaml
# (see .env.example). A host provisioning step can also write BENCH_CLOUD,
# BENCH_INSTANCE_TYPE and BENCH_REGION to /etc/llm-d-gpu-bench/host.env
# (BENCH_HOST_ENV_FILE), which is read first. Stop everything afterwards with
# docker compose down.
set -euo pipefail

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BENCH_DIR"

load_env_file() {
  if [[ -f "$1" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$1"
    set +a
  fi
}
load_env_file "${BENCH_HOST_ENV_FILE:-/etc/llm-d-gpu-bench/host.env}"
load_env_file .env

# Model and vLLM sizing.
export MODEL="${MODEL:-Qwen/Qwen3-8B}"
export DTYPE="${DTYPE:-auto}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-8192}"
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"

# Configurations (scripts/benchctl.py CONFIGS), runs and workload. The
# workload is #107's "many prefixes competing for cache" case.
export STRATEGIES="${STRATEGIES:-random-no-lmcache random approximate precise-memory precise-valkey}"
export RUNS="${RUNS:-3}"
export CONCURRENCY_LEVELS="${CONCURRENCY_LEVELS:-8 16 32}"
export WARMUP_REQUESTS="${WARMUP_REQUESTS:-384}"
export STAGE_REQUESTS="${STAGE_REQUESTS:-768}"
export NUM_PREFIXES="${NUM_PREFIXES:-192}"
export PROMPTS_PER_PREFIX="${PROMPTS_PER_PREFIX:-4}"
export SYSTEM_PROMPT_LEN="${SYSTEM_PROMPT_LEN:-4096}"
export QUESTION_LEN="${QUESTION_LEN:-256}"
export OUTPUT_LEN="${OUTPUT_LEN:-64}"
export SEED="${SEED:-42}"

# Valkey and LMCache (see compose.yaml).
export VALKEY_MAXMEMORY="${VALKEY_MAXMEMORY:-192gb}"
export VALKEY_IO_THREADS="${VALKEY_IO_THREADS:-8}"
export LMCACHE_L1_SIZE_GB="${LMCACHE_L1_SIZE_GB:-64}"
export LMCACHE_MAX_GPU_WORKERS="${LMCACHE_MAX_GPU_WORKERS:-4}"
export LMCACHE_EVICTION_POLICY="${LMCACHE_EVICTION_POLICY:-LRU}"
export LMCACHE_L2_STORE_POLICY="${LMCACHE_L2_STORE_POLICY:-default}"
export LMCACHE_SERVER_TRANSFER_MODE="${LMCACHE_SERVER_TRANSFER_MODE:-auto}"
export LMCACHE_MP_TRANSFER_MODE="${LMCACHE_MP_TRANSFER_MODE:-auto}"
# 1 (the default) also flushes the router's index (database 1) before each
# run, while the router is stopped, so precise-valkey starts as empty as
# precise-memory. The index's key count at the start of each run is recorded
# either way.
export FLUSH_ROUTER_INDEX="${FLUSH_ROUTER_INDEX:-1}"

# Host memory the preflight reserves besides Valkey and LMCache's L1, in GiB.
REPLICA_HOST_RAM_GIB="${REPLICA_HOST_RAM_GIB:-16}"
LMCACHE_SERVER_HOST_RAM_GIB="${LMCACHE_SERVER_HOST_RAM_GIB:-8}"
SYSTEM_HOST_RAM_GIB="${SYSTEM_HOST_RAM_GIB:-16}"

export RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"

REPLICAS=(vllm-0 vllm-1 vllm-2 vllm-3)
RESULTS="results/$RUN_ID"

log() { printf '\n==> %s\n' "$*"; }

# Runs a helper inside the bench network, so it reaches the fixed container
# IPs on any Docker host.
benchctl() {
  docker compose run --rm --no-deps -T --entrypoint python3 loadgen /bench/scripts/benchctl.py "$@"
}

valkey_cli() {
  docker compose exec -T valkey valkey-cli "$@"
}

valkey_stats() {
  valkey_cli INFO memory keyspace errorstats > "$1.txt"
  python3 scripts/benchctl.py valkey-stats < "$1.txt" > "$1.json"
}

# --- Checks --------------------------------------------------------------

# Calibration sends MAX_NUM_BATCHED_TOKENS prompt tokens plus one output
# token, so the context window has to be larger.
if (( MAX_MODEL_LEN <= MAX_NUM_BATCHED_TOKENS )); then
  echo "MAX_MODEL_LEN ($MAX_MODEL_LEN) must be larger than MAX_NUM_BATCHED_TOKENS ($MAX_NUM_BATCHED_TOKENS)" >&2
  exit 1
fi
if ! [[ "$RUNS" =~ ^[1-9][0-9]*$ ]]; then
  echo "RUNS must be a positive whole number, got '$RUNS'" >&2
  exit 1
fi
for config in $STRATEGIES; do
  python3 scripts/benchctl.py describe "$config" >/dev/null
done

python3 scripts/benchctl.py host-ram-check \
  --valkey-maxmemory "$VALKEY_MAXMEMORY" \
  --l1-size-gb "$LMCACHE_L1_SIZE_GB" \
  --replicas "${#REPLICAS[@]}" \
  --replica-gib "$REPLICA_HOST_RAM_GIB" \
  --lmcache-server-gib "$LMCACHE_SERVER_HOST_RAM_GIB" \
  --system-gib "$SYSTEM_HOST_RAM_GIB"

mkdir -p "$RESULTS"

# --- Stack ---------------------------------------------------------------

log "Building the vLLM + lmcache image (cached after the first build)"
docker compose build lmcache-server

log "Downloading $MODEL into the shared cache (skipped if already there)"
docker compose run --rm -T model-download

log "Starting Valkey, Envoy, the LMCache server and ${#REPLICAS[@]} vLLM replicas"
docker compose up -d --no-deps --wait --wait-timeout 900 valkey envoy lmcache-server
KV_CONNECTOR=lmcache docker compose up -d --no-deps --wait --wait-timeout 2400 "${REPLICAS[@]}"

# Calibrated with LMCache on, as in the configurations whose router uses it
# (precise-*). The random calibration prompts land in Valkey; database 0 is
# flushed before the first run.
if [[ -z "${PEAK_PREFILL_THROUGHPUT:-}" ]]; then
  log "Calibrating peak prefill throughput on vllm-0"
  PEAK_PREFILL_THROUGHPUT="$(benchctl calibrate --model "$MODEL" --chunk "$MAX_NUM_BATCHED_TOKENS")"
fi
export PEAK_PREFILL_THROUGHPUT
echo "peakPrefillThroughput = $PEAK_PREFILL_THROUGHPUT tokens/s"

log "Rendering router configs"
python3 scripts/render.py epp

log "Recording run metadata"
# The router only starts per configuration; pull it now so its digest is known.
docker compose pull --quiet epp
python3 scripts/metadata.py collect --out "$RESULTS/metadata.json"
docker compose logs --no-color vllm-0 > "$RESULTS/vllm-0.log" 2>&1 || true
docker compose logs --no-color lmcache-server > "$RESULTS/lmcache-server.log" 2>&1 || true

# --- Runs ----------------------------------------------------------------

run_once() {
  local config="$1" run="$2" epp="$3" connector="$4"
  local dir="$RESULTS/$config/run-$run"
  local started
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  mkdir -p "$dir"

  docker compose rm -sf epp >/dev/null
  docker compose stop "${REPLICAS[@]}" >/dev/null
  # A fresh LMCache server has an empty L1, and nothing is still being
  # written to Valkey when database 0 is flushed.
  docker compose restart lmcache-server >/dev/null
  docker compose up -d --no-deps --wait --wait-timeout 600 lmcache-server
  valkey_cli -n 0 FLUSHDB >/dev/null
  if [[ "$FLUSH_ROUTER_INDEX" == "1" ]]; then
    valkey_cli -n 1 FLUSHDB >/dev/null
  fi
  # Per-run error counts (OOM rejections) in valkey.json.
  valkey_cli CONFIG RESETSTAT >/dev/null

  # Recreated, not restarted: KV_CONNECTOR may change between
  # configurations, and a fresh replica has an empty GPU prefix cache and a
  # fresh KV-event stream for the new router.
  KV_CONNECTOR="$connector" docker compose up -d --no-deps --force-recreate --wait --wait-timeout 2400 "${REPLICAS[@]}"

  EPP_STRATEGY="$epp" docker compose up -d --no-deps epp
  benchctl wait-router --model "$MODEL"
  valkey_stats "$dir/valkey-before"

  local stage
  for stage in $(python3 scripts/render.py loadgen --config "$config" --run "$run"); do
    mkdir -p "$dir/$stage"
    if [[ "$stage" != warmup ]]; then
      benchctl snapshot --out "/results/$RUN_ID/$config/run-$run/$stage/counters-before.json"
    fi
    docker compose run --rm --no-deps -T loadgen --config_file "/etc/loadgen/$stage.yaml"
    if [[ "$stage" != warmup ]]; then
      sleep 2
      benchctl snapshot --out "/results/$RUN_ID/$config/run-$run/$stage/counters-after.json"
    fi
  done

  valkey_stats "$dir/valkey"
  docker compose logs --no-color epp > "$dir/epp.log" 2>&1 || true
  docker compose logs --no-color --since "$started" lmcache-server > "$dir/lmcache-server.log" 2>&1 || true
  local replica
  for replica in "${REPLICAS[@]}"; do
    docker compose logs --no-color "$replica" > "$dir/$replica.log" 2>&1 || true
  done
}

for config in $STRATEGIES; do
  read -r epp connector < <(python3 scripts/benchctl.py describe "$config")
  for (( run = 1; run <= RUNS; run++ )); do
    log "Configuration $config ($epp router, KV connector $connector), run $run of $RUNS"
    run_once "$config" "$run" "$epp" "$connector"
  done
done

docker compose rm -sf epp >/dev/null

log "Summary"
python3 scripts/summarize.py "$RESULTS" --json "$RESULTS/summary.json" | tee "$RESULTS/summary.md"
echo
echo "Results: $BENCH_DIR/$RESULTS"
