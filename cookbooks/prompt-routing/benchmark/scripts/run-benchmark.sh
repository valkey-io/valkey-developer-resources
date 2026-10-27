#!/usr/bin/env bash
# Run the prompt-routing latency benchmark end to end.
#
#   1. Start Valkey, Envoy, and four vLLM replicas (first start downloads the
#      model and takes a while).
#   2. Measure peak prefill throughput, unless PEAK_PREFILL_THROUGHPUT is set.
#   3. Render the router and load-generator configs.
#   4. For each strategy: stop the router, clear every prefix cache and the
#      Valkey index, start the router with that strategy, run the workload.
#   5. Write results/<run>/summary.md.
#
# Settings come from the environment or from a .env file next to compose.yaml
# (see .env.example). Stop everything afterwards with: docker compose down
set -euo pipefail

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BENCH_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export MODEL="${MODEL:-Qwen/Qwen3-8B}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-8192}"
export STRATEGIES="${STRATEGIES:-random approximate precise-memory precise-valkey}"
export CONCURRENCY_LEVELS="${CONCURRENCY_LEVELS:-8 16 32}"
export WARMUP_REQUESTS="${WARMUP_REQUESTS:-128}"
export STAGE_REQUESTS="${STAGE_REQUESTS:-512}"
export NUM_PREFIXES="${NUM_PREFIXES:-16}"
export PROMPTS_PER_PREFIX="${PROMPTS_PER_PREFIX:-64}"
export SYSTEM_PROMPT_LEN="${SYSTEM_PROMPT_LEN:-4096}"
export QUESTION_LEN="${QUESTION_LEN:-256}"
export OUTPUT_LEN="${OUTPUT_LEN:-64}"
export SEED="${SEED:-42}"
export RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"

REPLICAS=(vllm-0 vllm-1 vllm-2 vllm-3)
REPLICA_URLS=(http://172.30.0.11:8000 http://172.30.0.12:8000 http://172.30.0.13:8000 http://172.30.0.14:8000)
ROUTER_URL=http://172.30.0.10:8081
RESULTS="results/$RUN_ID"

log() { printf '\n==> %s\n' "$*"; }

# Runs a helper inside the bench network, so it reaches the fixed container
# IPs on any Docker host.
benchctl() {
  docker compose run --rm --no-deps -T --entrypoint python3 loadgen /bench/scripts/benchctl.py "$@"
}

for strategy in $STRATEGIES; do
  [[ -f "epp/$strategy.yaml" ]] || { echo "unknown strategy: $strategy" >&2; exit 1; }
done

mkdir -p "$RESULTS"

log "Downloading $MODEL into the shared cache (skipped if already there)"
docker compose run --rm -T model-download

log "Starting Valkey, Envoy and ${#REPLICAS[@]} vLLM replicas"
docker compose up -d --no-deps --wait --wait-timeout 2400 valkey envoy "${REPLICAS[@]}"

if [[ -z "${PEAK_PREFILL_THROUGHPUT:-}" ]]; then
  log "Calibrating peak prefill throughput on vllm-0"
  PEAK_PREFILL_THROUGHPUT="$(benchctl calibrate --endpoint "${REPLICA_URLS[0]}" \
    --model "$MODEL" --chunk "$MAX_NUM_BATCHED_TOKENS")"
fi
export PEAK_PREFILL_THROUGHPUT
echo "peakPrefillThroughput = $PEAK_PREFILL_THROUGHPUT tokens/s"

log "Rendering configs"
python3 scripts/render.py

# Record what produced these numbers.
{
  echo "run_id: $RUN_ID"
  echo "model: $MODEL"
  echo "peak_prefill_throughput: $PEAK_PREFILL_THROUGHPUT"
  echo "strategies: $STRATEGIES"
  echo "concurrency_levels: $CONCURRENCY_LEVELS"
  echo "warmup_requests: $WARMUP_REQUESTS"
  echo "stage_requests: $STAGE_REQUESTS"
  echo "workload: $NUM_PREFIXES prefixes x $SYSTEM_PROMPT_LEN tokens, $PROMPTS_PER_PREFIX prompts each, question $QUESTION_LEN, output $OUTPUT_LEN, seed $SEED"
  echo "images:"
  docker compose config --images | sort -u | sed 's/^/  - /'
  echo "gpus:"
  if command -v nvidia-smi >/dev/null; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | sed 's/^/  - /'
  fi
} > "$RESULTS/run.yaml"
docker compose logs --no-color vllm-0 > "$RESULTS/vllm-0.log" 2>&1 || true

for strategy in $STRATEGIES; do
  log "Strategy: $strategy"
  docker compose rm -sf epp >/dev/null
  benchctl reset-prefix-cache "${REPLICA_URLS[@]}"
  docker compose exec -T valkey valkey-cli FLUSHALL >/dev/null

  EPP_STRATEGY="$strategy" docker compose up -d --no-deps epp
  benchctl wait-router --url "$ROUTER_URL" --model "$MODEL"

  mkdir -p "$RESULTS/$strategy"
  docker compose run --rm --no-deps -T loadgen --config_file "/etc/loadgen/$strategy.yaml"

  # Evidence for the Valkey path: how many index keys the router wrote.
  echo "valkey_dbsize_after_run: $(docker compose exec -T valkey valkey-cli DBSIZE)" \
    > "$RESULTS/$strategy/index.txt"
  docker compose logs --no-color epp > "$RESULTS/$strategy/epp.log" 2>&1 || true
done

docker compose rm -sf epp >/dev/null

log "Summary"
python3 scripts/summarize.py "$RESULTS" | tee "$RESULTS/summary.md"
echo
echo "Results: $BENCH_DIR/$RESULTS"
