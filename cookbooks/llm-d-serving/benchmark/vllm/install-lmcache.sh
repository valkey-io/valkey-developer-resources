#!/bin/bash
# Build step for vllm/Dockerfile: make sure the image has exactly
# LMCACHE_VERSION of lmcache, plus VALKEY_GLIDE_SYNC_VERSION of
# valkey-glide-sync, without changing anything vLLM depends on.
#
#   - If the base image already has LMCACHE_VERSION, lmcache is left alone.
#   - Otherwise lmcache is installed with torch, vLLM, triton, flashinfer and
#     the nvidia-* CUDA wheels constrained to the versions already in the
#     image. If lmcache needs a different version of any of them, pip fails
#     and so does the build.
#   - The package changes are written to /opt/bench/pip-changes.txt, and
#     run-benchmark.sh copies them into each result's metadata.json.
#
# Only package metadata is checked here: importing lmcache's CUDA extensions
# needs the NVIDIA driver, which a build doesn't have. serve-vllm.sh and the
# LMCache server's command import the modules they use at startup instead.
set -euo pipefail

: "${LMCACHE_VERSION:?LMCACHE_VERSION is required}"
: "${VALKEY_GLIDE_SYNC_VERSION:?VALKEY_GLIDE_SYNC_VERSION is required}"

version_of() {
  python3 -c 'import importlib.metadata as m, sys
try:
    print(m.version(sys.argv[1]))
except m.PackageNotFoundError:
    print("none")' "$1"
}

# vLLM images install packages with uv into the system Python; fall back to
# pip if uv is missing.
pip_install() {
  if command -v uv >/dev/null 2>&1; then
    uv pip install --system --python "$(command -v python3)" "$@"
  else
    python3 -m pip install --no-cache-dir "$@"
  fi
}

freeze() {
  if command -v uv >/dev/null 2>&1; then
    uv pip freeze --system --python "$(command -v python3)"
  else
    python3 -m pip freeze
  fi
}

mkdir -p /opt/bench
freeze | sort > /tmp/freeze-before.txt

# Everything vLLM's GPU path is built against stays at the image's version.
grep -iE '^(torch|torchvision|torchaudio|triton|vllm|xformers|flashinfer[a-z0-9_-]*|nvidia-[a-z0-9_-]+)==' \
  /tmp/freeze-before.txt > /tmp/keep.txt || true
echo "install-lmcache: holding $(wc -l < /tmp/keep.txt) packages at the image's versions"

found="$(version_of lmcache)"
echo "install-lmcache: base image has lmcache $found, want $LMCACHE_VERSION"
packages=("valkey-glide-sync==$VALKEY_GLIDE_SYNC_VERSION")
if [ "$found" != "$LMCACHE_VERSION" ]; then
  packages+=("lmcache==$LMCACHE_VERSION")
fi
pip_install -c /tmp/keep.txt "${packages[@]}"

freeze | sort > /tmp/freeze-after.txt
{
  echo "base image lmcache: $found"
  diff /tmp/freeze-before.txt /tmp/freeze-after.txt | grep -E '^[<>]' || true
} > /opt/bench/pip-changes.txt
cat /opt/bench/pip-changes.txt

for pkg in lmcache:"$LMCACHE_VERSION" valkey-glide-sync:"$VALKEY_GLIDE_SYNC_VERSION"; do
  name="${pkg%%:*}" want="${pkg#*:}"
  have="$(version_of "$name")"
  if [ "$have" != "$want" ]; then
    echo "install-lmcache: expected $name $want, found $have" >&2
    exit 1
  fi
done
echo "install-lmcache: lmcache $LMCACHE_VERSION and valkey-glide-sync $VALKEY_GLIDE_SYNC_VERSION installed"
