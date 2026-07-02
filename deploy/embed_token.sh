#!/usr/bin/env bash
# Embed the (organizer-shared) MCP token into the agent's MCP URL so
# platform-created bench sessions authenticate without a vault.
# Run from repo root:  bash deploy/embed_token.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

CURRENT_VERSION=$(ant beta:agents retrieve --agent-id agent_01PU7KPhV5EMnY1sYdN77DKs | python3 -c "import sys,json;print(json.load(sys.stdin)['version'])")
echo "current version: $CURRENT_VERSION"

python3 - <<EOF | ant beta:agents update
import os
url = os.environ["MCCTX_MCP_URL"] + "?token=" + os.environ["MCP_AUTH_TOKEN"]
print(f'''agent_id: agent_01PU7KPhV5EMnY1sYdN77DKs
version: ${CURRENT_VERSION}
mcp_server:
  - type: url
    name: mccontext
    url: "{url}"
''')
EOF
echo "--- verifying"
ant beta:agents retrieve --agent-id agent_01PU7KPhV5EMnY1sYdN77DKs | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('VERSION:', d['version'], '| token embedded:', 'token=' in d['mcp_servers'][0]['url'])"
