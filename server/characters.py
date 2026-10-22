"""Spoiler-safe "who is this character?".

TVmaze gives the whole cast, but listing it would reveal characters who only show up later.
So a character counts as *introduced* at the first episode whose digest mentions them, and
nothing at or after the user's position is ever read. A character who is never named in a
digest is never listed (a deliberate, conservative miss). The same reply is given for a
character who isn't introduced yet and one that doesn't exist, so asking can't leak either.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import get_close_matches

from common.models import CastMember, EpisodeDigest, Pos, ShowData, fmt_pos

TITLES = {"mr", "mrs", "ms", "miss", "dr", "doctor", "detective", "captain", "agent", "officer"}
SNIPPET_LIMIT = 4  # most recent mentions returned for one character


@dataclass
class Character:
    name: str
    actor: str | None
    first_seen: Pos
    mentions: list[tuple[Pos, str]] = field(default_factory=list)  # (episode, sentence)


def _handles(name: str) -> list[str]:
    """Strings a digest would use for this character: the full name, else the first name."""
    words = [w for w in re.split(r"[\s.]+", name) if w]
    given = [w for w in words if w.lower() not in TITLES]
    handles = [name]
    if len(given) > 1 and len(given[0]) >= 3:
        handles.append(given[0])  # "Teo Marsh" -> "Teo"; surnames are shared too often
    return handles


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _mentions(handles: list[str], sentence: str) -> bool:
    return any(re.search(rf"\b{re.escape(h)}\b", sentence, re.IGNORECASE) for h in handles)


def _introduced(member: CastMember, episodes: list[EpisodeDigest]) -> Character | None:
    handles = _handles(member.character)
    mentions = [(e.pos, s) for e in episodes for s in _sentences(e.digest) if _mentions(handles, s)]
    if not mentions:
        return None
    return Character(member.character, member.actor, mentions[0][0], mentions)


def characters_through(data: ShowData, pos: Pos) -> list[Character]:
    """Characters introduced at or before `pos`, in order of first appearance."""
    episodes = sorted((e for e in data.episodes if e.pos <= pos), key=lambda e: e.pos)
    found = [c for m in data.cast if (c := _introduced(m, episodes)) is not None]
    return sorted(found, key=lambda c: (c.first_seen, c.name))


def find_character(data: ShowData, query: str, pos: Pos) -> Character | None:
    """Match a spoken name ("mara", "Teo Marsh") against characters introduced by `pos`."""
    known = characters_through(data, pos)
    q = query.lower().strip()
    if not q:
        return None
    index: dict[str, Character] = {}
    for c in known:
        for h in [c.name, *_handles(c.name)]:
            index.setdefault(h.lower(), c)
    if q in index:
        return index[q]
    close = get_close_matches(q, list(index), n=1, cutoff=0.75)
    return index[close[0]] if close else None


def speak_list(show: str, chars: list[Character], pos: Pos) -> str:
    if not chars:
        return f"I don't have any characters for {show} through {fmt_pos(pos)} yet."
    names = ", ".join(c.name for c in chars)
    return f"Characters in {show} so far, through {fmt_pos(pos)}: {names}."


def speak_one(show: str, c: Character, pos: Pos) -> str:
    who = f"{c.name}, played by {c.actor}" if c.actor else c.name
    head = f"{who}. First appears in {fmt_pos(c.first_seen)}."
    facts = " ".join(s for _, s in c.mentions[-SNIPPET_LIMIT:])
    return f"{head} So far, through {fmt_pos(pos)}: {facts}"
