import pytest

from web_demo.intent import parse

SHOW = "The Lighthouse Keepers"


@pytest.mark.parametrize(
    "text, tool, args",
    [
        (
            f"I'm on season 2 episode 3 of {SHOW}",
            "catch_me_up",
            {"show": SHOW, "season": 2, "episode": 3},
        ),
        (
            f"I've watched {SHOW} season one episode four",
            "catch_me_up",
            {"show": SHOW, "season": 1, "episode": 4},
        ),
        (
            f"i just finished s2e4 of {SHOW}.",
            "catch_me_up",
            {"show": SHOW, "season": 2, "episode": 4},
        ),
        (
            f"Catch me up on {SHOW}, I'm on season 1 episode 3",
            "catch_me_up",
            {"show": SHOW, "season": 1, "episode": 3},
        ),
        (
            f"Previously on {SHOW} before season 2 episode 1",
            "get_previously_on",
            {"show": SHOW, "season": 2, "episode": 1},
        ),
        (
            f"Recap {SHOW} through season 1",
            "get_recap",
            {"show": SHOW, "to_season": 1},
        ),
        (
            f"recap {SHOW} up to season 2 episode 3",
            "get_recap",
            {"show": SHOW, "to_season": 2, "to_episode": 3},
        ),
        (
            f"recap {SHOW} from season 1 episode 2 to season 2 episode 1",
            "get_recap",
            {
                "show": SHOW,
                "from_season": 1,
                "from_episode": 2,
                "to_season": 2,
                "to_episode": 1,
            },
        ),
        (f"Do you have {SHOW}?", "find_show", {"query": SHOW}),
    ],
)
def test_parses_supported_phrasings(text, tool, args):
    intent = parse(text)
    assert intent is not None, text
    assert intent.tool == tool
    assert intent.args == args


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "hello there",
        "what's the weather",
        "catch me up",  # no show or position: the server remembers nothing
        "previously on",
        f"previously on {SHOW}",  # no position
        f"recap {SHOW}",  # no range
    ],
)
def test_unrecognised_text_returns_none(text):
    assert parse(text) is None
