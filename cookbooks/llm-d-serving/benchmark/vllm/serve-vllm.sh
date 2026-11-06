#!/bin/bash
# Starts one vLLM replica for the GPU benchmark.
#
# The router flags follow llm-d's precise prefix-cache routing guide
# (guides/precise-prefix-cache-routing/modelserver/gpu/vllm/base/patch-vllm.yaml)
# and match the recipe's CPU stack (../docker-compose.yml):
#   --block-size 64           must equal blockSizeTokens in the router config;
#                             LMCache's 256-token chunks are four blocks
#   --enable-prefix-caching   the replica's own GPU prefix cache (local hits)
#   --enable-scale-out        serves /v1/*/render, which the router's
#                             token-producer calls to tokenize prompts
#   --kv-events-config        publishes KV-cache events over ZMQ; the topic
#                             names this replica by IP:port so the router can
#                             attribute each event to an endpoint
#   --enable-prompt-tokens-details
#                             reports cached prompt tokens in each response
#
# KV_CONNECTOR=lmcache (the default) adds LMCacheMPConnector, with the same
# --kv-transfer-config as the CPU stack: misses in the GPU prefix cache can
# load from the LMCache server, whose store is Valkey. KV_CONNECTOR=none
# leaves it out, for the random-no-lmcache baseline.
set -euo pipefail

: "${MODEL:?MODEL is required}"
: "${POD_IP:?POD_IP is required}"
KV_CONNECTOR="${KV_CONNECTOR:-lmcache}"

KV_EVENTS_CONFIG=$(printf '{"enable_kv_cache_events":true,"publisher":"zmq","endpoint":"tcp://*:5556","replay_endpoint":"tcp://*:5559","topic":"kv@%s:8000@%s"}' "$POD_IP" "$MODEL")
KV_TRANSFER_CONFIG='{"kv_connector":"LMCacheMPConnector","kv_role":"kv_both","kv_connector_extra_config":{"lmcache.mp.host":"tcp://lmcache-server","lmcache.mp.port":5555,"lmcache.mp.mq_timeout":120.0}}'

args=(
  --host 0.0.0.0
  --port 8000
  --dtype "${DTYPE:-auto}"
  --block-size 64
  --enable-prefix-caching
  --enable-scale-out
  --enable-prompt-tokens-details
  --max-model-len "${MAX_MODEL_LEN:-16384}"
  --max-num-batched-tokens "${MAX_NUM_BATCHED_TOKENS:-8192}"
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.90}"
  "--disable-access-log-for-endpoints=/health,/metrics,/v1/models,/v1/completions/render,/v1/chat/completions/render"
  --kv-events-config "$KV_EVENTS_CONFIG"
)

case "$KV_CONNECTOR" in
  lmcache)
    # Fail here, with a clear message, rather than deep inside vLLM's startup.
    python3 -c 'import lmcache.integration.vllm.lmcache_mp_connector' || {
      echo "serve-vllm: lmcache failed to import (see the traceback above); check the image build log" >&2
      exit 1
    }
    echo "serve-vllm: LMCacheMPConnector on, transfer mode ${LMCACHE_MP_TRANSFER_MODE:-auto}" >&2
    args+=(--kv-transfer-config "$KV_TRANSFER_CONFIG")
    ;;
  none)
    echo "serve-vllm: no KV connector (GPU prefix cache only)" >&2
    ;;
  *)
    echo "serve-vllm: KV_CONNECTOR must be lmcache or none, got '$KV_CONNECTOR'" >&2
    exit 1
    ;;
esac

exec vllm serve "$MODEL" "${args[@]}"
