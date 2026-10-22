"""MCP server entry point (Streamable HTTP, stateless).

Run locally:   python -m server.main            # http://127.0.0.1:8000/mcp (HOST, PORT override)
Expose it:     cloudflared tunnel --url http://127.0.0.1:8000
"""

from __future__ import annotations

import os

import uvicorn  # ASGI (Asynchronous Server Gateway Interface) server

from common.store import ShowStore
from server.app import app
from server.on_demand import OnDemand




if __name__ == "__main__":
    uvicorn.run(
        app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000"))
    )
