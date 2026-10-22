"""Worker for on-demand shows: runs the pipeline for jobs the server queued.

    ON_DEMAND=1 python -m server.main        # terminal 1: server enqueues unknown shows
    python -m pipeline.worker                # terminal 2: processes them (polls forever)
    python -m pipeline.worker --once         # drain the queue, then exit

`--mode baseline` (default, no AWS needed, ready in seconds) or `--mode llm` (Claude on
Bedrock; slower, better recaps). Run one worker only: the file-backed queue is not safe for
several (see common/jobs.py).
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable

from common.jobs import Job, JobStore
from common.models import ShowData
from common.store import ShowStore
from pipeline.llm import LLM, BedrockLLM, DiskCachedLLM
from pipeline.run import process_show

Process = Callable[[str, str, ShowStore, LLM | None], ShowData]


def run_once(
    jobs: JobStore,
    store: ShowStore,
    mode: str = "baseline",
    llm: LLM | None = None,
    process: Process = process_show,
) -> Job | None:
    """Claim and run one job. Returns it (with its final status), or None if none queued."""
    job = jobs.claim_next()
    if job is None:
        return None
    try:
        data = process(job.name, mode, store, llm)
        if data.show.id != job.show_id:
            raise LookupError(f"asked for TVmaze id {job.show_id}, name resolved to another show")
        if not data.episodes:
            raise LookupError(f"{job.name} has no episode text to summarize")
    except Exception as exc:  # noqa: BLE001  (record any failure on the job, keep the loop alive)
        jobs.mark_failed(job, f"{type(exc).__name__}: {exc}")
    else:
        jobs.mark_ready(job)
    return job


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["baseline", "llm"], default="baseline")
    parser.add_argument("--once", action="store_true", help="drain the queue and exit")
    parser.add_argument("--poll", type=float, default=5.0, help="seconds between queue checks")
    args = parser.parse_args()

    store = ShowStore()
    jobs = JobStore(store.root, store.backend)
    llm = DiskCachedLLM(BedrockLLM(), store.root / "cache" / "llm") if args.mode == "llm" else None
    if (n := jobs.requeue_stale_running()) and not args.once:
        print(f"re-queued {n} job(s) left running by a previous worker")
    while True:
        job = run_once(jobs, store, args.mode, llm)
        if job is not None:
            print(
                f"{job.name} ({job.show_id}): {job.status}"
                + (f" - {job.error}" if job.error else "")
            )
            continue
        if args.once:
            return
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
