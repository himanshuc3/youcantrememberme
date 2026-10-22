"""The application server: an MCP server with the recap tools composed in.

    ApplicationServer
      ├── mcp    MCPServer   protocol, transport, tool listing
      └── tools  RecapTools  the four tools, registered onto `mcp`

`server/main.py` runs it (uvicorn) and `server/handler.py` wraps it for AWS Lambda.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer  # mcp 2.x (was FastMCP in 1.x)
from mcp.server.transport_security import TransportSecuritySettings

from common.store import ShowStore
from server.on_demand import OnDemand
from server.recap_tools import RecapTools

# Identity of the server as shown to MCP clients; `instructions` is read by the LLM (Alexa+).
MCP_CONFIG = {
    "name": "Catch Me Up",
    "title": "Catch Me Up",
    "instructions": (
        "Spoiler-safe TV recaps. The server remembers nothing about users: always pass "
        "the show and the season/episode the user says they have reached. Use catch_me_up "
        "for 'catch me up, I'm on season 2 episode 4', get_previously_on for a short "
        "'previously on' before the episode they are about to watch, get_recap for an "
        "explicit range, and get_characters for 'who is X' or 'who's who' questions. If the "
        "user asks for a style (noir, for a child, with another show's characters...), pass it "
        "as `style` and retell the returned text accordingly, adding no new plot. Never reveal "
        "anything past the episode the user has reached."
    ),
}

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


class ApplicationServer:
    def __init__(self, store: ShowStore | None = None, on_demand: OnDemand | None = None):
        self.store = store or ShowStore()
        if on_demand is None and os.environ.get("ON_DEMAND") == "1":
            # Unknown shows get queued for `python -m pipeline.worker` (see server/on_demand.py).
            on_demand = OnDemand.from_env(self.store.root, backend=self.store.backend)
        self.mcp = MCPServer(**MCP_CONFIG)
        self.tools = RecapTools(self.store, on_demand)
        self.tools.register(self.mcp)

    def asgi_app(self):
        """ASGI app. Stateless + JSON responses suit Lambda and Alexa+'s request/response use."""
        return self.mcp.streamable_http_app(
            stateless_http=True, json_response=True, transport_security=transport_security()
        )


app = ApplicationServer().asgi_app()
