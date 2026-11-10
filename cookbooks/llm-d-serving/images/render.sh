#!/bin/sh
# Regenerate the recipe's diagrams: renders every src/*.mmd to ../<name>.svg
# with a pinned mermaid-cli image. Run from anywhere: ./images/render.sh
#
# Only 01-without-coordination and 04-busy-server come from Mermaid. The
# other five (02-architecture, 03-request-path, 05-router-restart,
# 06-batch-path, 07-gpu-benchmark) are hand-written SVG, because Mermaid's automatic layout
# crossed their edges or shrank their text below readable size at the
# ~800 px GitHub shows. Each of those .svg files is its own source: edit it
# directly, and this script leaves it alone.
#
# Labels are rendered as SVG <text> (htmlLabels: false in
# src/mermaid-config.json), because GitHub's image view does not render
# <foreignObject>. Needs Docker or Podman (set CONTAINER_RUNTIME=podman).
set -eu

cd "$(dirname "$0")"

IMAGE="docker.io/minlag/mermaid-cli:12.0.1"
RUNTIME="${CONTAINER_RUNTIME:-docker}"

for src in src/*.mmd; do
  name=$(basename "$src" .mmd)
  echo "rendering $name.svg"
  # HOME=/tmp: Chromium in the image needs a writable home when run as a
  # non-root user.
  "$RUNTIME" run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$PWD:/data" "$IMAGE" \
    -i "/data/$src" -o "/data/$name.svg" \
    -c /data/src/mermaid-config.json -b white
done

if grep -l foreignObject ./*.svg; then
  echo "error: the SVGs above contain <foreignObject>" >&2
  exit 1
fi
