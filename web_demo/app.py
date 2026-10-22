"""Fallback demo client that mimics how Alexa+ calls the MCP server.

    pip install -e ".[web]"
    python -m server.main                        # terminal 1: MCP server on :8000
    uvicorn web_demo.app:app --port 8080         # terminal 2: this page on :8080

(or just run `scripts/run_demo.sh`, which starts both with the offline demo data).

It is a *real* MCP client: every message becomes a Streamable HTTP `tools/call` to the server,
the same protocol Alexa+ uses. The only fake part is language understanding, done here by a
tiny rule-based parser (`web_demo/intent.py`) where Alexa+ would use its own AI.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx2
from fastapi import FastAPI
from fastapi.responses import FileResponse
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel

from web_demo.intent import HELP, parse

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
STATIC = Path(__file__).parent / "static"

# (tool name, arguments) -> the tool's result dict
ToolCaller = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


async def call_mcp_tool(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    http = httpx2.AsyncClient(timeout=30)
    async with http, Client(streamable_http_client(MCP_URL, http_client=http)) as client:
        result = await client.call_tool(tool, args)
    text = next((b.text for b in result.content if b.type == "text"), "{}")
    return json.loads(text)


class Ask(BaseModel):
    text: str


def create_app(call_tool: ToolCaller = call_mcp_tool) -> FastAPI:
    app = FastAPI(title="Catch Me Up: web demo")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.post("/api/ask")
    async def ask(body: Ask) -> dict[str, Any]:
        intent = parse(body.text)
        if intent is None:
            return {"understood": False, "spoken": HELP}
        try:
            result = await call_tool(intent.tool, intent.args)
        except Exception as exc:  # noqa: BLE001  (any transport failure: show it, don't 500)
            return {
                "understood": True,
                "tool": intent.tool,
                "arguments": intent.args,
                "spoken": f"I couldn't reach the MCP server at {MCP_URL}: {exc}",
                "error": True,
            }
        return {
            "understood": True,
            "tool": intent.tool,
            "arguments": intent.args,
            "result": result,
            "spoken": result.get("text", ""),
        }

    return app


app = create_app()
