"""The MCP tools. Plain functions over a ShowStore so they're easy to unit test.

Tool names/descriptions matter: Alexa+ decides when to call them from these strings, and
the hackathon guidance stresses clear, distinct tools. Responses are small dicts; `text` is
what should be spoken.
"""

from __future__ import annotations

from typing import Any, Literal

from common.store import ShowStore
from server.assemble import assemble_recap, previously_on
from server.resolve import resolve_show

NOT_FOUND = "I don't have recaps for that show yet. I can recap: {known}."


def _unknown(store: ShowStore, query: str) -> dict[str, Any]:
    known = ", ".join(sd.show.name for sd in store.all()) or "none yet"
    return {"found": False, "query": query, "text": NOT_FOUND.format(known=known)}


def find_show(store: ShowStore, query: str) -> dict[str, Any]:
    sd = resolve_show(query, store.all())
    if sd is None:
        return _unknown(store, query)
    return {
        "found": True,
        "name": sd.show.name,
        "seasons": {str(k): v for k, v in sorted(sd.show.season_sizes.items())},
    }


def get_recap(
    store: ShowStore,
    show: str,
    to_season: int,
    to_episode: int | None = None,
    from_season: int = 1,
    from_episode: int = 1,
    detail: Literal["brief", "standard"] = "standard",
) -> dict[str, Any]:
    sd = resolve_show(show, store.all())
    if sd is None:
        return _unknown(store, show)
    # No end episode means "through the end of that season".
    end = (to_season, to_episode if to_episode is not None else 10_000)
    try:
        recap = assemble_recap(sd, (from_season, from_episode), end, detail)
    except (ValueError, LookupError) as exc:
        return {"found": True, "text": str(exc)}
    return {"found": True, **recap.model_dump()}


def get_previously_on(
    store: ShowStore, show: str, season: int, episode: int, count: int = 2
) -> dict[str, Any]:
    sd = resolve_show(show, store.all())
    if sd is None:
        return _unknown(store, show)
    recap = previously_on(sd, (season, episode), count)
    return {"found": True, **recap.model_dump()}
