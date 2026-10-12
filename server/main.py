"""MCP server entry point (Streamable HTTP, stateless).

Run locally:   python -m server.main            # serves http://127.0.0.1:8000/mcp
Expose it:     cloudflared tunnel --url http://127.0.0.1:8000
"""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.mcpserver import Context, MCPServer  # mcp 2.x (was FastMCP in 1.x)
from mcp.server.transport_security import TransportSecuritySettings

from common.progress import ProgressStore
from common.store import ShowStore
from server import tools
from server.identity import resolve_user_id
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


def build_server(
    store: ShowStore | None = None,
    progress: ProgressStore | None = None,
    on_demand: OnDemand | None = None,
) -> MCPServer:
    store = store or ShowStore()
    progress = progress or ProgressStore()
    if on_demand is None and os.environ.get("ON_DEMAND") == "1":
        # Unknown shows get queued for `python -m pipeline.worker` (see server/on_demand.py).
        on_demand = OnDemand.from_env(store.root)
    mcp = MCPServer(
        "Catch Me Up",
        instructions=(
            "Spoiler-safe TV recaps. If the user says how far they got in a show, call "
            "save_progress so you can remember it. When they later ask to be caught up, call "
            "catch_me_up. Use get_recap for an explicit season/episode range. Never reveal "
            "anything past the episode the user has reached."
        ),
    )

    def user_id(ctx: Context) -> str:
        return resolve_user_id(ctx.request_context, ctx.headers)

    @mcp.tool()
    def find_show(query: str, ctx: Context) -> dict:
        """Check whether a TV show is available and list its seasons and episode counts."""
        return tools.find_show(store, query, on_demand=on_demand, user_id=user_id(ctx))

    @mcp.tool()
    def save_progress(show: str, season: int, episode: int, ctx: Context) -> dict:
        """Remember how far the user has watched a show ("I'm on season 2, episode 4" means
        they finished season 2 episode 4). Saved across conversations."""
        return tools.save_progress(
            store, progress, user_id(ctx), show, season, episode, on_demand=on_demand
        )

    @mcp.tool()
    def catch_me_up(
        ctx: Context,
        show: str | None = None,
        detail: Literal["brief", "standard"] = "standard",
    ) -> dict:
        """Spoiler-safe recap from the start through the episode the user last said they
        watched. Omit show to use the show they most recently talked about. If no progress
        is saved yet, it asks which episode they reached."""
        return tools.catch_me_up(store, progress, user_id(ctx), show, detail, on_demand=on_demand)

    @mcp.tool()
    def get_recap(
        show: str,
        ctx: Context,
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
            user_id=user_id(ctx),
        )

    @mcp.tool()
    def get_previously_on(
        ctx: Context,
        show: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        count: int = 2,
    ) -> dict:
        """'Previously on...' recap of the last few episodes. Give season and episode to recap
        the episodes before that one; omit them to recap the last episodes the user already
        watched, using their saved progress."""
        return tools.get_previously_on(
            store, progress, user_id(ctx), show, season, episode, count, on_demand=on_demand
        )

    return mcp


def build_app(
    store: ShowStore | None = None,
    progress: ProgressStore | None = None,
    on_demand: OnDemand | None = None,
):
    """ASGI app. Stateless + JSON responses suit Lambda and Alexa+'s request/response use."""
    return build_server(store, progress, on_demand).streamable_http_app(
        stateless_http=True, json_response=True, transport_security=transport_security()
    )


app = build_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
