#!/bin/bash
# Starts one vLLM replica for the prompt-routing benchmark.
#
# The flags follow llm-d's precise prefix-cache routing guide
# (guides/precise-prefix-cache-routing/modelserver/gpu/vllm/base/patch-vllm.yaml):
#   --block-size 64           must match blockSizeTokens in the router config
#   --enable-scale-out        serves /v1/*/render, which the router's
#                             token-producer calls to tokenize prompts
#   --kv-events-config        publishes KV-cache events over ZMQ; the topic
#                             names this replica by IP:port so the router can
#                             attribute each event to an endpoint
#   --enable-prompt-tokens-details
#                             reports cached prompt tokens in each response,
#                             which the load generator records as cache hits
set -euo pipefail

: "${MODEL:?MODEL is required}"
: "${POD_IP:?POD_IP is required}"

KV_EVENTS_CONFIG=$(printf '{"enable_kv_cache_events":true,"publisher":"zmq","endpoint":"tcp://*:5556","replay_endpoint":"tcp://*:5559","topic":"kv@%s:8000@%s"}' "$POD_IP" "$MODEL")

exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype "${DTYPE:-auto}" \
  --block-size 64 \
  --enable-prefix-caching \
  --enable-scale-out \
  --enable-prompt-tokens-details \
  --max-model-len "${MAX_MODEL_LEN:-16384}" \
  --max-num-batched-tokens "${MAX_NUM_BATCHED_TOKENS:-8192}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.90}" \
  --disable-access-log-for-endpoints=/health,/metrics,/v1/models,/v1/completions/render,/v1/chat/completions/render \
  --kv-events-config "$KV_EVENTS_CONFIG"
