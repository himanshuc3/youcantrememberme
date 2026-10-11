from common.progress import Progress, ProgressStore
from server import tools
from server.identity import GUEST, resolve_user_id


def test_store_roundtrip_and_latest(tmp_path):
    ps = ProgressStore(tmp_path)
    assert ps.get("u", 1) is None and ps.latest("u") is None
    ps.set("u", Progress(show_id=1, season=1, episode=2, updated_at="2026-01-01T00:00:00"))
    ps.set("u", Progress(show_id=2, season=3, episode=1, updated_at="2026-02-01T00:00:00"))
    assert ps.get("u", 1).pos == (1, 2)
    assert ps.latest("u").show_id == 2
    # a second ProgressStore on the same dir sees it: it really is persisted
    assert ProgressStore(tmp_path).get("u", 2).pos == (3, 1)


def test_users_are_separate_and_ids_cannot_escape_the_directory(tmp_path):
    ps = ProgressStore(tmp_path)
    ps.set("alice", Progress(show_id=1, season=1, episode=1))
    ps.set("../../etc/passwd", Progress(show_id=1, season=2, episode=2))
    assert ps.get("bob", 1) is None
    assert ps.get("alice", 1).pos == (1, 1)
    assert {p.parent for p in tmp_path.rglob("*.json")} == {tmp_path / "users"}


def test_overwriting_progress_replaces_it(tmp_path):
    ps = ProgressStore(tmp_path)
    ps.set("u", Progress(show_id=1, season=2, episode=4))
    ps.set("u", Progress(show_id=1, season=2, episode=3))  # "actually I'm on episode 3"
    assert ps.get("u", 1).pos == (2, 3)


def test_save_then_catch_me_up_across_sessions(stores):
    shows, progress = stores
    out = tools.save_progress(shows, progress, "u1", "test show", 2, 2)
    assert out["saved"] and out["through"] == "season 2, episode 2"

    # a later "session": nothing but the user id is shared
    recap = tools.catch_me_up(shows, progress, "u1")
    assert recap["remembered_progress"]
    assert "SEASON1 summary." in recap["text"]
    assert "S2E1" in recap["text"] and "S2E2" in recap["text"]
    assert "S2E3" not in recap["text"]  # never past the saved point
    assert recap["covered_through"] == "season 2, episode 2"


def test_catch_me_up_with_no_progress_asks_instead_of_guessing(stores):
    shows, progress = stores
    out = tools.catch_me_up(shows, progress, "nobody", "The Test Show")
    assert out["needs_progress"] and "Which season and episode" in out["text"]
    assert tools.catch_me_up(shows, progress, "nobody")["needs_progress"]


def test_progress_is_per_user(stores):
    shows, progress = stores
    tools.save_progress(shows, progress, "alice", "The Test Show", 1, 3)
    assert tools.catch_me_up(shows, progress, "bob", "The Test Show")["needs_progress"]
    assert "S1E3" not in tools.catch_me_up(shows, progress, "alice")["text"]  # season digest


def test_save_progress_rejects_episodes_that_do_not_exist(stores):
    shows, progress = stores
    bad_season = tools.save_progress(shows, progress, "u", "The Test Show", 9, 1)
    bad_episode = tools.save_progress(shows, progress, "u", "The Test Show", 1, 99)
    assert not bad_season["saved"] and "seasons 1 to 2" in bad_season["text"]
    assert not bad_episode["saved"] and "3 episodes" in bad_episode["text"]
    assert progress.get("u", 7) is None  # nothing was stored


def test_save_progress_unknown_show(stores):
    shows, progress = stores
    assert tools.save_progress(shows, progress, "u", "Nonexistent", 1, 1)["found"] is False


def test_previously_on_defaults_to_saved_progress_and_includes_last_watched(stores):
    shows, progress = stores
    tools.save_progress(shows, progress, "u", "The Test Show", 2, 1)
    out = tools.get_previously_on(shows, progress, "u")
    assert "S2E1" in out["text"] and "S1E3" in out["text"]
    assert "S2E2" not in out["text"]


def test_previously_on_explicit_episode_does_not_need_progress(stores):
    shows, progress = stores
    out = tools.get_previously_on(shows, progress, "u", "The Test Show", 2, 1)
    assert "S1E3" in out["text"] and "S2E1" not in out["text"]


def test_previously_on_without_progress_asks(stores):
    shows, progress = stores
    assert tools.get_previously_on(shows, progress, "u")["needs_progress"]
    assert tools.get_previously_on(shows, progress, "u", "The Test Show")["needs_progress"]


class FakeHeaders(dict):
    pass


def test_identity_tiers():
    h = FakeHeaders({"x-demo-user": "browser-123"})
    assert resolve_user_id(None, h, mode="guest") == GUEST  # header ignored by default
    assert resolve_user_id(None, h, mode="header") == "demo:browser-123"
    assert resolve_user_id(None, FakeHeaders(), mode="header") == GUEST
    assert resolve_user_id(None, None, mode="header") == GUEST


def test_find_show_has_spoken_text(stores):
    shows, _ = stores
    out = tools.find_show(shows, "the test show")
    assert out["found"] and "The Test Show" in out["text"]
    assert "season 1 has 3 episodes" in out["text"]
    assert tools.find_show(shows, "Nonexistent")["found"] is False
