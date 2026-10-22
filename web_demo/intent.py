"""Turn a typed sentence into an MCP tool call. A deliberately small rule-based parser.

On a real device Alexa+ does the language understanding and picks the tool itself. This
parser exists only so the web demo can mimic that without an LLM or an Echo. It handles a
handful of phrasings (see tests/test_intent.py) and says so when it doesn't understand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

WORDS = {
    w: i
    for i, w in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
            "twenty",
        ]
    )
}
NUM = r"(\d+|" + "|".join(w for w in WORDS if w != "zero") + r")"
SEASON_EP = re.compile(
    rf"\b(?:season|s)\s*{NUM}[\s,]*(?:and\s+)?(?:episode|ep|e)\s*{NUM}\b", re.IGNORECASE
)
SEASON_ONLY = re.compile(rf"\b(?:season|s)\s*{NUM}\b", re.IGNORECASE)
TRAILING = re.compile(r"[\s.!?,]+$")

HELP = (
    "I didn't understand that. Try: \"Catch me up on The Lighthouse Keepers, I'm on season 2 "
    'episode 3", "previously on The Lighthouse Keepers before season 2 episode 1", or '
    '"recap The Lighthouse Keepers through season 1". The server remembers nothing between '
    "messages, so always say the show and where you are."
)


@dataclass
class Intent:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


def _n(token: str) -> int:
    t = token.lower()
    return int(t) if t.isdigit() else WORDS[t]


def _clean_show(text: str) -> str | None:
    text = TRAILING.sub("", text.strip())
    text = re.sub(r"^(?:of|on|for|in|from|about|with)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:please|now|again)$", "", text, flags=re.IGNORECASE)
    return text.strip() or None


def parse(text: str) -> Intent | None:
    t = text.strip()
    low = t.lower()
    if not t:
        return None
    se = [(_n(m.group(1)), _n(m.group(2)), m.span()) for m in SEASON_EP.finditer(t)]

    def without_positions() -> str:
        rest = t
        for _, _, (a, b) in reversed(se):
            rest = rest[:a] + " " + rest[b:]
        return rest

    # "previously on <show> before season X episode Y": all three are required
    if "previously" in low:
        rest = re.sub(r"(?i)^.*?previously(?: on)?", "", without_positions())
        rest = re.sub(r"(?i)\b(?:before|until|up to|leading up to)\b.*$", "", rest)
        show = _clean_show(rest)
        if not show or not se:
            return None
        return Intent(
            "get_previously_on", {"show": show, "season": se[-1][0], "episode": se[-1][1]}
        )

    # "catch me up on X, I'm on season 2 episode 4" / "I'm on season 2 episode 4 of X"
    if se and (
        re.search(r"(?i)\bcatch(?:ing)?\s+(?:me\s+)?up\b", t)
        or re.search(
            r"(?i)\b(?:i'?m|i am|i'?ve|i have|we'?re|we are|just|finished|watched|stopped)\b", t
        )
    ):
        rest = without_positions()
        rest = re.sub(r"(?i)\bcatch(?:ing)?\s+(?:me\s+)?up\b", " ", rest)
        rest = re.sub(
            r"(?i)\b(?:i'?m|i am|i'?ve|i have|we'?re|we are|just|finished|watched|stopped|"
            r"on|at|through|up to|done with|caught up (?:to|through))\b",
            " ",
            rest,
        )
        rest = re.sub(r"(?i)^\s*(?:i|we)\b", " ", rest)  # "i just finished ..." leaves a bare "i"
        rest = re.sub(r"\s+", " ", rest)
        show = _clean_show(rest)
        if not show:
            return None
        return Intent("catch_me_up", {"show": show, "season": se[0][0], "episode": se[0][1]})

    # "recap X through season 2 [episode 3] [from season 1 episode 2]"
    if re.search(r"(?i)\b(?:recap|summary|summarize|summarise|what happened)\b", t):
        end = se[-1][:2] if se else None
        start = se[0][:2] if len(se) > 1 else (1, 1)
        if end is None:
            only = SEASON_ONLY.search(t)
            if only is None:
                return None
            end = (_n(only.group(1)), None)
        rest = SEASON_ONLY.sub(" ", without_positions())
        rest = re.sub(
            r"(?i)^.*?\b(?:recap|summary|summarize|summarise|what happened(?: in)?)\b",
            "",
            rest,
            count=1,
        )
        # Cut at the first time connector. A bare "to" counts only at the very end, so
        # titles like "Back to the Future" survive.
        rest = re.split(r"(?i)\b(?:through|thru|up to|until|from)\b|\bto\s*$", rest)[0]
        show = _clean_show(re.sub(r"\s+", " ", rest))
        args = {"to_season": end[0]}
        if end[1] is not None:
            args["to_episode"] = end[1]
        if len(se) > 1:
            args["from_season"], args["from_episode"] = start
        if show:
            args["show"] = show
        else:
            return None
        return Intent("get_recap", args)

    if m := re.search(r"(?i)\b(?:do you have|have you got|is|find|looking for)\s+(.+)$", t):
        show = _clean_show(re.sub(r"(?i)\bavailable\b", "", m.group(1)))
        if show:
            return Intent("find_show", {"query": show})
    return None
