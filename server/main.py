"""MCP server entry point (Streamable HTTP, stateless).

Run locally:   python -m server.main            # serves http://127.0.0.1:8000/mcp
Expose it:     cloudflared tunnel --url http://127.0.0.1:8000
"""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.mcpserver import MCPServer  # mcp 2.x (was FastMCP in 1.x)

from common.store import ShowStore
from server import tools


def build_server(store: ShowStore | None = None) -> MCPServer:
    store = store or ShowStore()
    mcp = MCPServer(
        "Catch Me Up",
        instructions=(
            "Spoiler-safe TV recaps. Use get_recap when someone returns to a show and wants "
            "to catch up through a given season/episode. Never reveal anything past the "
            "requested episode."
        ),
    )

    @mcp.tool()
    def find_show(query: str) -> dict:
        """Check whether a TV show is available and list its seasons and episode counts."""
        return tools.find_show(store, query)

    @mcp.tool()
    def get_recap(
        show: str,
        to_season: int,
        to_episode: int | None = None,
        from_season: int = 1,
        from_episode: int = 1,
        detail: Literal["brief", "standard"] = "standard",
    ) -> dict:
        """Spoiler-safe spoken recap of a TV show from one point to another, e.g. to catch up
        after a break. Only events up to to_season/to_episode are included; omit to_episode
        to recap through the end of that season."""
        return tools.get_recap(
            store, show, to_season, to_episode, from_season, from_episode, detail
        )

    @mcp.tool()
    def get_previously_on(show: str, season: int, episode: int, count: int = 2) -> dict:
        """'Previously on...' recap of the last few episodes before the one the user is about
        to watch (season/episode). The episode itself is not included."""
        return tools.get_previously_on(store, show, season, episode, count)

    return mcp


def build_app(store: ShowStore | None = None):
    """ASGI app. Stateless + JSON responses suit Lambda and Alexa+'s request/response use."""
    return build_server(store).streamable_http_app(stateless_http=True, json_response=True)


app = build_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
