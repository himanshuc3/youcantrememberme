"""A chat agent for the web demo: an LLM picks and calls our MCP tools, standing in for Alexa+.

The MCP server is unchanged and has no LLM; here the model reads the tool list (names,
descriptions, schemas) from the server, decides which tool to call and with what arguments, and
turns the results into a spoken answer. It also does the restyling the server asks for through
`rewrite` instructions (e.g. "like a noir narrator").

Pick the model provider with WEB_DEMO_LLM; unset, it is chosen from the credentials present (messages are kept in Anthropic's format internally;
the OpenAI adapter converts to and from it):
  bedrock    Claude on Amazon Bedrock. AWS_BEARER_TOKEN_BEDROCK (a Bedrock API key) or the normal
             AWS credential chain; AWS_REGION. Model: WEB_DEMO_MODEL_ID, else BEDROCK_MODEL_ID.
  anthropic  The Anthropic API directly. ANTHROPIC_API_KEY.
  openai     Any OpenAI-compatible chat API with tool calling: OpenRouter, OpenAI, or a local
             Ollama (no key). OPENAI_BASE_URL, OPENAI_API_KEY, and WEB_DEMO_MODEL_ID (required).
  rules      No model: the offline regex parser (web_demo/intent.py), handled in web_demo/app.py.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Protocol

import httpx

DEFAULT_MODEL = "anthropic.claude-sonnet-5"  # Bedrock id
ANTHROPIC_MODEL = "claude-sonnet-5-5"  # Anthropic API id
MAX_STEPS = 6  # model <-> tool round trips per message
MAX_HISTORY = 20  # past messages sent back to the model

SYSTEM = """You are the voice of "Catch Me Up", a spoiler-safe TV recap service, speaking through a \
smart speaker. Be brief and natural to say aloud: no markdown, lists or emoji.

Use the tools for everything about shows. Never answer plot or character questions from your own \
memory, because it may contain spoilers: only say what the tool results contain.
- The tools remember nothing. Always pass the show and the season/episode the user says they have \
reached. If they haven't said where they are, ask which season and episode they last watched. \
"I'm on season 2 episode 4" means they finished that episode. Reuse a position the user already \
gave earlier in this conversation.
- If a result says it is fetching the show or newer episodes, tell the user to ask again in a few \
minutes.
- If a result has `rewrite`, retell its `text` in the requested style, following the instructions. \
You may use your knowledge of other shows only to rename or restyle; add no plot beyond `text`."""


class Chat(Protocol):
    def create(self, system: str, messages: list[dict], tools: list[dict]) -> Any: ...


class _MessagesChat:
    """Providers that speak the Anthropic Messages API (Bedrock, Anthropic)."""

    model: str
    client: Any

    def create(self, system: str, messages: list[dict], tools: list[dict]) -> Any:
        return self.client.messages.create(
            model=self.model, max_tokens=1500, system=system, messages=messages, tools=tools
        )


class BedrockChat(_MessagesChat):
    def __init__(self, model: str | None = None, region: str | None = None, client=None):
        self.model = (
            model
            or os.environ.get("WEB_DEMO_MODEL_ID")
            or os.environ.get("BEDROCK_MODEL_ID")
            or DEFAULT_MODEL
        )
        if client is None:
            from anthropic import AnthropicBedrockMantle  # needs `anthropic[bedrock]`

            client = AnthropicBedrockMantle(
                aws_region=region or os.environ.get("AWS_REGION", "us-east-1")
            )
        self.client = client


class AnthropicChat(_MessagesChat):
    def __init__(self, model: str | None = None, client=None):
        self.model = model or os.environ.get("WEB_DEMO_MODEL_ID") or ANTHROPIC_MODEL
        if client is None:
            from anthropic import Anthropic

            client = Anthropic()  # ANTHROPIC_API_KEY
        self.client = client


class OpenAIChat:
    """Any OpenAI-compatible /chat/completions endpoint (OpenRouter, OpenAI, Ollama, ...)."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ):
        self.model = model or os.environ.get("WEB_DEMO_MODEL_ID")
        if not self.model:
            raise ValueError(
                "set WEB_DEMO_MODEL_ID to a model of your OpenAI-compatible provider, e.g. "
                "llama3.1 (Ollama) or an OpenRouter model id"
            )
        base = base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.client = client or httpx.Client(
            base_url=base.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {key}"} if key else {},
            timeout=120,
        )

    def create(self, system: str, messages: list[dict], tools: list[dict]) -> Any:
        payload = {
            "model": self.model,
            "max_tokens": 1500,
            "messages": to_openai_messages(system, messages),
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ],
        }
        resp = self.client.post("chat/completions", json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"{resp.status_code} from the model provider: {resp.text[:300]}")
        message = resp.json()["choices"][0]["message"]
        blocks = []
        if message.get("content"):
            blocks.append(SimpleNamespace(type="text", text=message["content"]))
        for call in message.get("tool_calls") or []:
            args = call["function"].get("arguments") or "{}"
            blocks.append(
                SimpleNamespace(
                    type="tool_use",
                    id=call["id"],
                    name=call["function"]["name"],
                    input=json.loads(args) if isinstance(args, str) else args,
                )
            )
        has_calls = any(b.type == "tool_use" for b in blocks)
        return SimpleNamespace(stop_reason="tool_use" if has_calls else "end_turn", content=blocks)


def to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    """Anthropic-format conversation -> OpenAI chat messages."""
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        if isinstance(m["content"], str):
            out.append({"role": m["role"], "content": m["content"]})
        elif m["role"] == "assistant":
            texts = [b["text"] for b in m["content"] if b["type"] == "text"]
            calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                }
                for b in m["content"]
                if b["type"] == "tool_use"
            ]
            out.append(
                {"role": "assistant", "content": " ".join(texts) or None, "tool_calls": calls}
            )
        else:  # a user turn made of tool results
            for b in m["content"]:
                out.append(
                    {"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]}
                )
    return out


def detect_mode() -> str:
    """Provider to use when WEB_DEMO_LLM isn't set: whichever credentials are present."""
    env = os.environ
    if env.get("OPENAI_API_KEY") or env.get("OPENAI_BASE_URL"):
        return "openai"
    if env.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if env.get("AWS_BEARER_TOKEN_BEDROCK") or env.get("AWS_PROFILE"):
        return "bedrock"
    return "rules"


def make_chat(mode: str) -> Chat:
    if mode == "bedrock":
        return BedrockChat()
    if mode == "anthropic":
        return AnthropicChat()
    if mode == "openai":
        return OpenAIChat()
    raise ValueError(f"unknown WEB_DEMO_LLM {mode!r}; use bedrock, anthropic, openai or rules")


ToolCaller = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


def tool_specs(mcp_tools) -> list[dict]:
    """MCP tool definitions -> the Messages API `tools` format."""
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
        for t in mcp_tools
    ]


@dataclass
class AgentResult:
    spoken: str
    calls: list[dict[str, Any]] = field(default_factory=list)  # {tool, arguments, result}


async def run_agent(
    chat: Chat,
    tools: list[dict],
    call_tool: ToolCaller,
    text: str,
    history: list[dict] | None = None,
) -> AgentResult:
    messages = [*(history or [])[-MAX_HISTORY:], {"role": "user", "content": text}]
    calls: list[dict[str, Any]] = []
    for _ in range(MAX_STEPS):
        resp = await asyncio.to_thread(chat.create, SYSTEM, messages, tools)
        if resp.stop_reason == "refusal":
            raise RuntimeError("the model declined to answer")
        content = [
            {"type": "text", "text": b.text}
            if b.type == "text"
            else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
            for b in resp.content
            if b.type in ("text", "tool_use")
        ]
        uses = [b for b in content if b["type"] == "tool_use"]
        if not uses:
            spoken = " ".join(b["text"] for b in content if b["type"] == "text").strip()
            return AgentResult(spoken or "(no answer)", calls)
        messages.append({"role": "assistant", "content": content})
        results = []
        for use in uses:
            try:
                out = await call_tool(use["name"], use["input"])
                payload, is_error = json.dumps(out), False
            except Exception as exc:  # noqa: BLE001  (tell the model; it can recover or apologise)
                out, payload, is_error = {"error": str(exc)}, f"Tool failed: {exc}", True
            calls.append({"tool": use["name"], "arguments": use["input"], "result": out})
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": use["id"],
                    "content": payload,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": results})
    return AgentResult("Sorry, I got stuck working that out. Could you rephrase?", calls)
