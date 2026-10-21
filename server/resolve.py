"""Resolve a spoken show name ("the bear", "breaking bad show") to a stored show.

Alexa passes whatever the user said, so matching is forgiving: case, punctuation and a
leading "the" are ignored, then we fall back to fuzzy matching, then to partial titles
("lighthouse" -> "The Lighthouse Keepers") when exactly one show fits.
"""

from __future__ import annotations

import re
from difflib import get_close_matches

from common.models import ShowData


def normalize(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9 ]+", "", name)
    name = re.sub(r"^(the|a|an) ", "", name)
    name = re.sub(r"\s+(tv )?(show|series)$", "", name)
    return re.sub(r"\s+", " ", name).strip()


def resolve_show(query: str, shows: list[ShowData], cutoff: float = 0.75) -> ShowData | None:
    q = normalize(query)
    if not q:
        return None
    index: dict[str, ShowData] = {}
    for sd in shows:
        for n in [sd.show.name, *sd.show.aliases]:
            index.setdefault(normalize(n), sd)
    if q in index:
        return index[q]
    candidates = _partial(q, index)
    if len(candidates) > 1:
        return None  # "breaking" fits two shows: ask rather than guess
    if candidates:
        return candidates[0]
    close = get_close_matches(q, list(index), n=1, cutoff=cutoff)
    return index[close[0]] if close else None


def _partial(q: str, index: dict[str, ShowData]) -> list[ShowData]:
    """Shows where every word the user said loosely matches a word of the title."""
    words = q.split()
    hits = {
        id(sd): sd
        for name, sd in index.items()
        if all(get_close_matches(w, name.split(), n=1, cutoff=0.8) for w in words)
    }
    return list(hits.values())
