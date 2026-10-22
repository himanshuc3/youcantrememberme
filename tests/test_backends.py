"""Storage behaviour on DynamoDB (in memory via moto, so no server is needed)."""

from common.backend import DynamoBackend, getDBConnection
from common.jobs import JobStore
from common.models import EpisodeDigest, SeasonDigest, Show, ShowData
from common.store import ShowStore


def _show() -> ShowData:
    return ShowData(
        show=Show(id=7, name="The Test Show", season_sizes={1: 2, 2: 1}),
        episodes=[EpisodeDigest(season=1, number=1, digest="One.")],
        seasons=[SeasonDigest(season=1, digest="S1.", episode_count=2)],
    )


def test_documents_round_trip(dynamo):
    assert dynamo.get("shows", "1") is None
    dynamo.put("shows", "1", {"a": 1})
    dynamo.put("shows", "1", {"a": 2})  # put replaces
    dynamo.put("shows", "2", {"b": {"1": "x"}})
    assert dynamo.get("shows", "1") == {"a": 2}
    assert dynamo.items("shows") == [("1", {"a": 2}), ("2", {"b": {"1": "x"}})]
    assert dynamo.items("jobs") == []


def test_show_store(dynamo, tmp_path):
    shows = ShowStore(tmp_path, backend=dynamo)
    assert shows.get(7) is None and shows.all() == []
    shows.save(_show())
    assert shows.get(7) == _show()  # int season keys survive the JSON round trip
    assert [d.show.id for d in shows.all()] == [7]


def test_job_store_lifecycle(dynamo, tmp_path):
    jobs = JobStore(tmp_path, dynamo)
    job, created = jobs.enqueue(7, "The Test Show")
    assert created and job.status == "queued"
    assert jobs.enqueue(7, "The Test Show")[1] is False  # deduped
    claimed = jobs.claim_next()
    assert claimed.status == "running" and claimed.attempts == 1
    jobs.mark_ready(claimed)
    assert jobs.get(7).status == "ready"
    assert jobs.created_today() == 1


def test_table_names_use_the_prefix(dynamo):
    assert dynamo.table_name("shows") == "youcantrememberme-shows"
    assert DynamoBackend(prefix="x-", resource=dynamo.resource).table_name("jobs") == "x-jobs"


def test_make_backend_is_always_dynamodb(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    assert isinstance(getDBConnection(), DynamoBackend)
