"""Document storage behind ShowStore and JobStore: always DynamoDB.

Two tiny collections (`shows`, `jobs`), one DynamoDB table each, so one three-method interface
covers every store. Real AWS in production, DynamoDB Local (Docker, `task db:up`) in development
and `moto` in tests; there is no other backend and no file fallback.

Settings (nothing is hardcoded; no secrets live in the repo):
  DYNAMODB_TABLE_PREFIX     default "youcantrememberme-"  -> youcantrememberme-shows, ...
  DYNAMODB_ENDPOINT_URL     optional, e.g. http://localhost:8001 for DynamoDB Local
  AWS_REGION                default us-east-1 (plus the standard AWS credential chain)
  DATA_DIR                  only the pipeline's on-disk download / LLM caches (default ./data)

Documents are plain JSON (string keys). boto3 is imported lazily.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

COLLECTIONS = ("shows", "jobs")

Doc = dict[str, Any]


class DocStore(Protocol):
    def get(self, collection: str, key: str) -> Doc | None: ...

    def put(self, collection: str, key: str, doc: Doc) -> None: ...

    def items(self, collection: str) -> list[tuple[str, Doc]]:
        """Every (key, document) in the collection, sorted by key."""
        ...


class DynamoBackend:
    """One table per logical collection, partition key `id` (string).

    The document is stored whole as a JSON string in `data`: nothing here is queried by
    attribute, this sidesteps DynamoDB's float/Decimal handling, and the shape is identical
    to the other backends. An item is capped at 400 KB, ample for a show's digests.
    """

    def __init__(self, prefix: str | None = None, region: str | None = None, resource=None):
        if resource is None:
            import boto3  # needs the `dynamodb` extra (already present on AWS Lambda)

            resource = boto3.resource(
                "dynamodb",
                region_name=region or os.environ.get("AWS_REGION", "us-east-1"),
                endpoint_url=os.environ.get("DYNAMODB_ENDPOINT_URL") or None,
            )
        self.resource = resource
        self.prefix = (
            prefix
            if prefix is not None
            else os.environ.get("DYNAMODB_TABLE_PREFIX", "youcantrememberme-")
        )

    def table_name(self, collection: str) -> str:
        return f"{self.prefix}{collection}"

    def _table(self, collection: str):
        return self.resource.Table(self.table_name(collection))

    def get(self, collection: str, key: str) -> Doc | None:
        item = self._table(collection).get_item(Key={"id": key}).get("Item")
        return json.loads(item["data"]) if item else None

    def put(self, collection: str, key: str, doc: Doc) -> None:
        self._table(collection).put_item(Item={"id": key, "data": json.dumps(doc)})

    def items(self, collection: str) -> list[tuple[str, Doc]]:
        table, items, kwargs = self._table(collection), [], {}
        while True:  # a scan returns at most 1 MB per page
            page = table.scan(**kwargs)
            items += page["Items"]
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return [(i["id"], json.loads(i["data"])) for i in sorted(items, key=lambda i: i["id"])]

    def ensure_tables(self) -> None:
        """Create the tables if missing (DynamoDB Local / dev). Production tables normally
        come from infrastructure-as-code with the same schema: `id` (S) hash key."""
        existing = {t.name for t in self.resource.tables.all()}
        for c in COLLECTIONS:
            name = self.table_name(c)
            if name in existing:
                continue
            table = self.resource.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()


def getDBConnection() -> DocStore:
    return DynamoBackend()
