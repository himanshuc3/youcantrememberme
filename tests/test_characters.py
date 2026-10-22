"""Who's who is spoiler-safe by construction, and a style request becomes rewrite instructions."""

import pytest

from common.models import CastMember, EpisodeDigest, Show, ShowData
from server import tools
from server.characters import characters_through, find_character

DIGESTS = {
    (1, 1): "Mara Voss arrives at the lighthouse. The keeper is missing.",
    (1, 2): "A storm traps Mara and the boat captain, Teo Marsh. Teo finds a coat.",
    (1, 3): "Dr. Ines Calder visits the rock. She asks about the coat.",
    (2, 1): "Teo reveals that Wren Okafor is the missing keeper's daughter.",
}


@pytest.fixture
def data():
    return ShowData(
        show=Show(id=1, name="The Rock", season_sizes={1: 3, 2: 1}),
        cast=[
            CastMember(character="Mara Voss", actor="A. Actor"),
            CastMember(character="Teo Marsh", actor="B. Actor"),
            CastMember(character="Dr. Ines Calder", actor="C. Actor"),
            CastMember(character="Wren Okafor", actor="D. Actor"),
            CastMember(character="Never Named", actor="E. Actor"),
        ],
        episodes=[EpisodeDigest(season=s, number=n, digest=d) for (s, n), d in DIGESTS.items()],
    )


@pytest.fixture
def store(shows, data):
    shows.save(data)
    return shows


def names(data, pos):
    return [c.name for c in characters_through(data, pos)]


def test_a_character_appears_when_first_named_and_not_before(data):
    assert names(data, (1, 1)) == ["Mara Voss"]
    assert names(data, (1, 2)) == ["Mara Voss", "Teo Marsh"]
    assert names(data, (1, 3)) == ["Mara Voss", "Teo Marsh", "Dr. Ines Calder"]
    assert "Wren Okafor" not in names(data, (1, 3))  # introduced in season 2
    assert "Never Named" not in names(data, (2, 1))  # never named in any digest


def test_first_name_matches_and_titles_are_skipped(data):
    assert find_character(data, "mara", (1, 3)).name == "Mara Voss"
    assert find_character(data, "Teo", (1, 3)).first_seen == (1, 2)
    assert find_character(data, "ines", (1, 3)).name == "Dr. Ines Calder"  # not "Dr"


def test_unknown_and_not_yet_introduced_get_the_same_answer(store):
    later = tools.get_characters(store, "The Rock", 1, 3, "Wren Okafor")
    never = tools.get_characters(store, "The Rock", 1, 3, "Nobody Atall")
    assert later["text"].replace("Wren Okafor", "X") == never["text"].replace("Nobody Atall", "X")
    assert "Wren" not in later["text"].replace("Wren Okafor", "")


def test_one_character_only_uses_digests_up_to_the_position(store):
    early = tools.get_characters(store, "The Rock", 1, 2, "Teo")
    assert early["character"] == "Teo Marsh" and early["first_seen"] == "season 1, episode 2"
    assert all("daughter" not in s for s in early["known_so_far"])
    assert "daughter" not in early["text"]
    late = tools.get_characters(store, "The Rock", 2, 1, "Teo")
    assert any("daughter" in s for s in late["known_so_far"])


def test_whos_who_lists_only_whats_introduced(store):
    out = tools.get_characters(store, "The Rock", 1, 1)
    assert [c["name"] for c in out["characters"]] == ["Mara Voss"]
    assert "Teo" not in out["text"]


def test_show_without_cast_says_so(shows):
    shows.save(
        ShowData(
            show=Show(id=2, name="No Cast", season_sizes={1: 1}),
            episodes=[EpisodeDigest(season=1, number=1, digest="Something.")],
        )
    )
    out = tools.get_characters(shows, "No Cast", 1, 1)
    assert "character details" in out["text"] and "characters" not in out


def test_style_adds_rewrite_instructions_without_changing_the_text(shows):
    plain = tools.catch_me_up(shows, "The Test Show", 1, 2)
    styled = tools.catch_me_up(shows, "The Test Show", 1, 2, style="like a noir detective")
    assert "rewrite" not in plain
    assert styled["text"] == plain["text"]
    assert styled["rewrite"]["style"] == "like a noir detective"
    assert "covered_through" in styled["rewrite"]["instructions"]
    for fn, args in [
        (tools.get_recap, ("The Test Show", 1, 2)),
        (tools.get_previously_on, ("The Test Show", 1, 3)),
    ]:
        assert fn(shows, *args, style="in pirate speak")["rewrite"]["style"] == "in pirate speak"


def test_style_is_ignored_when_there_is_no_recap(shows):
    out = tools.catch_me_up(shows, "Zzz Unknown", 1, 1, style="noir")
    assert "rewrite" not in out
    assert "rewrite" not in tools.catch_me_up(shows, "The Test Show", 1, 2, style="   ")
