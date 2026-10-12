"""Unknown show -> honest reply + a deduped job -> worker fills the store -> next ask works."""

import pytest

from common.jobs import JobStore
from common.models import EpisodeDigest, Show, ShowData
from server import tools
from server.on_demand import OnDemand

SHOWS = {"new show": (99, "New Show")}  # what the fake TVmaze knows


def fake_lookup(query):
    return SHOWS.get(query.lower().strip())


@pytest.fixture
def env(stores):
    shows, progress = stores
    jobs = JobStore(shows.root)
    od = OnDemand(jobs, fake_lookup, daily_limit=5, user_limit=2)
    return shows, progress, jobs, od


def test_unknown_real_show_is_queued_once(env):
    shows, _, jobs, od = env
    first = tools.find_show(shows, "New Show", on_demand=od, user_id="u1")
    assert first["found"] is False and first["pending"] is True
    assert "ask me again" in first["text"]
    assert [j.show_id for j in jobs.all()] == [99]

    again = tools.find_show(shows, "New Show", on_demand=od, user_id="u2")  # another user
    assert again["pending"] and "still getting" in again["text"]
    assert len(jobs.all()) == 1  # deduped on the TVmaze id


def test_not_a_show_is_not_queued(env):
    shows, _, jobs, od = env
    out = tools.get_recap(shows, "Zzzzz", 1, on_demand=od, user_id="u1")
    assert out["found"] is False and not out.get("pending")
    assert "I can recap" in out["text"] and jobs.all() == []


def test_lookup_failure_degrades_to_a_plain_miss(env):
    shows, _, jobs, _ = env

    def boom(query):
        raise TimeoutError

    od = OnDemand(jobs, boom)
    out = tools.find_show(shows, "New Show", on_demand=od)
    assert out["found"] is False and "I can recap" in out["text"] and jobs.all() == []


def test_without_on_demand_behaviour_is_unchanged(env):
    shows, *_ = env
    out = tools.find_show(shows, "New Show")
    assert out["found"] is False and "I can recap" in out["text"]


def test_user_and_daily_limits(env):
    shows, _, jobs, od = env
    SHOWS.update({f"s{i}": (100 + i, f"S{i}") for i in range(6)})
    try:
        outs = [tools.find_show(shows, f"s{i}", on_demand=od, user_id="u1") for i in range(3)]
    finally:
        for i in range(6):
            SHOWS.pop(f"s{i}")
    assert [o.get("pending", False) for o in outs] == [True, True, False]  # user_limit=2
    assert "can't add new shows" in outs[2]["text"]
    assert len(jobs.all()) == 2


def test_progress_can_be_saved_before_the_show_is_ready(env):
    shows, progress, _jobs, od = env
    out = tools.save_progress(shows, progress, "u1", "New Show", 2, 4, on_demand=od)
    assert out["saved"] and out["pending"] and "season 2, episode 4" in out["text"]
    assert progress.get("u1", 99).pos == (2, 4)

    # catch me up before it's ready: "still working", not "which episode?"
    waiting = tools.catch_me_up(shows, progress, "u1", on_demand=od)
    assert waiting["pending"] and "still getting New Show ready" in waiting["text"]
    assert not waiting.get("needs_progress")


def test_exhausted_failure_says_sorry_and_stops_retrying(env):
    shows, _, jobs, od = env
    tools.find_show(shows, "New Show", on_demand=od)
    for _ in range(3):
        job = jobs.claim_next()
        assert job is not None
        jobs.mark_failed(job, "boom")
        jobs.enqueue(99, "New Show", "x")  # re-queue while attempts remain
    out = tools.find_show(shows, "New Show", on_demand=od)
    assert "wasn't able" in out["text"]
    assert jobs.claim_next() is None


def test_worker_fills_the_store_and_the_next_request_works(env):
    from pipeline.worker import run_once

    shows, progress, jobs, od = env
    tools.save_progress(shows, progress, "u1", "New Show", 1, 2, on_demand=od)

    def fake_process(name, mode, store, llm):
        data = ShowData(
            show=Show(id=99, name=name, season_sizes={1: 2}),
            episodes=[EpisodeDigest(season=1, number=n, digest=f"E{n}.") for n in (1, 2)],
        )
        store.save(data)
        return data

    job = run_once(jobs, shows, process=fake_process)
    assert job.status == "ready"
    out = tools.catch_me_up(shows, progress, "u1", on_demand=od)
    assert out["remembered_progress"] and "E1." in out["text"] and "E2." in out["text"]


def test_worker_records_failures(env):
    from pipeline.worker import run_once

    shows, _, jobs, od = env
    tools.find_show(shows, "New Show", on_demand=od)

    def broken(*_):
        raise LookupError("TVmaze has no show")

    job = run_once(jobs, shows, process=broken)
    assert job.status == "failed" and "TVmaze has no show" in job.error
    assert run_once(jobs, shows, process=broken) is None  # nothing left to claim


def test_over_http_the_miss_queues_a_job(env, monkeypatch):
    """Same thing through the real MCP tool layer (Context injection, JSON-RPC)."""
    import json

    from starlette.testclient import TestClient

    from server.main import build_app

    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    shows, progress, jobs, od = env
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "get_recap", "arguments": {"show": "New Show", "to_season": 1}},
    }
    with TestClient(build_app(shows, progress, od)) as client:
        resp = client.post("/mcp", json=body, headers=headers)
    result = json.loads(resp.json()["result"]["content"][0]["text"])
    assert result["pending"] is True and result["show_id"] == 99
    assert [j.status for j in jobs.all()] == ["queued"]
