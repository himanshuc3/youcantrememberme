import pytest

from common.models import EpisodeDigest, SeasonDigest, Show, ShowData
from server.assemble import assemble_recap, previously_on


def make_show(sizes: dict[int, int], with_season_digests=True) -> ShowData:
    eps = [
        EpisodeDigest(season=s, number=n, digest=f"S{s}E{n} happens. More detail on S{s}E{n}.")
        for s, size in sizes.items()
        for n in range(1, size + 1)
    ]
    seasons = (
        [
            SeasonDigest(season=s, digest=f"SEASON{s} summary.", episode_count=size)
            for s, size in sizes.items()
        ]
        if with_season_digests
        else []
    )
    return ShowData(
        show=Show(id=1, name="Test Show", season_sizes=sizes), episodes=eps, seasons=seasons
    )


def test_only_episodes_in_range_are_used():
    data = make_show({1: 3, 2: 3})
    recap = assemble_recap(data, (1, 1), (2, 2))
    assert "S2E3" not in recap.text
    assert recap.covered_through == "season 2, episode 2"


def test_full_season_uses_season_digest():
    data = make_show({1: 3, 2: 3})
    recap = assemble_recap(data, (1, 1), (1, 3))
    assert "SEASON1 summary." in recap.text
    assert "S1E1" not in recap.text


def test_partial_season_never_uses_season_digest():
    # The season-2 digest could mention S2E3, which is after the requested end.
    data = make_show({1: 3, 2: 3})
    recap = assemble_recap(data, (1, 1), (2, 2))
    assert "SEASON2" not in recap.text
    assert "S2E1" in recap.text and "S2E2" in recap.text


def test_range_starting_mid_season_does_not_use_season_digest():
    data = make_show({1: 3})
    recap = assemble_recap(data, (1, 2), (1, 3))
    assert "SEASON1" not in recap.text


def test_stale_season_digest_is_ignored():
    # Season grew after the digest was built (episode_count no longer matches).
    data = make_show({1: 3})
    data.seasons[0].episode_count = 2
    recap = assemble_recap(data, (1, 1), (1, 3))
    assert "SEASON1" not in recap.text


def test_end_without_episode_means_end_of_season():
    data = make_show({1: 3, 2: 3})
    recap = assemble_recap(data, (1, 1), (1, 10_000))
    assert recap.covered_through == "season 1, episode 3"


def test_long_ranges_drop_oldest_not_newest():
    data = make_show({1: 40}, with_season_digests=False)
    recap = assemble_recap(data, (1, 1), (1, 40), detail="brief")
    assert recap.truncated
    assert "S1E40" in recap.text
    assert "S1E1 " not in recap.text
    assert recap.starts_at != "season 1, episode 1"
    assert len(recap.text.split()) <= 90


def test_bad_ranges():
    data = make_show({1: 3})
    with pytest.raises(ValueError):
        assemble_recap(data, (1, 3), (1, 1))
    with pytest.raises(LookupError):
        assemble_recap(data, (5, 1), (5, 2))


def test_previously_on_excludes_the_episode_itself_and_crosses_seasons():
    data = make_show({1: 3, 2: 3})
    recap = previously_on(data, (2, 1), count=2)
    assert "S1E2" in recap.text and "S1E3" in recap.text
    assert "S2E1" not in recap.text


def test_previously_on_first_episode():
    data = make_show({1: 3})
    recap = previously_on(data, (1, 1))
    assert "first episode" in recap.text
