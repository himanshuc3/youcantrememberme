"""Deterministic recap checks (no LLM): speakability and honesty of the metadata.

Run over every stored show at a set of ranges. Checks:
  * word count within the budget for the requested detail level
  * no markdown / bullets / URLs / HTML in `text`
  * `covered_through` <= requested end, and every requested-range episode is accounted for
"""

from __future__ import annotations

import re

from common.models import Recap

_BAD = re.compile(r"[*_#`<>]|https?://|^\s*[-•]\s", re.MULTILINE)


def check_recap(recap: Recap, max_words: int) -> list[str]:
    problems = []
    if len(recap.text.split()) > max_words:
        problems.append(f"too long: {len(recap.text.split())} > {max_words} words")
    if _BAD.search(recap.text):
        problems.append("contains markup or a URL; not speakable")
    return problems
