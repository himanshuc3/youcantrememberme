"""Per-user watch progress: "I'm through season 2, episode 4 of The Bear".

This is the cross-session state that lets someone come back later and just say "catch me up".

MVP storage is one small JSON file per user under `$DATA_DIR/users/`. The user id is hashed
for the filename (so an id can never be used as a path). On AWS Lambda the filesystem is
ephemeral, so deployment needs a DynamoDB-backed implementation of the same three methods.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from common.models import Pos


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
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.environ.get("DATA_DIR", "data"))
        self.dir = self.root / "users"

    def _path(self, user_id: str) -> Path:
        return self.dir / f"{hashlib.sha256(user_id.encode()).hexdigest()[:32]}.json"

    def load(self, user_id: str) -> UserProgress:
        path = self._path(user_id)
        if not path.exists():
            return UserProgress()
        return UserProgress.model_validate_json(path.read_text(encoding="utf-8"))

    def get(self, user_id: str, show_id: int) -> Progress | None:
        return self.load(user_id).shows.get(show_id)

    def latest(self, user_id: str) -> Progress | None:
        """The show the user touched most recently (for "catch me up" with no show named)."""
        shows = self.load(user_id).shows.values()
        return max(shows, key=lambda p: p.updated_at, default=None)

    def set(self, user_id: str, progress: Progress) -> None:
        data = self.load(user_id)
        data.shows[progress.show_id] = progress
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path(user_id)
        # Write to a temp file then rename, so a crash never leaves a half-written file.
        fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data.model_dump_json(indent=2))
        os.replace(tmp, path)
