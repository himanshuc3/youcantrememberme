"""Per-user watch progress: "I'm through season 2, episode 4 of The Bear".

This is the cross-session state that lets someone come back later and just say "catch me up".

One document per user in the configured backend (common/backend.py); the user id is hashed
to form the key. On AWS Lambda the filesystem is ephemeral, so production uses DynamoDB
(STORAGE_BACKEND=dynamodb).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from common.backend import DocStore, make_backend
from common.models import Pos

COLLECTION = "users"


class Progress(BaseModel):
    show_id: int
    season: int
    episode: int
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def pos(self) -> Pos:
        return (self.season, self.episode)


class UserProgress(BaseModel):
    shows: dict[int, Progress] = Field(default_factory=dict)  # show id -> progress


class ProgressStore:
    def __init__(self, root: str | Path | None = None, backend: DocStore | None = None):
        self.root = Path(root or os.environ.get("DATA_DIR", "data"))
        self.backend = backend or make_backend(self.root)

    @staticmethod
    def _key(user_id: str) -> str:
        # hashed, so a user id can never be used as a path or leak into a table of keys
        return hashlib.sha256(user_id.encode()).hexdigest()[:32]

    def load(self, user_id: str) -> UserProgress:
        doc = self.backend.get(COLLECTION, self._key(user_id))
        return UserProgress.model_validate(doc) if doc is not None else UserProgress()

    def get(self, user_id: str, show_id: int) -> Progress | None:
        return self.load(user_id).shows.get(show_id)

    def latest(self, user_id: str) -> Progress | None:
        """The show the user touched most recently (for "catch me up" with no show named)."""
        shows = self.load(user_id).shows.values()
        return max(shows, key=lambda p: p.updated_at, default=None)

    def set(self, user_id: str, progress: Progress) -> None:
        data = self.load(user_id)
        data.shows[progress.show_id] = progress
        self.backend.put(COLLECTION, self._key(user_id), json.loads(data.model_dump_json()))
