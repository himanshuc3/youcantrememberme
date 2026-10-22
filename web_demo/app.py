"""Demo client that mimics how Alexa+ calls the MCP server.

    task dev            # or `task db:up`, `task server`; then `task web`
    open http://127.0.0.1:8080

It is a *real* MCP client: every message becomes Streamable HTTP `tools/list` / `tools/call`
requests to the server, the same protocol Alexa+ uses. The only fake part is the language
understanding Alexa+ would do. Modes (WEB_DEMO_LLM; unset = picked from the credentials present):

* `openai` / `anthropic` / `bedrock`: an LLM reads the server's tool list, picks tools, fills in
  arguments and writes the spoken answer (`web_demo/agent.py`). Needs that provider's API key.
* `rules`: a tiny regex parser (`web_demo/intent.py`), offline, handles a few fixed phrasings.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any

import httpx2
from fastapi import FastAPI
from fastapi.responses import FileResponse
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel

from web_demo.agent import Chat, ToolCaller, detect_mode, make_chat, run_agent, tool_specs
from web_demo.intent import HELP, parse

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
STATIC = Path(__file__).parent / "static"

KEY_HINT = {
    "openai": "OPENAI_API_KEY (and OPENAI_BASE_URL)",
    "anthropic": "ANTHROPIC_API_KEY",
    "bedrock": "AWS_BEARER_TOKEN_BEDROCK",
}

Connect = Callable[[], AbstractAsyncContextManager[tuple[list[dict], ToolCaller]]]


def _result_dict(result) -> dict[str, Any]:
    text = next((b.text for b in result.content if b.type == "text"), "{}")
    return json.loads(text)


async def call_mcp_tool(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    http = httpx2.AsyncClient(timeout=30)
    async with http, Client(streamable_http_client(MCP_URL, http_client=http)) as client:
        return _result_dict(await client.call_tool(tool, args))


@asynccontextmanager
async def mcp_session() -> AsyncIterator[tuple[list[dict], ToolCaller]]:
    """One MCP connection: the server's tool list (as model tool specs) and a way to call them."""
    http = httpx2.AsyncClient(timeout=30)
    async with http, Client(streamable_http_client(MCP_URL, http_client=http)) as client:
        specs = tool_specs((await client.list_tools()).tools)

        async def call(tool: str, args: dict[str, Any]) -> dict[str, Any]:
            return _result_dict(await client.call_tool(tool, args))

        yield specs, call


def _root_cause(exc: BaseException) -> BaseException:
    """The MCP client wraps failures in task-group exception groups; show the real error."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


class Turn(BaseModel):
    role: str
    content: str


class Ask(BaseModel):
    text: str
    history: list[Turn] = []


def create_app(
    call_tool: ToolCaller = call_mcp_tool,
    *,
    mode: str | None = None,
    chat: Chat | None = None,
    connect: Connect = mcp_session,
) -> FastAPI:
    mode = (mode or os.environ.get("WEB_DEMO_LLM") or detect_mode()).lower()
    app = FastAPI(title="Catch Me Up: web demo")
    state: dict[str, Chat] = {}  # the Bedrock client, built on first use so errors show in chat

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.post("/api/ask")
    async def ask(body: Ask) -> dict[str, Any]:
        history = [t.model_dump() for t in body.history]

        def reply(spoken: str, calls: list, **extra: Any) -> dict[str, Any]:
            turns = [*history, {"role": "user", "content": body.text}]
            turns.append({"role": "assistant", "content": spoken})
            return {"spoken": spoken, "calls": calls, "mode": mode, "history": turns, **extra}

        if mode == "rules":
            intent = parse(body.text)
            if intent is None:
                return reply(HELP, [], understood=False)
            try:
                result = await call_tool(intent.tool, intent.args)
            except Exception as exc:  # noqa: BLE001  (any transport failure: show it, don't 500)
                spoken = f"I couldn't reach the MCP server at {MCP_URL}: {exc}"
                return reply(spoken, [], understood=True, error=True)
            calls = [{"tool": intent.tool, "arguments": intent.args, "result": result}]
            return reply(result.get("text", ""), calls, understood=True)

        try:
            model = state.setdefault("chat", chat or make_chat(mode))
            async with connect() as (specs, call):
                out = await run_agent(model, specs, call, body.text, history)
        except Exception as exc:  # noqa: BLE001  (no credentials, no model access, server down...)
            cause = _root_cause(exc)
            spoken = f"I couldn't complete that ({type(cause).__name__}): {cause}"
            if any(s in str(cause).lower() for s in ("credentials", "401", "api key", "auth")):
                spoken += (
                    f" Check {KEY_HINT.get(mode, 'your API key')} in .env, then restart `task web`."
                )
            return reply(spoken, [], understood=True, error=True)
        return reply(out.spoken, out.calls, understood=True)

    return app


app = create_app()
