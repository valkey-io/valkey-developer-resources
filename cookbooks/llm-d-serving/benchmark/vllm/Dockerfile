# vLLM GPU image with a pinned lmcache and the Valkey GLIDE client, for the
# replicas, the LMCache server and the no-LMCache baseline in compose.yaml.
#
# The base is the multi-arch index digest of vllm/vllm-openai:v0.30.0 (CUDA
# 13.0.2, Python 3.12, torch 2.13.0). It is built with INSTALL_KV_CONNECTORS,
# which installs an unpinned lmcache; install-lmcache.sh replaces it with
# LMCACHE_VERSION if it differs, without changing torch, vLLM or the CUDA
# libraries, and fails the build if the result is not LMCACHE_VERSION.
# lmcache 0.5.5 wheels are built against torch 2.13.0 and CUDA 13.
#
# valkey-glide-sync is what LMCache's Valkey L2 adapter connects with. Only the
# LMCache server uses it; it is installed here so one image serves all.
ARG VLLM_BASE_IMAGE=docker.io/vllm/vllm-openai:v0.30.0@sha256:8a69ffad015f138d7170c4ddc429e230a3bc1c1719f67e14324749df200a4b90
FROM ${VLLM_BASE_IMAGE}

ARG LMCACHE_VERSION=0.5.5
ARG VALKEY_GLIDE_SYNC_VERSION=2.5.2

COPY vllm/install-lmcache.sh /tmp/install-lmcache.sh
RUN LMCACHE_VERSION="${LMCACHE_VERSION}" \
    VALKEY_GLIDE_SYNC_VERSION="${VALKEY_GLIDE_SYNC_VERSION}" \
    bash /tmp/install-lmcache.sh \
 && rm /tmp/install-lmcache.sh

LABEL org.opencontainers.image.description="vLLM 0.30.0 with lmcache ${LMCACHE_VERSION} and valkey-glide-sync ${VALKEY_GLIDE_SYNC_VERSION} for the llm-d serving GPU benchmark"
