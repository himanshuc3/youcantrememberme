"""Copy every document from one storage backend into another.

    # existing JSON files -> DynamoDB tables (created if missing; DynamoDB Local via
    # DYNAMODB_ENDPOINT_URL)
    STORAGE_BACKEND=dynamodb python -m common.migrate --from file --src-dir data --create-tables

Reads the source and destination settings from the environment (see common/backend.py).
`--to` defaults to $STORAGE_BACKEND. Documents are keyed identically in every backend, so
re-running is safe: it overwrites with the same content.
"""

from __future__ import annotations

import argparse

from common.backend import COLLECTIONS, DynamoBackend, make_backend


def migrate(src, dst) -> dict[str, int]:
    counts = {}
    for collection in COLLECTIONS:
        pairs = src.items(collection)
        for key, doc in pairs:
            dst.put(collection, key, doc)
        counts[collection] = len(pairs)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="src", required=True, choices=["file", "dynamodb"])
    parser.add_argument("--to", dest="dst", choices=["file", "dynamodb"])
    parser.add_argument("--src-dir", help="root for --from file (default $DATA_DIR or ./data)")
    parser.add_argument("--create-tables", action="store_true", help="create DynamoDB tables")
    args = parser.parse_args()

    src = make_backend(args.src_dir, args.src)
    dst = make_backend(None, args.dst)
    if args.create_tables and isinstance(dst, DynamoBackend):
        dst.ensure_tables()
    print(migrate(src, dst))


if __name__ == "__main__":
    main()
