"""MCP server entry point (Streamable HTTP, stateless).

Run locally:   python -m server.main            # http://127.0.0.1:8000/mcp (HOST, PORT override)
Expose it:     cloudflared tunnel --url http://127.0.0.1:8000
"""

from __future__ import annotations

import os
from typing import Literal

import uvicorn  # ASGI (Asynchronous Server Gateway Interface) server
from mcp.server.mcpserver import MCPServer  # mcp 2.x (was FastMCP in 1.x)
from mcp.server.transport_security import TransportSecuritySettings

from common.store import ShowStore
from server import tools
from server.on_demand import OnDemand

LOCAL_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]


def transport_security() -> TransportSecuritySettings:
    """DNS-rebinding protection: the SDK rejects requests whose Host header isn't allowed
    (HTTP 421 "Invalid Host header"). Localhost is always allowed. When the server is reached
    through a tunnel or a cloud URL, list that hostname:

        ALLOWED_HOSTS=abc-123.trycloudflare.com,my-fn.lambda-url.us-east-1.on.aws

    `ALLOWED_HOSTS=*` switches the check off (handy with tunnels whose hostname changes on
    every run; avoid it for a long-lived deployment).
    """
    extra = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
    if "*" in extra:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    hosts = LOCAL_HOSTS + extra
    return TransportSecuritySettings(
        allowed_hosts=hosts,
        allowed_origins=[f"{scheme}://{h}" for h in hosts for scheme in ("http", "https")],
    )


def build_server(store: ShowStore | None = None, on_demand: OnDemand | None = None) -> MCPServer:
    store = store or ShowStore()
    if on_demand is None and os.environ.get("ON_DEMAND") == "1":
        # Unknown shows get queued for `python -m pipeline.worker` (see server/on_demand.py).
        on_demand = OnDemand.from_env(store.root)
    mcp = MCPServer(
        "Catch Me Up",
        instructions=(
            "Spoiler-safe TV recaps. The server remembers nothing about users: always pass "
            "the show and the season/episode the user says they have reached. Use catch_me_up "
            "for 'catch me up, I'm on season 2 episode 4', get_previously_on for a short "
            "'previously on' before the episode they are about to watch, and get_recap for an "
            "explicit range. Never reveal anything past the episode the user has reached."
        ),
    )

    @mcp.tool()
    def find_show(query: str) -> dict:
        """Check whether a TV show is available and list its seasons and episode counts."""
        return tools.find_show(store, query, on_demand=on_demand)

    @mcp.tool()
    def catch_me_up(
        show: str,
        season: int,
        episode: int,
        detail: Literal["brief", "standard"] = "standard",
    ) -> dict:
        """Spoiler-safe recap of everything from the start of the show through the episode the
        user last watched ("I'm on season 2, episode 4" means they finished that episode)."""
        return tools.catch_me_up(store, show, season, episode, detail, on_demand=on_demand)

    @mcp.tool()
    def get_recap(
        show: str,
        to_season: int,
        to_episode: int | None = None,
        from_season: int = 1,
        from_episode: int = 1,
        detail: Literal["brief", "standard"] = "standard",
    ) -> dict:
        """Spoiler-safe spoken recap of a TV show between two explicit points. Only events up
        to to_season/to_episode are included; omit to_episode to recap through the end of
        that season."""
        return tools.get_recap(
            store,
            show,
            to_season,
            to_episode,
            from_season,
            from_episode,
            detail,
            on_demand=on_demand,
        )

    @mcp.tool()
    def get_previously_on(show: str, season: int, episode: int, count: int = 2) -> dict:
        """'Previously on...' recap of the last few episodes (default 2) before the given
        season and episode, which is the one the user is about to watch."""
        return tools.get_previously_on(store, show, season, episode, count, on_demand=on_demand)

    return mcp


def build_app(store: ShowStore | None = None, on_demand: OnDemand | None = None):
    """ASGI app. Stateless + JSON responses suit Lambda and Alexa+'s request/response use."""
    return build_server(store, on_demand).streamable_http_app(
        stateless_http=True, json_response=True, transport_security=transport_security()
    )


app = build_app()

if __name__ == "__main__":
    uvicorn.run(
        app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000"))
    )
