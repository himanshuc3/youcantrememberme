"""Turn source text into spoiler-safe digests.

Two modes:

* baseline: no LLM. The episode digest is TVmaze's own blurb; the season digest is the first
  sentence of each episode. Good enough to exercise the whole system end to end.
* llm: Claude on Bedrock (pipeline/llm.py). Spoiler safety is enforced by construction:
    - the episode prompt contains ONLY that episode's source text plus the digests of the
      few episodes before it (for names/continuity), never anything later;
    - the season prompt contains ONLY that season's episode digests;
    - the model is told to use nothing from its own memory of the show, because training
      data may include later events (spoilers) and hallucinated "facts".
"""

from __future__ import annotations

import json
import re

from common.models import Episode, EpisodeDigest, SeasonDigest
from pipeline.llm import LLM

CONTEXT_EPISODES = 3  # how many previous digests the episode prompt may see

# --------------------------------------------------------------------------- baseline


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


# --------------------------------------------------------------------------- llm

SPOILER_RULES = """\
You write short "story so far" notes for a spoken TV recap service. People use it to catch \
up on a show they paused, and they must never be spoiled.

Hard rules:
- Use ONLY the text provided in this message. Do not add any detail from your own memory of \
the show: your memory may include events that happen later, and may be wrong.
- Never mention, hint at, or foreshadow anything that is not in the provided text.
- Do not use episode titles, "finale", "premiere", "cliffhanger", "twist", or other words \
that hint at what is coming.
- Write plain spoken English: no markdown, no lists, no parentheses, no quotation marks.
- Reply with a single JSON object and nothing else.
"""

EPISODE_SYSTEM = (
    SPOILER_RULES
    + """
For one episode, write a digest of at most two sentences (about 40 words) saying what \
happens, in the present tense, naming characters as the source does. Also set \
"title_is_spoiler" to true if the episode title given reveals a plot event (for example a \
death, betrayal or reveal), otherwise false.

JSON shape: {"digest": "...", "title_is_spoiler": false}
"""
)

SEASON_SYSTEM = (
    SPOILER_RULES
    + """
You are given the digests of every episode in one season, in order. Write a season digest \
of at most four sentences (about 80 words) covering the main storyline of the season, using \
only those digests.

JSON shape: {"digest": "..."}
"""
)


class DigestError(RuntimeError):
    pass


def _parse_json(text: str) -> dict:
    """Pull one JSON object out of a reply, tolerating code fences or stray prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise TypeError("JSON reply is not an object")
    return obj


def _ask(llm: LLM, system: str, user: str, attempts: int = 2) -> dict:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            obj = _parse_json(llm.complete(system, user))
            if not str(obj.get("digest", "")).strip():
                raise ValueError("empty digest")
            return obj
        except (ValueError, TypeError) as exc:  # JSONDecodeError is a ValueError
            last = exc
    raise DigestError(f"could not get a valid digest: {last}")


def episode_prompt(show_name: str, ep: Episode, prior: list[EpisodeDigest]) -> str:
    previous = "\n".join(
        f"- Season {d.season}, episode {d.number}: {d.digest}" for d in prior[-CONTEXT_EPISODES:]
    )
    return (
        f"Show: {show_name}\n"
        f"This episode: season {ep.season}, episode {ep.number}, titled {ep.title!r}\n\n"
        f"Digests of the episodes just before it (for continuity only):\n"
        f"{previous or '(none: this is the first episode)'}\n\n"
        f"Source text for this episode:\n{ep.extra_text or ep.summary}\n"
    )


def season_prompt(show_name: str, season: int, digests: list[EpisodeDigest]) -> str:
    lines = "\n".join(f"- Episode {d.number}: {d.digest}" for d in digests)
    return f"Show: {show_name}\nSeason {season} episode digests:\n{lines}\n"


def llm_episode_digest(
    llm: LLM, show_name: str, ep: Episode, prior: list[EpisodeDigest]
) -> EpisodeDigest | None:
    if not (ep.extra_text or ep.summary):
        return None  # nothing to summarize; never let the model fill the gap from memory
    obj = _ask(llm, EPISODE_SYSTEM, episode_prompt(show_name, ep, prior))
    return EpisodeDigest(
        season=ep.season,
        number=ep.number,
        digest=str(obj["digest"]).strip(),
        title=ep.title,
        title_is_spoiler=bool(obj.get("title_is_spoiler", False)),
    )


def llm_season_digest(
    llm: LLM, show_name: str, season: int, digests: list[EpisodeDigest]
) -> SeasonDigest:
    ordered = sorted(digests, key=lambda d: d.number)
    obj = _ask(llm, SEASON_SYSTEM, season_prompt(show_name, season, ordered))
    return SeasonDigest(
        season=season, digest=str(obj["digest"]).strip(), episode_count=len(ordered)
    )
