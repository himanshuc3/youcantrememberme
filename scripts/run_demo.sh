#!/usr/bin/env bash
# Start the MCP server (:8000) and the web demo (:8080) on the offline demo data.
#   scripts/run_demo.sh                 # uses examples/demo-data (fictional show, no network)
#   DATA_DIR=data scripts/run_demo.sh   # uses data/ built by `python -m pipeline.run`
set -euo pipefail
cd "$(dirname "$0")/.."

export DATA_DIR="${DATA_DIR:-examples/demo-data}"
export IDENTITY_MODE=header          # demo only: one remembered profile per browser
export MCP_URL="http://127.0.0.1:${MCP_PORT:-8000}/mcp"

python -m server.main &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 2

echo "MCP server:  $MCP_URL   (data: $DATA_DIR)"
echo "Web demo:    http://127.0.0.1:${WEB_PORT:-8080}"
uvicorn web_demo.app:app --port "${WEB_PORT:-8080}"
