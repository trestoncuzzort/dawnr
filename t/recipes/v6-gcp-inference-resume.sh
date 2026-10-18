#!/usr/bin/env bash
# Restart only the already-provisioned evaluation worker, preserving its packages.
set -euo pipefail
if [[ ! -x /opt/dawnr-run/inference/llama.cpp/build/bin/llama-server ||
      ! -f /opt/dawnr-run/evaluation/t/out/v6-20261018/export-final/export.json ]]; then
  echo 'Preserved inference installation is incomplete; inspect before provisioning.' >&2
  exit 1
fi
date -u > /opt/dawnr-run/BOOTED
