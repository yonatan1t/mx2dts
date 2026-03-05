#!/usr/bin/env bash
# Convert each IOC to overlay and run west build (hello_world) to verify DTS compiles.
set -e

MX2DTS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${GITHUB_WORKSPACE:-/workdir}"

# IOC path (relative to mx2dts repo) -> Zephyr board for west build -b
# Format: "ioc_path:board"
IOCS=(
  "tests/test.ioc:nucleo_wb55rg"
)

export CUBEMX_DB="${CUBEMX_DB:-$WORKSPACE/cubemx-db/db}"
export ZEPHYR_BASE="${ZEPHYR_BASE:-$WORKSPACE/zephyrproject/zephyr}"
cd "$WORKSPACE/zephyrproject"

for entry in "${IOCS[@]}"; do
  ioc_rel="${entry%%:*}"
  board="${entry##*:}"
  ioc_path="$MX2DTS_ROOT/$ioc_rel"
  stem="$(basename "$ioc_rel" .ioc)"
  overlay_path="$MX2DTS_ROOT/ci/build/$stem.overlay"

  if [[ ! -f "$ioc_path" ]]; then
    echo "Skipping (not found): $ioc_path"
    continue
  fi

  echo "=== $ioc_rel -> $board ==="
  mkdir -p "$(dirname "$overlay_path")"
  mx2dts "$ioc_path" --mode overlay -o "$overlay_path" --warn-only

  echo "Building hello_world with overlay..."
  west build -b "$board" zephyr/samples/hello_world -- -DOVERLAY_FILE="$overlay_path"
  rm -rf build
done

echo "All DTS builds passed."
