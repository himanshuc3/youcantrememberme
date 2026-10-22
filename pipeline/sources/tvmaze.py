"""TVmaze client (https://www.tvmaze.com/api). Free, no key, CC BY-SA 4.0: credit TVmaze.

Rate limit is >= 20 calls / 10 s per IP; we back off on HTTP 429.
Day-1 finding: episode `summary` is only 1-2 sentences, so richer text comes from Wikipedia.
"""

from __future__ import annotations

import html
import re
import time

import httpx

from common.models import CastMember, Episode, Show

BASE = "https://api.tvmaze.com"
HEADERS = {"User-Agent": "youcantrememberme-hackathon/0.1"}


def _get(client: httpx.Client, path: str, **params) -> httpx.Response:
    for attempt in range(5):
        resp = client.get(f"{BASE}{path}", params=params)
        if resp.status_code != 429:
            return resp
        time.sleep(2**attempt)
    resp.raise_for_status()
    return resp


def strip_html(text: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def lookup_show(query: str, timeout: float = 1.5) -> tuple[int, str] | None:
    """Cheap existence check: (TVmaze id, canonical name), or None if there is no such show.

    One request with a short timeout, because the server calls this on the request path.
    Network errors propagate; the caller decides how to degrade.
    """
    with httpx.Client(headers=HEADERS, timeout=timeout) as client:
        resp = client.get(f"{BASE}/singlesearch/shows", params={"q": query})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    raw = resp.json()
    return raw["id"], raw["name"]


def fetch_cast(show_id: int) -> list[CastMember]:
    """The show's main cast as (character, actor). Best effort: a failure means no cast."""
    try:
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            resp = _get(client, f"/shows/{show_id}/cast")
            resp.raise_for_status()
            raw = resp.json()
    except httpx.HTTPError:
        return []
    seen: set[str] = set()
    cast = []
    for entry in raw:
        name = (entry.get("character") or {}).get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        cast.append(CastMember(character=name, actor=(entry.get("person") or {}).get("name")))
    return cast


def fetch_show_and_episodes(query: str) -> tuple[Show, list[Episode]]:
    """Look a show up by name; returns the show plus its regular (non-special) episodes."""
    with httpx.Client(headers=HEADERS, timeout=20) as client:
        resp = _get(client, "/singlesearch/shows", q=query)
        if resp.status_code == 404:
            raise LookupError(f"TVmaze has no show matching {query!r}")
        resp.raise_for_status()
        raw_show = resp.json()
        raw_eps = _get(client, f"/shows/{raw_show['id']}/episodes").json()

    episodes = [
        Episode(
            show_id=raw_show["id"],
            season=e["season"],
            number=e["number"],
            title=e["name"],
            airdate=e.get("airdate"),
            summary=strip_html(e.get("summary")),
        )
        for e in raw_eps
        if e.get("number") is not None  # skips unnumbered specials
    ]
    sizes: dict[int, int] = {}
    for e in episodes:
        sizes[e.season] = sizes.get(e.season, 0) + 1
    show = Show(
        id=raw_show["id"],
        name=raw_show["name"],
        premiered=raw_show.get("premiered"),
        season_sizes=dict(sorted(sizes.items())),
    )
    return show, episodes
