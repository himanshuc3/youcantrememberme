"""Create the DynamoDB tables (if missing) and load the fictional demo show into them.

    python scripts/seed_demo.py                 # reads examples/demo-data/shows/*.json
    python scripts/seed_demo.py --tables-only   # just create the tables

Uses the usual settings (DYNAMODB_ENDPOINT_URL etc.), so it works against DynamoDB Local
(`task db:up` runs it) and, with real credentials, against AWS. Safe to re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

from common.backend import DynamoBackend
from common.models import ShowData
from common.store import ShowStore

DEMO_SHOWS = Path(__file__).resolve().parent.parent / "examples" / "demo-data" / "shows"


def main() -> None:
    backend = DynamoBackend()
    backend.ensure_tables()
    if "--tables-only" in sys.argv:
        return
    store = ShowStore(backend=backend)
    for path in sorted(DEMO_SHOWS.glob("*.json")):
        data = ShowData.model_validate_json(path.read_text(encoding="utf-8"))
        store.save(data)
        print(f"seeded {data.show.name} ({data.show.id})")


if __name__ == "__main__":
    main()
