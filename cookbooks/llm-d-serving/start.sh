#!/bin/sh
# Start the llm-d serving stack: check that the container runtime has enough
# memory, then run `compose up -d --wait` and show the services' status.
#
# Usage: ./start.sh   (from any directory; it switches to the recipe folder)
#
# It uses docker if `docker info` answers, otherwise podman. Set
# CONTAINER_ENGINE=podman (or docker) to choose; the notebook reads it too.
set -eu

cd "$(dirname "$0")"

# A runtime reports a little less memory than its setting (the VM keeps some):
# the measured minimum of 8.5 GiB reports about 8.2 GiB, and the recommended
# 10 GiB about 9.7 GiB. The notebook's setup cell uses the same thresholds;
# test_llm_d_serving.py checks that the two agree.
MIN_RUNTIME_MEMORY=8589934592            # 8.0 GiB reported
RECOMMENDED_RUNTIME_MEMORY=10200547328   # 9.5 GiB reported

gib() {
  tenths=$(( $1 * 10 / 1073741824 ))
  echo "$(( tenths / 10 )).$(( tenths % 10 ))"
}

rt=""
mem_bytes=""
candidates="${CONTAINER_ENGINE:-docker podman}"
for candidate in $candidates; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  mem_bytes="$("$candidate" info --format '{{.MemTotal}}' 2>/dev/null)" ||
    mem_bytes="$("$candidate" info --format '{{.Host.MemTotal}}' 2>/dev/null)" ||
    mem_bytes=""
  if [ -n "$mem_bytes" ] && [ "$mem_bytes" -ge 0 ] 2>/dev/null; then
    rt="$candidate"
    break
  fi
  mem_bytes=""
done

if [ -z "$rt" ]; then
  tried=""
  for candidate in $candidates; do tried="${tried:+$tried or }'$candidate info'"; done
  echo "Could not read the container runtime's memory from $tried. Is the runtime running?" >&2
  exit 1
fi

if [ "$mem_bytes" -lt "$MIN_RUNTIME_MEMORY" ]; then
  {
    echo "Not enough memory: $rt reports $(gib "$mem_bytes") GiB; this recipe needs at least 8.5 GiB (10 GiB recommended), which this check sees as at least 8.0 GiB. Raise the limit and retry:"
    echo "  Colima: colima stop, then colima start --memory 10"
    echo "  Docker Desktop: Settings > Resources"
    echo "  Podman on macOS or Linux: podman machine stop, then podman machine set --memory 10240, then podman machine start"
    echo "  WSL2 on Windows (Docker Engine or Podman): memory=10GB under [wsl2] in %UserProfile%\\.wslconfig, then wsl --shutdown"
  } >&2
  exit 1
fi

if [ "$mem_bytes" -lt "$RECOMMENDED_RUNTIME_MEMORY" ]; then
  echo "Note: $rt reports $(gib "$mem_bytes") GiB, below the recommended 10 GiB. See 'Running on a smaller machine' in the README."
fi

status=0
"$rt" compose up -d --wait || status=$?
"$rt" compose ps -a
exit "$status"
