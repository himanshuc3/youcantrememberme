"""The same store behaviour must hold on every backend (file, DynamoDB).

DynamoDB is exercised through moto, so no server is needed.
"""

import pytest

from common.backend import DynamoBackend, FileBackend, make_backend
from common.jobs import JobStore
from common.migrate import migrate
from common.models import EpisodeDigest, SeasonDigest, Show, ShowData
from common.progress import Progress, ProgressStore
from common.store import ShowStore

moto = pytest.importorskip("moto")


def _show() -> ShowData:
    return ShowData(
        show=Show(id=7, name="The Test Show", season_sizes={1: 2, 2: 1}),
        episodes=[EpisodeDigest(season=1, number=1, digest="One.")],
        seasons=[SeasonDigest(season=1, digest="S1.", episode_count=2)],
    )


@pytest.fixture(params=["file", "dynamodb"])
def backend(request, tmp_path, monkeypatch):
    if request.param == "file":
        yield FileBackend(tmp_path)
    else:
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
        with moto.mock_aws():
            import boto3

            be = DynamoBackend(resource=boto3.resource("dynamodb", region_name="us-east-1"))
            be.ensure_tables()
            yield be


def test_documents_round_trip(backend):
    assert backend.get("shows", "1") is None
    backend.put("shows", "1", {"a": 1})
    backend.put("shows", "1", {"a": 2})  # put replaces
    backend.put("shows", "2", {"b": {"1": "x"}})
    assert backend.get("shows", "1") == {"a": 2}
    assert backend.items("shows") == [("1", {"a": 2}), ("2", {"b": {"1": "x"}})]
    assert backend.items("jobs") == []


def test_show_store(backend, tmp_path):
    shows = ShowStore(tmp_path, backend=backend)
    assert shows.get(7) is None and shows.all() == []
    shows.save(_show())
    assert shows.get(7) == _show()  # int season keys survive the JSON round trip
    assert [d.show.id for d in shows.all()] == [7]


def test_progress_store(backend, tmp_path):
    ps = ProgressStore(tmp_path, backend=backend)
    ps.set("alexa-user-1", Progress(show_id=7, season=2, episode=1))
    assert ProgressStore(tmp_path, backend=backend).get("alexa-user-1", 7).pos == (2, 1)
    assert ps.get("someone-else", 7) is None
    # the raw user id is never stored as a key
    assert all("alexa-user-1" not in key for key, _ in backend.items("users"))


def test_job_store_lifecycle(backend, tmp_path):
    jobs = JobStore(tmp_path, backend=backend)
    job, created = jobs.enqueue(7, "The Test Show", "me")
    assert created and job.status == "queued"
    assert jobs.enqueue(7, "The Test Show", "me")[1] is False  # deduped
    claimed = jobs.claim_next()
    assert claimed.status == "running" and claimed.attempts == 1
    jobs.mark_ready(claimed)
    assert jobs.get(7).status == "ready"
    assert jobs.created_today("me") == 1


def test_migrate_file_to_other_backend(backend, tmp_path):
    src = FileBackend(tmp_path / "src")
    ShowStore(backend=src, root=tmp_path / "src").save(_show())
    ProgressStore(backend=src, root=tmp_path / "src").set(
        "u", Progress(show_id=7, season=1, episode=1)
    )
    counts = migrate(src, backend)
    assert counts == {"shows": 1, "users": 1, "jobs": 0}
    assert ShowStore(tmp_path, backend=backend).get(7) == _show()
    assert ProgressStore(tmp_path, backend=backend).get("u", 7).pos == (1, 1)


def test_make_backend_selection(monkeypatch, tmp_path):
    assert isinstance(make_backend(tmp_path), FileBackend)
    monkeypatch.setenv("STORAGE_BACKEND", "bogus")
    with pytest.raises(ValueError):
        make_backend(tmp_path)
