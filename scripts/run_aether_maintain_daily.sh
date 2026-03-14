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
  --aether-token "${AETHER_TOKEN}" \
  --provider-id 81e53f4e-b0fb-48d1-9466-ea54013fec1e \
  --proxy-node-id d91042e8-bb66-4e0f-9eef-53ac2ba2c137 \
  --target-keys 200 \
  --cleanup-limit 20 \
  --import-limit 20 \
  --oauth-callback-url "${AETHER_OAUTH_CALLBACK_URL:-}" \
  --oauth-email-domain "${AETHER_OAUTH_EMAIL_DOMAIN:-cyc3253.org}" \
  --oauth-timeout-sec "${AETHER_OAUTH_TIMEOUT_SEC:-300}" \
  --safe \
  ${AETHER_FALLBACK_TO_EXISTING_CPA:+--fallback-to-existing-cpa} \
  ${DRY} \
  --log-file /home/chenyechao/.openclaw/workspace/memory/aether-maintain-last.json
