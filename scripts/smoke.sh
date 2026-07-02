#!/usr/bin/env bash
# Post-deploy smoke: scripts/smoke.sh <base-url> [--turn]
# --turn sends one real chat turn (costs ~$0.05 when PENNY_BACKEND=agent).
set -euo pipefail
BASE="${1:?usage: smoke.sh <base-url> [--turn]}"

H=$(curl -sf --max-time 10 "$BASE/healthz")
echo "healthz: $H"
echo "$H" | grep -q '"ok":true' || { echo "FAIL: not ok"; exit 1; }

SNAP=$(curl -sfN --max-time 10 "$BASE/events" | head -1)
echo "$SNAP" | grep -q '"type": "snapshot"' || { echo "FAIL: no SSE snapshot"; exit 1; }
echo "sse: snapshot ok"

if [ "${2:-}" = "--turn" ]; then
  R=$(curl -sf --max-time 120 -X POST "$BASE/turn" -H "Content-Type: application/json" \
      -d '{"session_id":"smoke","text":"In one sentence, who are you?"}')
  echo "$R" | grep -q '"type": "done"' || { echo "FAIL: turn did not complete"; exit 1; }
  echo "turn: ok"
fi
echo "SMOKE PASS"
