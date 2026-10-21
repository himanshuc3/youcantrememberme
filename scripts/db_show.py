"""Look inside the local DynamoDB (or whatever STORAGE_BACKEND points at).

python scripts/db_show.py                # every collection: how many documents
python scripts/db_show.py shows          # keys + a one-line summary of each document
python scripts/db_show.py shows 526      # the full JSON document
"""

from __future__ import annotations

import json
import sys

from common.backend import COLLECTIONS, make_backend


def summary(collection: str, doc: dict) -> str:
    if collection == "shows":
        show = doc["show"]
        return f"{show['name']}: {len(doc['episodes'])} episode digests, seasons {show['season_sizes']}"
    if collection == "jobs":
        return (
            f"{doc['name']}: {doc['status']} (attempts {doc['attempts']}) {doc.get('error') or ''}"
        )
    return ", ".join(sorted(doc))


def main() -> None:
    backend = make_backend()
    if len(sys.argv) == 1:
        for c in COLLECTIONS:
            print(f"{c}: {len(backend.items(c))} documents")
    elif len(sys.argv) == 2:
        for key, doc in backend.items(sys.argv[1]):
            print(f"{key}\t{summary(sys.argv[1], doc)}")
    else:
        doc = backend.get(sys.argv[1], sys.argv[2])
        print(json.dumps(doc, indent=2) if doc is not None else "not found")


if __name__ == "__main__":
    main()
