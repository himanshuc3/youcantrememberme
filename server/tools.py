"""The MCP tools. Plain functions over the stores so they're easy to unit test.

Tool names/descriptions matter: Alexa+ decides when to call them from these strings, and
the hackathon guidance stresses clear, distinct tools. Responses are small dicts; `text` is
what should be spoken.

Two ways to use the service:
* one-off:   get_recap / get_previously_on with an explicit season and episode;
* remembered: save_progress once ("I'm through season 2, episode 4"), then later just
  catch_me_up or get_previously_on with nothing else, across sessions.
"""

from __future__ import annotations

from typing import Any, Literal

from common.models import ShowData, fmt_pos
from common.progress import Progress, ProgressStore
from common.store import ShowStore
from server.assemble import assemble_recap, previously_on
from server.on_demand import OnDemand
from server.resolve import resolve_show

NOT_FOUND = "I don't have recaps for that show yet. I can recap: {known}."


def _unknown(
    store: ShowStore,
    query: str,
    on_demand: OnDemand | None = None,
    user_id: str = "guest",
) -> dict[str, Any]:
    """Reply for a show we have no digests for. With on-demand enabled, also queues it."""
    if on_demand is not None:
        req = on_demand.request(user_id, query)
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


def _pending_for(on_demand: OnDemand | None, show_id: int) -> dict[str, Any] | None:
    """If this show was requested and isn't ready, the spoken "still working on it" reply."""
    req = on_demand.status(show_id) if on_demand is not None else None
    return _requested(req) if req is not None else None


def _ask_where(show_name: str | None = None) -> dict[str, Any]:
    what = f"of {show_name}" if show_name else "of which show"
    return {
        "found": True,
        "needs_progress": True,
        "text": (
            f"I don't know how far you got yet. Which season and episode {what} did you "
            "last watch? Tell me and I'll remember it."
        ),
    }


def _refreshing(
    sd: ShowData,
    pos: tuple[int, int],
    on_demand: OnDemand | None,
    user_id: str,
) -> dict[str, Any] | None:
    """If `pos` is beyond the last episode we have stored (the show may have aired more since
    it was fetched), queue a re-fetch and return the spoken "fetching" reply. None means the
    data covers it, or a refresh wouldn't help, so the caller carries on as usual."""
    if on_demand is None or pos <= max((e.pos for e in sd.episodes), default=(0, 0)):
        return None
    req = on_demand.refresh(user_id, sd.show.id, sd.show.name)
    if req is None:
        return None
    return {**_requested(req), "found": True}


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


def find_show(
    store: ShowStore,
    query: str,
    *,
    on_demand: OnDemand | None = None,
    user_id: str = "guest",
) -> dict[str, Any]:
    sd = resolve_show(query, store.all())
    if sd is None:
        return _unknown(store, query, on_demand, user_id)
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
    *,
    on_demand: OnDemand | None = None,
    user_id: str = "guest",
) -> dict[str, Any]:
    sd = resolve_show(show, store.all())
    if sd is None:
        return _unknown(store, show, on_demand, user_id)
    if (fetching := _refreshing(sd, (to_season, to_episode or 1), on_demand, user_id)) is not None:
        return fetching
    # No end episode means "through the end of that season".
    end = (to_season, to_episode if to_episode is not None else 10_000)
    try:
        recap = assemble_recap(sd, (from_season, from_episode), end, detail)
    except (ValueError, LookupError) as exc:
        return {"found": True, "text": str(exc)}
    return {"found": True, **recap.model_dump()}


def save_progress(
    store: ShowStore,
    progress: ProgressStore,
    user_id: str,
    show: str,
    season: int,
    episode: int,
    *,
    on_demand: OnDemand | None = None,
) -> dict[str, Any]:
    sd = resolve_show(show, store.all())
    if sd is None:
        out = _unknown(store, show, on_demand, user_id)
        if out.get("pending"):
            # Remember the position now; the show only has to exist by the time they ask.
            progress.set(user_id, Progress(show_id=out["show_id"], season=season, episode=episode))
            out["saved"] = True
            out["through"] = fmt_pos((season, episode))
            out["text"] = (
                f"Got it. I'll remember you're through {fmt_pos((season, episode))} of "
                f"{out['show']}. I don't have it yet, but I've started getting it ready, "
                "so ask me to catch you up in a few minutes."
            )
        return out
    if (fetching := _refreshing(sd, (season, episode), on_demand, user_id)) is not None:
        progress.set(user_id, Progress(show_id=sd.show.id, season=season, episode=episode))
        return {**fetching, "saved": True, "through": fmt_pos((season, episode))}
    if (problem := _bad_episode(sd, season, episode)) is not None:
        return {"found": True, "saved": False, "text": problem}
    progress.set(user_id, Progress(show_id=sd.show.id, season=season, episode=episode))
    return {
        "found": True,
        "saved": True,
        "show": sd.show.name,
        "through": fmt_pos((season, episode)),
        "text": (
            f"Got it. I'll remember you're through {fmt_pos((season, episode))} of "
            f"{sd.show.name}. Ask me to catch you up any time."
        ),
    }


def catch_me_up(
    store: ShowStore,
    progress: ProgressStore,
    user_id: str,
    show: str | None = None,
    detail: Literal["brief", "standard"] = "standard",
    *,
    on_demand: OnDemand | None = None,
) -> dict[str, Any]:
    """Recap from the start through the episode the user last said they watched."""
    if show:
        sd = resolve_show(show, store.all())
        if sd is None:
            return _unknown(store, show, on_demand, user_id)
        saved = progress.get(user_id, sd.show.id)
    else:
        saved = progress.latest(user_id)
        sd = store.get(saved.show_id) if saved else None
        if saved and sd is None:  # progress for a show that isn't ready (or is gone)
            if (pending := _pending_for(on_demand, saved.show_id)) is not None:
                return pending
            saved = None
    if saved is None or sd is None:
        return _ask_where(sd.show.name if sd else None)
    if (fetching := _refreshing(sd, saved.pos, on_demand, user_id)) is not None:
        return fetching
    try:
        recap = assemble_recap(sd, (1, 1), saved.pos, detail)
    except (ValueError, LookupError) as exc:
        return {"found": True, "text": str(exc)}
    return {"found": True, "remembered_progress": True, **recap.model_dump()}


def get_previously_on(
    store: ShowStore,
    progress: ProgressStore,
    user_id: str,
    show: str | None = None,
    season: int | None = None,
    episode: int | None = None,
    count: int = 2,
    *,
    on_demand: OnDemand | None = None,
) -> dict[str, Any]:
    """'Previously on' before an episode. With no season/episode, uses remembered progress and
    recaps the last few episodes the user has already watched."""
    if show:
        sd = resolve_show(show, store.all())
        if sd is None:
            return _unknown(store, show, on_demand, user_id)
    else:
        latest = progress.latest(user_id)
        sd = store.get(latest.show_id) if latest else None
        if sd is None:
            if latest and (pending := _pending_for(on_demand, latest.show_id)) is not None:
                return pending
            return _ask_where()
    if season is not None and episode is not None:
        before = (season, episode)  # explicit: recap the episodes before this one
        if (fetching := _refreshing(sd, before, on_demand, user_id)) is not None:
            return fetching
    else:
        saved = progress.get(user_id, sd.show.id)
        if saved is None:
            return _ask_where(sd.show.name)
        before = (saved.season, saved.episode + 1)  # include the last watched episode
        if (fetching := _refreshing(sd, saved.pos, on_demand, user_id)) is not None:
            return fetching
    recap = previously_on(sd, before, count)
    return {"found": True, **recap.model_dump()}
