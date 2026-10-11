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
from server.resolve import resolve_show

NOT_FOUND = "I don't have recaps for that show yet. I can recap: {known}."


def _unknown(store: ShowStore, query: str) -> dict[str, Any]:
    known = ", ".join(sd.show.name for sd in store.all()) or "none yet"
    return {"found": False, "query": query, "text": NOT_FOUND.format(known=known)}


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


def save_progress(
    store: ShowStore,
    progress: ProgressStore,
    user_id: str,
    show: str,
    season: int,
    episode: int,
) -> dict[str, Any]:
    sd = resolve_show(show, store.all())
    if sd is None:
        return _unknown(store, show)
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
) -> dict[str, Any]:
    """Recap from the start through the episode the user last said they watched."""
    if show:
        sd = resolve_show(show, store.all())
        if sd is None:
            return _unknown(store, show)
        saved = progress.get(user_id, sd.show.id)
    else:
        saved = progress.latest(user_id)
        sd = store.get(saved.show_id) if saved else None
        if saved and sd is None:  # progress for a show we no longer have
            saved = None
    if saved is None or sd is None:
        return _ask_where(sd.show.name if sd else None)
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
) -> dict[str, Any]:
    """'Previously on' before an episode. With no season/episode, uses remembered progress and
    recaps the last few episodes the user has already watched."""
    if show:
        sd = resolve_show(show, store.all())
        if sd is None:
            return _unknown(store, show)
    else:
        latest = progress.latest(user_id)
        sd = store.get(latest.show_id) if latest else None
        if sd is None:
            return _ask_where()
    if season is not None and episode is not None:
        before = (season, episode)  # explicit: recap the episodes before this one
    else:
        saved = progress.get(user_id, sd.show.id)
        if saved is None:
            return _ask_where(sd.show.name)
        before = (saved.season, saved.episode + 1)  # include the last watched episode
    recap = previously_on(sd, before, count)
    return {"found": True, **recap.model_dump()}
