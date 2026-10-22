"""Pluggable document storage behind ShowStore and JobStore.

Two tiny collections (`shows`, `jobs`), each a key -> JSON-object map, so one
three-method interface covers every store:

    STORAGE_BACKEND=file      (default) JSON files under $DATA_DIR/<collection>/<key>.json
    STORAGE_BACKEND=dynamodb  AWS in production, DynamoDB Local in development; one table per collection

Settings (nothing is hardcoded; no secrets live in the repo):
  DATA_DIR                  file backend root, and the on-disk pipeline caches (default ./data)
  DYNAMODB_TABLE_PREFIX     default "youcantrememberme-"  -> youcantrememberme-shows, ...
  DYNAMODB_ENDPOINT_URL     optional, e.g. http://localhost:8001 for DynamoDB Local
  AWS_REGION                default us-east-1 (plus the standard AWS credential chain)

Documents are plain JSON (string keys), so a document is identical across backends and
`python -m common.migrate` can copy any backend into any other. The DynamoDB driver is
imported lazily: `pip install -e ".[dynamodb]"`.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol

COLLECTIONS = ("shows", "jobs")

Doc = dict[str, Any]


class DocStore(Protocol):
    def get(self, collection: str, key: str) -> Doc | None: ...

    def put(self, collection: str, key: str, doc: Doc) -> None: ...

    def items(self, collection: str) -> list[tuple[str, Doc]]:
        """Every (key, document) in the collection, sorted by key."""
        ...


class FileBackend:
    """`<root>/<collection>/<key>.json`, written atomically (temp file + rename)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _dir(self, collection: str) -> Path:
        return self.root / collection

    def get(self, collection: str, key: str) -> Doc | None:
        path = self._dir(collection) / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, collection: str, key: str, doc: Doc) -> None:
        d = self._dir(collection)
        d.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        os.replace(tmp, d / f"{key}.json")

    def items(self, collection: str) -> list[tuple[str, Doc]]:
        d = self._dir(collection)
        if not d.exists():
            return []
        return [
            (p.stem, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(d.glob("*.json"))
        ]


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


def make_backend(root: str | Path | None = None, kind: str | None = None) -> DocStore:
    kind = (kind or os.environ.get("STORAGE_BACKEND") or "file").lower()
    if kind == "file":
        return FileBackend(root or os.environ.get("DATA_DIR", "data"))
    if kind == "dynamodb":
        return DynamoBackend()
    raise ValueError(f"unknown STORAGE_BACKEND {kind!r}; use file or dynamodb")
