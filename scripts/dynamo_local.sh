#!/usr/bin/env bash
# Start DynamoDB Local in Docker, create the tables and load the demo show.
# Usage: scripts/dynamo_local.sh [--no-seed]     (--no-seed: create empty tables only)
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d dynamodb

export DYNAMODB_ENDPOINT_URL=${DYNAMODB_ENDPOINT_URL:-http://localhost:8001}
export AWS_REGION=${AWS_REGION:-us-east-1}
# DynamoDB Local ignores credentials but boto3 insists on some.
export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-local} AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-local}

if [ "${1:-}" = "--no-seed" ]; then
  python scripts/seed_demo.py --tables-only
else
  python scripts/seed_demo.py
fi

cat <<MSG

DynamoDB Local is up at $DYNAMODB_ENDPOINT_URL. Run the server against it with \`task server\`, or:

  export DYNAMODB_ENDPOINT_URL=$DYNAMODB_ENDPOINT_URL AWS_REGION=$AWS_REGION \\
         AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local
  python -m server.main
MSG
