"""The MCP-facing tools, as a class that owns their dependencies.

Each public method is one tool: its name, signature and docstring are exactly what Alexa+ sees
(the LLM picks tools from those strings). The logic stays in `server/tools.py` as plain
functions over the stores; this class only binds the store and the on-demand queue to them.
`register` adds the methods to an MCP server (composition: the server doesn't subclass this).
"""

from __future__ import annotations

from typing import Literal

from mcp.server.mcpserver import MCPServer

from common.store import ShowStore
from server import tools
from server.on_demand import OnDemand


class RecapTools:
    def __init__(self, store: ShowStore, on_demand: OnDemand | None = None):
        self.store = store
        self.on_demand = on_demand

    def find_show(self, query: str) -> dict:
        """Check whether a TV show is available and list its seasons and episode counts."""
        return tools.find_show(self.store, query, on_demand=self.on_demand)

    def catch_me_up(
        self,
        show: str,
        season: int,
        episode: int,
        detail: Literal["brief", "standard"] = "standard",
        style: str | None = None,
    ) -> dict:
        """Spoiler-safe recap of everything from the start of the show through the episode the
        user last watched ("I'm on season 2, episode 4" means they finished that episode).

        style (optional): a free-text request such as "like a noir narrator", "for a five year
        old" or "with the characters of Friends". The server cannot restyle text itself; it
        returns `rewrite` instructions and you retell `text` in that style."""
        return tools.catch_me_up(
            self.store, show, season, episode, detail, style, on_demand=self.on_demand
        )

    def get_recap(
        self,
        show: str,
        to_season: int,
        to_episode: int | None = None,
        from_season: int = 1,
        from_episode: int = 1,
        detail: Literal["brief", "standard"] = "standard",
        style: str | None = None,
    ) -> dict:
        """Spoiler-safe spoken recap of a TV show between two explicit points. Only events up
        to to_season/to_episode are included; omit to_episode to recap through the end of
        that season.

        style (optional): a free-text request such as "like a noir narrator" or "with the
        characters of Friends". The server cannot restyle text itself; it returns `rewrite`
        instructions and you retell `text` in that style."""
        return tools.get_recap(
            self.store,
            show,
            to_season,
            to_episode,
            from_season,
            from_episode,
            detail,
            style,
            on_demand=self.on_demand,
        )

    def get_previously_on(
        self,
        show: str,
        season: int,
        episode: int,
        count: int = 2,
        style: str | None = None,
    ) -> dict:
        """'Previously on...' recap of the last few episodes (default 2) before the given
        season and episode, which is the one the user is about to watch.

        style (optional): a free-text request such as "like a noir narrator". The server
        cannot restyle text itself; it returns `rewrite` instructions and you retell `text`."""
        return tools.get_previously_on(
            self.store, show, season, episode, count, style, on_demand=self.on_demand
        )

    def get_characters(
        self, show: str, season: int, episode: int, character: str | None = None
    ) -> dict:
        """Spoiler-safe "who's who". Without `character`: the characters introduced so far
        (through the season and episode the user has reached). With `character` (a spoken name
        like "Mara"): who they are and what is known about them so far. Never reveals
        characters who appear after that episode."""
        return tools.get_characters(
            self.store, show, season, episode, character, on_demand=self.on_demand
        )

    def __get_tools(self):
        return (
            self.find_show,
            self.catch_me_up,
            self.get_recap,
            self.get_previously_on,
            self.get_characters,
        )

    def register(self, mcp: MCPServer) -> None:
        mcp_tools = self.__get_tools()
        for tool in mcp_tools:
            mcp.add_tool(tool)
