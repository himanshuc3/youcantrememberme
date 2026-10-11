"""Build season digests from episode digests.

Invariant: a season digest is built only from that season's own episode digests, and only
when the season is complete (every episode has a digest). `episode_count` is recorded so the
server can refuse to use it for a partially-covered range.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from common.models import EpisodeDigest, SeasonDigest, Show


def build_season_digests(
    show: Show,
    episode_digests: list[EpisodeDigest],
    make: Callable[[int, list[EpisodeDigest]], SeasonDigest],
) -> list[SeasonDigest]:
    by_season: dict[int, list[EpisodeDigest]] = defaultdict(list)
    for d in episode_digests:
        by_season[d.season].append(d)
    out = []
    for season, digests in sorted(by_season.items()):
        if len(digests) == show.season_sizes.get(season):  # complete seasons only
            out.append(make(season, digests))
    return out
