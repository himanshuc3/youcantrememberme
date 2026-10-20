"""Digest storage.

One document per show, keyed by TVmaze id, in the configured backend (JSON files locally by
default, DynamoDB in production and against DynamoDB Local: see common/backend.py). The server
only ever reads, the pipeline only ever writes.

`root` is `$DATA_DIR`: the file backend's location and where the pipeline keeps its raw-text
and LLM caches (those always stay on local disk, whichever backend holds the digests).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from common.backend import DocStore, make_backend
from common.models import ShowData

COLLECTION = "shows"


class ShowStore:
    def __init__(self, root: str | Path | None = None, backend: DocStore | None = None):
        self.root = Path(root or os.environ.get("DATA_DIR", "data"))
        self.backend = backend or make_backend(self.root)

    def save(self, data: ShowData) -> str:
        key = str(data.show.id)
        # via JSON text so dict keys (season numbers) become strings, as DynamoDB documents require
        self.backend.put(COLLECTION, key, json.loads(data.model_dump_json()))
        return key

    def get(self, show_id: int) -> ShowData | None:
        doc = self.backend.get(COLLECTION, str(show_id))
        return ShowData.model_validate(doc) if doc is not None else None

    def all(self) -> list[ShowData]:
        return [ShowData.model_validate(doc) for _, doc in self.backend.items(COLLECTION)]
