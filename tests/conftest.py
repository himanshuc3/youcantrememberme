import pytest

from common.models import EpisodeDigest, SeasonDigest, Show, ShowData
from common.progress import ProgressStore
from common.store import ShowStore


@pytest.fixture
def stores(tmp_path):
    """A ShowStore holding one 2-season show ("The Test Show"), plus an empty ProgressStore."""
    sizes = {1: 3, 2: 3}
    data = ShowData(
        show=Show(id=7, name="The Test Show", season_sizes=sizes),
        episodes=[
            EpisodeDigest(season=s, number=n, digest=f"S{s}E{n} happens.")
            for s, size in sizes.items()
            for n in range(1, size + 1)
        ],
        seasons=[
            SeasonDigest(season=s, digest=f"SEASON{s} summary.", episode_count=size)
            for s, size in sizes.items()
        ],
    )
    shows = ShowStore(tmp_path)
    shows.save(data)
    return shows, ProgressStore(tmp_path)
