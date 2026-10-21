from common.models import Show, ShowData
from server.resolve import normalize, resolve_show


def shows(*names):
    return [ShowData(show=Show(id=i, name=n)) for i, n in enumerate(names, 1)]


def test_normalize():
    assert normalize("The Bear") == "bear"
    assert normalize("  Breaking Bad TV show ") == "breaking bad"
    assert normalize("Marvel's Daredevil!") == "marvels daredevil"


def test_resolve_exact_and_loose():
    s = shows("The Bear", "Breaking Bad", "Severance")
    assert resolve_show("the bear", s).show.name == "The Bear"
    assert resolve_show("bear show", s).show.name == "The Bear"
    assert resolve_show("breaking bed", s).show.name == "Breaking Bad"  # speech-to-text slip


def test_resolve_unknown():
    assert resolve_show("Totally Unknown Series", shows("The Bear")) is None
    assert resolve_show("", shows("The Bear")) is None


def test_resolve_typos_and_partial_titles():
    s = shows("The Office", "The Lighthouse Keepers", "Game of Thrones", "The Bear")
    assert resolve_show("the offise", s).show.name == "The Office"
    assert resolve_show("lighthouse", s).show.name == "The Lighthouse Keepers"
    assert resolve_show("lighthouse keper", s).show.name == "The Lighthouse Keepers"
    assert resolve_show("thrones", s).show.name == "Game of Thrones"
    assert resolve_show("the", s) is None  # nothing distinctive to match on


def test_resolve_ambiguous_partial_title_is_not_guessed():
    s = shows("Breaking Bad", "Breaking Point")
    assert resolve_show("breaking", s) is None
