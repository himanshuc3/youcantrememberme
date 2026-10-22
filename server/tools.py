"""The MCP tools. Plain functions over the stores so they're easy to unit test.

Tool names/descriptions matter: Alexa+ decides when to call them from these strings, and
the hackathon guidance stresses clear, distinct tools. Responses are small dicts; `text` is
what should be spoken.

The service is stateless: it stores no per-user data. The caller (Alexa+) supplies the
show and the episode the user has reached on every call, so nothing identifies a user.
"""

from __future__ import annotations

from typing import Any, Literal

from common.models import ShowData, fmt_pos
from common.store import ShowStore
from server import characters as chars
from server.assemble import assemble_recap, previously_on
from server.on_demand import OnDemand
from server.resolve import resolve_show

NOT_FOUND = "I don't have recaps for that show yet. I can recap: {known}."


def _unknown(store: ShowStore, query: str, on_demand: OnDemand | None = None) -> dict[str, Any]:
    """Reply for a show we have no digests for. With on-demand enabled, also queues it."""
    if on_demand is not None:
        req = on_demand.request(query)
        if req.kind != "unknown":
            return _requested(req, query)
    known = ", ".join(sd.show.name for sd in store.all()) or "none yet"
    return {"found": False, "query": query, "text": NOT_FOUND.format(known=known)}


def _requested(req, query: str = "") -> dict[str, Any]:
    return {
        "found": False,
        "query": query or req.name,
        "pending": req.kind == "pending",
        "status": req.status,
        "show": req.name,
        "show_id": req.show_id,
        "text": req.text,
    }


def _refreshing(
    sd: ShowData, pos: tuple[int, int], on_demand: OnDemand | None
) -> dict[str, Any] | None:
    """If `pos` is beyond the last episode we have stored (the show may have aired more since
    it was fetched), queue a re-fetch and return the spoken "fetching" reply. None means the
    data covers it, or a refresh wouldn't help, so the caller carries on as usual."""
    if on_demand is None or pos <= max((e.pos for e in sd.episodes), default=(0, 0)):
        return None
    req = on_demand.refresh(sd.show.id, sd.show.name)
    if req is None:
        return None
    return {**_requested(req), "found": True}


REWRITE = (
    "The user asked for this recap in a particular style. Retell `text` in that style as a short "
    "spoken answer. Use ONLY the events and characters in `text`; if they asked to swap in "
    "characters from another show or story, only rename them and keep every event identical. "
    "Never add, hint at or invent plot beyond `text`, and say nothing about episodes after "
    "`covered_through`."
)


def _styled(out: dict[str, Any], style: str | None) -> dict[str, Any]:
    """The server has no LLM, so a requested style is handed to the caller's LLM as instructions."""
    if (
        style
        and style.strip()
        and out.get("found")
        and not out.get("pending")
        and "covered_through" in out
    ):
        out["rewrite"] = {"style": style.strip(), "instructions": REWRITE}
    return out


def _bad_episode(sd: ShowData, season: int, episode: int) -> str | None:
    """Return a spoken error if (season, episode) doesn't exist for this show."""
    sizes = sd.show.season_sizes
    if not sizes:
        return None
    if season not in sizes:
        return f"{sd.show.name} has seasons {min(sizes)} to {max(sizes)}, not season {season}."
    if not 1 <= episode <= sizes[season]:
        return f"Season {season} of {sd.show.name} has {sizes[season]} episodes."
    return None


def find_show(store: ShowStore, query: str, *, on_demand: OnDemand | None = None) -> dict[str, Any]:
    sd = resolve_show(query, store.all())
    if sd is None:
        return _unknown(store, query, on_demand)
    sizes = sorted(sd.show.season_sizes.items())
    detail = ", ".join(f"season {s} has {n} episodes" for s, n in sizes)
    return {
        "found": True,
        "name": sd.show.name,
        "seasons": {str(k): v for k, v in sizes},
        "text": f"Yes, I have {sd.show.name}: {detail}."
        if sizes
        else f"Yes, I have {sd.show.name}.",
    }


def get_recap(
    store: ShowStore,
    show: str,
    to_season: int,
    to_episode: int | None = None,
    from_season: int = 1,
    from_episode: int = 1,
    detail: Literal["brief", "standard"] = "standard",
    style: str | None = None,
    *,
    on_demand: OnDemand | None = None,
) -> dict[str, Any]:
    sd = resolve_show(show, store.all())
    if sd is None:
        return _unknown(store, show, on_demand)
    if (fetching := _refreshing(sd, (to_season, to_episode or 1), on_demand)) is not None:
        return fetching
    # No end episode means "through the end of that season".
    end = (to_season, to_episode if to_episode is not None else 10_000)
    try:
        recap = assemble_recap(sd, (from_season, from_episode), end, detail)
    except (ValueError, LookupError) as exc:
        return {"found": True, "text": str(exc)}
    return _styled({"found": True, **recap.model_dump()}, style)


def catch_me_up(
    store: ShowStore,
    show: str,
    season: int,
    episode: int,
    detail: Literal["brief", "standard"] = "standard",
    style: str | None = None,
    *,
    on_demand: OnDemand | None = None,
) -> dict[str, Any]:
    """Recap from the very start through the given episode (the last one the user watched)."""
    sd = resolve_show(show, store.all())
    if sd is None:
        return _unknown(store, show, on_demand)
    if (fetching := _refreshing(sd, (season, episode), on_demand)) is not None:
        return fetching
    if (problem := _bad_episode(sd, season, episode)) is not None:
        return {"found": True, "text": problem}
    try:
        recap = assemble_recap(sd, (1, 1), (season, episode), detail)
    except (ValueError, LookupError) as exc:
        return {"found": True, "text": str(exc)}
    return _styled({"found": True, **recap.model_dump()}, style)


def get_previously_on(
    store: ShowStore,
    show: str,
    season: int,
    episode: int,
    count: int = 2,
    style: str | None = None,
    *,
    on_demand: OnDemand | None = None,
) -> dict[str, Any]:
    """'Previously on' for the `count` episodes immediately before (season, episode), which
    is the episode the user is about to watch. Crosses season boundaries."""
    sd = resolve_show(show, store.all())
    if sd is None:
        return _unknown(store, show, on_demand)
    if (fetching := _refreshing(sd, (season, episode), on_demand)) is not None:
        return fetching
    if (problem := _bad_episode(sd, season, episode)) is not None:
        return {"found": True, "text": problem}
    recap = previously_on(sd, (season, episode), count)
    return _styled({"found": True, **recap.model_dump()}, style)


def get_characters(
    store: ShowStore,
    show: str,
    season: int,
    episode: int,
    character: str | None = None,
    *,
    on_demand: OnDemand | None = None,
) -> dict[str, Any]:
    """Who's who through (season, episode), or what is known about one character so far."""
    sd = resolve_show(show, store.all())
    if sd is None:
        return _unknown(store, show, on_demand)
    if (fetching := _refreshing(sd, (season, episode), on_demand)) is not None:
        return fetching
    if (problem := _bad_episode(sd, season, episode)) is not None:
        return {"found": True, "text": problem}
    if not sd.cast:  # stored before cast was fetched: re-fetch in the background if we can
        req = on_demand.refresh(sd.show.id, sd.show.name) if on_demand is not None else None
        text = (
            req.text
            if req is not None
            else f"I don't have character details for {sd.show.name} yet."
        )
        return {"found": True, "show": sd.show.name, "pending": req is not None, "text": text}
    pos = (season, episode)
    if character:
        match = chars.find_character(sd, character, pos)
        if match is None:  # same answer for "not introduced yet" and "no such character"
            return {
                "found": True,
                "show": sd.show.name,
                "text": f"I don't know a character called {character} in {sd.show.name} "
                f"through {fmt_pos(pos)}.",
            }
        return {
            "found": True,
            "show": sd.show.name,
            "character": match.name,
            "actor": match.actor,
            "first_seen": fmt_pos(match.first_seen),
            "known_so_far": [s for _, s in match.mentions[-chars.SNIPPET_LIMIT :]],
            "covered_through": fmt_pos(pos),
            "text": chars.speak_one(sd.show.name, match, pos),
        }
    listed = chars.characters_through(sd, pos)
    return {
        "found": True,
        "show": sd.show.name,
        "characters": [
            {"name": c.name, "actor": c.actor, "first_seen": fmt_pos(c.first_seen)} for c in listed
        ],
        "covered_through": fmt_pos(pos),
        "text": chars.speak_list(sd.show.name, listed, pos),
    }
