"""The committed offline demo dataset: loads, and demonstrates spoiler safety."""

from pathlib import Path

import pytest

from common.models import ShowData
from server.assemble import assemble_recap

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo-data"


@pytest.fixture(scope="module")
def show():
    files = sorted((DEMO / "shows").glob("*.json"))
    assert len(files) == 1, "run `python examples/make_demo_data.py`"
    return ShowData.model_validate_json(files[0].read_text(encoding="utf-8"))


def test_demo_show_shape(show):
    assert show.show.name == "The Lighthouse Keepers"
    assert show.show.season_sizes == {1: 5, 2: 4}
    assert len(show.episodes) == 9 and len(show.seasons) == 2


def test_recap_before_the_twist_never_mentions_it(show):
    # The father reveal happens in S1E5. Anything through S1E4 must not hint at it.
    for end in [(1, 1), (1, 2), (1, 3), (1, 4)]:
        text = assemble_recap(show, (1, 1), end).text.lower()
        assert "father" not in text, end
        assert "recording" not in text, end


def test_recap_through_the_end_of_season_one_does_include_it(show):
    assert "father" in assemble_recap(show, (1, 1), (1, 5)).text.lower()


def test_demo_data_is_in_sync_with_the_generator(show):
    import sys

    sys.path.insert(0, str(DEMO.parent))
    from make_demo_data import build

    assert build().model_dump() == show.model_dump()
