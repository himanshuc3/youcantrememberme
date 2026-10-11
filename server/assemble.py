"""Spoiler-safe recap assembly. This is the core of the product.

Rules (each one is covered by tests/test_assemble.py):

1. Only episodes inside [start, end] are ever used.
2. A season digest is used only if the range covers the *whole* season, i.e. the number of
   in-range episode digests equals the digest's `episode_count`. A season digest for a
   partially-covered season may mention events past the requested end, so it is never used.
3. If the result is too long to say aloud, shrink it (first sentences only), then drop the
   *oldest* segments. Never drop the newest, and report honestly via `starts_at`/`truncated`.
4. `covered_through` is the last episode actually included, never later than requested.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import groupby
from typing import Literal

from common.models import EpisodeDigest, Pos, Recap, ShowData, fmt_pos

Detail = Literal["brief", "standard"]

# Rough spoken length: ~150 words per minute.
WORD_BUDGET: dict[str, int] = {"brief": 90, "standard": 220}

NO_PRIOR_EPISODES = "That's the first episode, so there's nothing to catch up on yet."


@dataclass
class _Segment:
    label: str
    text: str
    kind: Literal["season", "episode"]
    start: Pos
    end: Pos


def _words(text: str) -> int:
    return len(text.split())


def _first_sentence(text: str) -> str:
    text = text.strip()
    m = re.match(r"(.+?[.!?])(\s|$)", text, flags=re.DOTALL)
    return m.group(1) if m else text


def _segments(data: ShowData, start: Pos, end: Pos) -> list[_Segment]:
    in_range = sorted((e for e in data.episodes if start <= e.pos <= end), key=lambda e: e.pos)
    season_digests = {s.season: s for s in data.seasons}
    segs: list[_Segment] = []
    for season, group_iter in groupby(in_range, key=lambda e: e.season):
        group = list(group_iter)
        sd = season_digests.get(season)
        if sd is not None and sd.episode_count == len(group):
            # Whole season is inside the range (rule 2).
            segs.append(
                _Segment(f"Season {season}", sd.digest, "season", group[0].pos, group[-1].pos)
            )
        else:
            for e in group:
                segs.append(
                    _Segment(
                        f"Season {e.season}, episode {e.number}",
                        e.digest,
                        "episode",
                        e.pos,
                        e.pos,
                    )
                )
    return segs


def _render(segs: list[_Segment]) -> str:
    return " ".join(f"{s.label}. {s.text}" for s in segs)


def _fit(segs: list[_Segment], budget: int) -> tuple[list[_Segment], bool]:
    """Shrink to the word budget (rule 3). Returns (segments, truncated)."""
    if _words(_render(segs)) <= budget:
        return segs, False
    # Step 1: episodes keep only their first sentence.
    segs = [
        _Segment(s.label, _first_sentence(s.text), s.kind, s.start, s.end)
        if s.kind == "episode"
        else s
        for s in segs
    ]
    truncated = False
    # Step 2: drop the oldest segments, always keeping at least the newest.
    while len(segs) > 1 and _words(_render(segs)) > budget:
        segs = segs[1:]
        truncated = True
    return segs, truncated


def assemble_recap(data: ShowData, start: Pos, end: Pos, detail: Detail = "standard") -> Recap:
    if start > end:
        raise ValueError("The start of the range is after its end.")
    segs = _segments(data, start, end)
    if not segs:
        raise LookupError(
            f"I don't have {data.show.name} recaps between {fmt_pos(start)} and {fmt_pos(end)}."
        )
    first_pos, last_pos = segs[0].start, segs[-1].end
    segs, truncated = _fit(segs, WORD_BUDGET[detail])
    return Recap(
        show=data.show.name,
        text=_render(segs),
        starts_at=fmt_pos(segs[0].start if truncated else first_pos),
        covered_through=fmt_pos(last_pos),
        truncated=truncated,
        attribution=data.attribution,
    )


def previously_on(data: ShowData, before: Pos, count: int = 2) -> Recap:
    """Recap of the `count` episodes immediately before `before` (which is NOT included)."""
    prior: list[EpisodeDigest] = sorted(
        (e for e in data.episodes if e.pos < before), key=lambda e: e.pos
    )[-max(1, count) :]
    if not prior:
        return Recap(
            show=data.show.name,
            text=NO_PRIOR_EPISODES,
            starts_at=fmt_pos(before),
            covered_through=fmt_pos(before),
            attribution=data.attribution,
        )
    segs = [
        _Segment(f"Season {e.season}, episode {e.number}", e.digest, "episode", e.pos, e.pos)
        for e in prior
    ]
    segs, truncated = _fit(segs, WORD_BUDGET["standard"])
    return Recap(
        show=data.show.name,
        text=_render(segs),
        starts_at=fmt_pos(segs[0].start),
        covered_through=fmt_pos(segs[-1].end),
        truncated=truncated,
        attribution=data.attribution,
    )
