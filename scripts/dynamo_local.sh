#!/usr/bin/env bash
# Start DynamoDB Local in Docker, create the tables, seed them from examples/demo-data,
# and print the env vars the server needs. Usage: scripts/dynamo_local.sh [--no-seed]
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d dynamodb

export STORAGE_BACKEND=dynamodb
export DYNAMODB_ENDPOINT_URL=http://localhost:8001
export AWS_REGION=us-east-1
# DynamoDB Local ignores credentials but boto3 insists on some.
export AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local

if [ "${1:-}" != "--no-seed" ]; then
  DATA_DIR=examples/demo-data python -m common.migrate --from file --to dynamodb --create-tables
fi

cat <<MSG

DynamoDB Local is up at $DYNAMODB_ENDPOINT_URL. Run the server against it with:

  export STORAGE_BACKEND=dynamodb DYNAMODB_ENDPOINT_URL=$DYNAMODB_ENDPOINT_URL \\
         AWS_REGION=us-east-1 AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local
  python -m server.main
MSG
