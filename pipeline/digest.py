"""Turn source text into spoiler-safe digests.

Two modes:

* baseline: no LLM. The episode digest is TVmaze's own blurb; the season digest is the first
  sentence of each episode. Good enough to exercise the whole system end to end.
* llm: STUB until the provider is chosen (Claude API vs Bedrock). Planned design:
    - episode digest prompt sees ONLY that episode's source text + the previous episodes'
      digests (for continuity), so later events can't leak by construction;
    - output is JSON: {"digest": "<=2 spoken sentences>", "title_is_spoiler": bool};
    - season digest prompt sees ONLY that season's episode digests;
    - everything is cached on disk keyed by a hash of (prompt, input) so reruns are free.
"""

from __future__ import annotations

import re

from common.models import Episode, EpisodeDigest, SeasonDigest


def _first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip(), flags=re.DOTALL)
    return m.group(1) if m else text.strip()


def baseline_episode_digest(ep: Episode) -> EpisodeDigest | None:
    text = ep.extra_text or ep.summary
    if not text:
        return None  # no source text: better to have a gap than invent something
    return EpisodeDigest(season=ep.season, number=ep.number, digest=text, title=ep.title)


def baseline_season_digest(season: int, digests: list[EpisodeDigest]) -> SeasonDigest:
    body = " ".join(_first_sentence(d.digest) for d in sorted(digests, key=lambda d: d.number))
    return SeasonDigest(season=season, digest=body, episode_count=len(digests))


def llm_episode_digest(ep: Episode, prior: list[EpisodeDigest]) -> EpisodeDigest:
    raise NotImplementedError("LLM provider not chosen yet")


def llm_season_digest(season: int, digests: list[EpisodeDigest]) -> SeasonDigest:
    raise NotImplementedError("LLM provider not chosen yet")
