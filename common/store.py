"""Digest storage.

MVP: one JSON file per show under `$DATA_DIR/shows/<tvmaze id>.json` (default `./data`).
The same interface can later be backed by S3 or DynamoDB for deployment; the server only
ever reads, the pipeline only ever writes.
"""

from __future__ import annotations

import os
from pathlib import Path

from common.models import ShowData


class ShowStore:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.environ.get("DATA_DIR", "data"))
        self.dir = self.root / "shows"

    def save(self, data: ShowData) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{data.show.id}.json"
        path.write_text(data.model_dump_json(indent=2), encoding="utf-8")
        return path

    def get(self, show_id: int) -> ShowData | None:
        path = self.dir / f"{show_id}.json"
        if not path.exists():
            return None
        return ShowData.model_validate_json(path.read_text(encoding="utf-8"))

    def all(self) -> list[ShowData]:
        if not self.dir.exists():
            return []
        return [
            ShowData.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted(self.dir.glob("*.json"))
        ]
