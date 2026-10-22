#!/usr/bin/env bash
# Start the MCP server (:8000) and the chat web demo (:8080). Needs DynamoDB Local with the demo
# show loaded (`task db:up`), plus the usual DYNAMODB_ENDPOINT_URL / AWS_* settings (`task demo` sets them).
set -euo pipefail
cd "$(dirname "$0")/.."

export PORT="${MCP_PORT:-8000}"          # what server.main listens on
export MCP_URL="http://127.0.0.1:${MCP_PORT:-8000}/mcp"

python -m server.main &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 2

echo "MCP server:  $MCP_URL"
echo "Web demo:    http://127.0.0.1:${WEB_PORT:-8080}"
uvicorn web_demo.app:app --port "${WEB_PORT:-8080}"
