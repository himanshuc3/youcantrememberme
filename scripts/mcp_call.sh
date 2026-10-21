#!/usr/bin/env bash
# Call one MCP tool through the Inspector CLI. Usage: scripts/mcp_call.sh <tool> [key=value ...]
#   scripts/mcp_call.sh find_show query="The Lighthouse Keepers"
# Env: MCP_URL, INSPECT_USER (X-Demo-User header), INSPECTOR (command prefix).
set -euo pipefail
tool="$1"; shift
args=()
for kv in "$@"; do args+=(--tool-arg "$kv"); done
${INSPECTOR:-npx -y @modelcontextprotocol/inspector@2.11.0} --cli --transport http \
  --server-url "${MCP_URL:-http://127.0.0.1:8000/mcp}" \
  --header "X-Demo-User: ${INSPECT_USER:-inspector}" \
  --method tools/call --tool-name "$tool" "${args[@]}"
