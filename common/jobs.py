"""On-demand show jobs: "someone asked for a show we don't have yet".

One small JSON file per TVmaze show id under `$DATA_DIR/jobs/`, so a show can only ever have
one job (that is the dedupe). The server enqueues; `pipeline.worker` claims and runs them.

MVP storage and queueing are local files and assume ONE worker process. On AWS the same
methods map onto DynamoDB (conditional writes for `enqueue` and `claim_next`) plus SQS.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["queued", "running", "ready", "failed"]

MAX_ATTEMPTS = 3


def _now() -> str:
    return datetime.now(UTC).isoformat()


def requester_hash(user_id: str) -> str:
    """Jobs record who asked only as a hash, for per-user rate limits."""
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


class Job(BaseModel):
    show_id: int  # TVmaze id
    name: str
    status: Status = "queued"
    requested_by: str  # requester_hash(...)
    requested_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    attempts: int = 0
    error: str | None = None

    @property
    def exhausted(self) -> bool:
        return self.status == "failed" and self.attempts >= MAX_ATTEMPTS


class JobStore:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.environ.get("DATA_DIR", "data"))
        self.dir = self.root / "jobs"

    def _path(self, show_id: int) -> Path:
        return self.dir / f"{show_id}.json"

    def _write(self, job: Job) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        job.updated_at = _now()
        fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(job.model_dump_json(indent=2))
        os.replace(tmp, self._path(job.show_id))

    def get(self, show_id: int) -> Job | None:
        path = self._path(show_id)
        if not path.exists():
            return None
        return Job.model_validate_json(path.read_text(encoding="utf-8"))

    def all(self) -> list[Job]:
        if not self.dir.exists():
            return []
        return [
            Job.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted(self.dir.glob("*.json"))
        ]

    def enqueue(self, show_id: int, name: str, requested_by: str) -> tuple[Job, bool]:
        """Queue a show. Returns (job, created). A queued or running job is returned
        untouched. A failed job with attempts left is re-queued, and so is a 'ready' one:
        callers only enqueue after a store miss, so its data must have gone missing."""
        existing = self.get(show_id)
        if existing is not None and (
            existing.status in ("queued", "running") or existing.exhausted
        ):
            return existing, False
        job = Job(
            show_id=show_id,
            name=name,
            requested_by=requested_by,
            attempts=existing.attempts if existing and existing.status == "failed" else 0,
        )
        self._write(job)
        return job, True

    def claim_next(self) -> Job | None:
        """Oldest queued job -> running (attempts + 1). Single-worker only."""
        queued = sorted(
            (j for j in self.all() if j.status == "queued"), key=lambda j: j.requested_at
        )
        if not queued:
            return None
        job = queued[0]
        job.status = "running"
        job.attempts += 1
        self._write(job)
        return job

    def mark_ready(self, job: Job) -> None:
        job.status, job.error = "ready", None
        self._write(job)

    def mark_failed(self, job: Job, error: str) -> None:
        job.status, job.error = "failed", error[:500]
        self._write(job)

    def requeue_stale_running(self) -> int:
        """Call at worker start-up: a crash can leave a job stuck in 'running'."""
        n = 0
        for job in self.all():
            if job.status == "running":
                job.status = "queued"
                self._write(job)
                n += 1
        return n

    def created_today(self, requested_by: str | None = None) -> int:
        today = datetime.now(UTC).date().isoformat()
        return sum(
            1
            for j in self.all()
            if j.requested_at.startswith(today)
            and (requested_by is None or j.requested_by == requested_by)
        )
