"""What to do when someone asks for a show we have no digests for.

The reply is always immediate and honest ("I don't have that yet"). Behind it:

1. check the name against TVmaze (cheap; filters typos and non-shows before anything costs
   money),
2. enqueue a pipeline job, deduped on the TVmaze show id,
3. the worker (`python -m pipeline.worker`) fills the ShowStore; the next request just works.

Cost guards: a global and a per-user cap on newly created jobs per UTC day.

Off unless `ON_DEMAND=1` (see server/main.py), so tests and offline demos never touch the
network. Settings: ON_DEMAND_DAILY_LIMIT (default 20), ON_DEMAND_USER_LIMIT (default 3).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from common.jobs import Job, JobStore, requester_hash

Lookup = Callable[[str], "tuple[int, str] | None"]

Kind = Literal["pending", "unknown", "unavailable"]


@dataclass
class Request:
    kind: Kind
    text: str
    show_id: int | None = None
    name: str | None = None
    status: str | None = None


def _pending(job: Job, created: bool) -> Request:
    if created:
        text = (
            f"I don't have {job.name} yet. I've started getting it ready, "
            "so ask me again in a few minutes."
        )
    else:
        text = f"I'm still getting {job.name} ready. Ask me again in a few minutes."
    return Request("pending", text, job.show_id, job.name, job.status)


class OnDemand:
    def __init__(
        self,
        jobs: JobStore,
        lookup: Lookup,
        daily_limit: int = 20,
        user_limit: int = 3,
    ):
        self.jobs = jobs
        self.lookup = lookup
        self.daily_limit = daily_limit
        self.user_limit = user_limit

    @classmethod
    def from_env(cls, root=None, lookup: Lookup | None = None) -> OnDemand:
        if lookup is None:
            from pipeline.sources.tvmaze import lookup_show

            lookup = lookup_show
        return cls(
            JobStore(root),
            lookup,
            daily_limit=int(os.environ.get("ON_DEMAND_DAILY_LIMIT", "20")),
            user_limit=int(os.environ.get("ON_DEMAND_USER_LIMIT", "3")),
        )

    def status(self, show_id: int) -> Request | None:
        """State of an existing job, or None if the show was never requested."""
        job = self.jobs.get(show_id)
        if job is None or job.status == "ready":
            return None  # "ready" means the data is (or is about to be) in the ShowStore
        if job.exhausted:
            return Request(
                "unavailable",
                f"I wasn't able to get {job.name} ready. Sorry about that.",
                job.show_id,
                job.name,
                job.status,
            )
        return _pending(job, created=False)

    def request(self, user_id: str, query: str) -> Request:
        """Called when `query` matched no stored show."""
        try:
            found = self.lookup(query)
        except Exception:  # noqa: BLE001  (network, rate limit...: degrade to a plain miss)
            return Request("unknown", "")
        if found is None:
            return Request("unknown", "")
        show_id, name = found

        existing = self.status(show_id)
        if existing is not None:
            return existing

        who = requester_hash(user_id)
        if (
            self.jobs.created_today() >= self.daily_limit
            or self.jobs.created_today(who) >= self.user_limit
        ):
            return Request(
                "unavailable",
                f"I don't have {name} yet, and I can't add new shows right now. "
                "Try again tomorrow.",
                show_id,
                name,
            )
        job, created = self.jobs.enqueue(show_id, name, who)
        return _pending(job, created)
