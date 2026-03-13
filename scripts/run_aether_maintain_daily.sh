#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   AETHER_EMAIL=... AETHER_PASSWORD=... CPA_MGMT_KEY=... \
#   scripts/run_aether_maintain_daily.sh [--dry-run]

DRY=""
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY="--dry-run"
fi

python3 /home/chenyechao/.openclaw/workspace/scripts/aether_gpt_pool_maintain.py \
  --cpa-base http://127.0.0.1:8080 \
  --cpa-mgmt-key "${CPA_MGMT_KEY}" \
  --aether-base http://127.0.0.1:8084 \
  --aether-email "${AETHER_EMAIL}" \
  --aether-password "${AETHER_PASSWORD}" \
  --provider-id e4efb41c-1956-44e1-9c00-986e5cae12f6 \
  --proxy-node-id d91042e8-bb66-4e0f-9eef-53ac2ba2c137 \
  --target-keys 20 \
  --cleanup-limit 20 \
  --import-limit 20 \
  --safe \
  ${DRY} \
  --log-file /home/chenyechao/.openclaw/workspace/memory/aether-maintain-last.json
