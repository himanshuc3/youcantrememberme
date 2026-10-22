"""The Bedrock-driven web demo agent, with a scripted fake model (no AWS)."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace as NS

import httpx
import pytest
from fastapi.testclient import TestClient

from web_demo.agent import (
    MAX_STEPS,
    BedrockChat,
    OpenAIChat,
    detect_mode,
    make_chat,
    run_agent,
    to_openai_messages,
    tool_specs,
)
from web_demo.app import create_app


def text(t):
    return NS(type="text", text=t)


def use(id_, name, **args):
    return NS(type="tool_use", id=id_, name=name, input=args)


class FakeChat:
    """Replays scripted responses and records what it was sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.sent = []

    def create(self, system, messages, tools):
        self.sent.append(([dict(m) for m in messages], tools))
        stop, *blocks = self.responses.pop(0)
        return NS(stop_reason=stop, content=blocks)


SPECS = [{"name": "catch_me_up", "description": "d", "input_schema": {"type": "object"}}]


def test_model_picks_a_tool_then_answers_from_its_result():
    chat = FakeChat(
        (
            "tool_use",
            text("one sec"),
            use("t1", "catch_me_up", show="Lighthouse", season=1, episode=3),
        ),
        ("end_turn", text("Mara arrives and meets Teo.")),
    )
    seen = []

    async def call(name, args):
        seen.append((name, args))
        return {"found": True, "text": "Season 1, episode 1. Mara arrives."}

    out = asyncio.run(run_agent(chat, SPECS, call, "I'm on s1e3 of Lighthouse, catch me up"))
    assert seen == [("catch_me_up", {"show": "Lighthouse", "season": 1, "episode": 3})]
    assert out.spoken == "Mara arrives and meets Teo."
    assert out.calls[0]["result"]["found"] is True
    # the tool result went back to the model as a tool_result block
    second_call_messages = chat.sent[1][0]
    assert second_call_messages[-1]["content"][0]["type"] == "tool_result"
    assert second_call_messages[-1]["content"][0]["tool_use_id"] == "t1"
    assert chat.sent[0][1] == SPECS  # the server's tools were offered to the model


def test_history_is_sent_so_follow_ups_work():
    chat = FakeChat(("end_turn", text("In noir style: it rained.")))
    history = [
        {"role": "user", "content": "catch me up, season 1 episode 3"},
        {"role": "assistant", "content": "Mara arrived."},
    ]

    async def call(name, args):
        raise AssertionError("no tool needed")

    out = asyncio.run(run_agent(chat, SPECS, call, "now make it noir", history))
    sent = chat.sent[0][0]
    assert [m["content"] for m in sent] == [
        "catch me up, season 1 episode 3",
        "Mara arrived.",
        "now make it noir",
    ]
    assert out.spoken.startswith("In noir style")


def test_a_failing_tool_is_reported_to_the_model_not_raised():
    chat = FakeChat(
        ("tool_use", use("t1", "catch_me_up", show="x", season=1, episode=1)),
        ("end_turn", text("Sorry, the recap service is down.")),
    )

    async def call(name, args):
        raise ConnectionError("boom")

    out = asyncio.run(run_agent(chat, SPECS, call, "hi"))
    result_block = chat.sent[1][0][-1]["content"][0]
    assert result_block["is_error"] is True and "boom" in result_block["content"]
    assert out.spoken == "Sorry, the recap service is down."


def test_a_model_that_never_stops_calling_tools_is_cut_off():
    chat = FakeChat(*[("tool_use", use(f"t{i}", "catch_me_up")) for i in range(MAX_STEPS)])

    async def call(name, args):
        return {"found": False}

    out = asyncio.run(run_agent(chat, SPECS, call, "loop"))
    assert "stuck" in out.spoken and len(out.calls) == MAX_STEPS


def test_tool_specs_use_the_messages_api_shape():
    tool = NS(name="a", description=None, input_schema={"type": "object"})
    assert tool_specs([tool]) == [
        {"name": "a", "description": "", "input_schema": {"type": "object"}}
    ]


def test_bedrock_chat_passes_model_tools_and_system(monkeypatch):
    monkeypatch.setenv("WEB_DEMO_MODEL_ID", "anthropic.test-model")
    sent = {}
    client = NS(messages=NS(create=lambda **kw: sent.update(kw) or "resp"))
    assert (
        BedrockChat(client=client).create("sys", [{"role": "user", "content": "x"}], SPECS)
        == "resp"
    )
    assert (
        sent["model"] == "anthropic.test-model"
        and sent["tools"] == SPECS
        and sent["system"] == "sys"
    )


# ---- through the FastAPI app ---------------------------------------------------------------


def make_client(chat, calls_log=None):
    @asynccontextmanager
    async def connect():
        async def call(name, args):
            (calls_log if calls_log is not None else []).append((name, args))
            return {"found": True, "text": "Recap text.", "covered_through": "season 1, episode 3"}

        yield SPECS, call

    return TestClient(create_app(mode="bedrock", chat=chat, connect=connect))


def test_app_runs_the_agent_and_returns_history_for_the_next_turn():
    chat = FakeChat(
        ("tool_use", use("t1", "catch_me_up", show="X", season=1, episode=3)),
        ("end_turn", text("Here is your recap.")),
    )
    log = []
    body = make_client(chat, log).post("/api/ask", json={"text": "catch me up on X s1e3"}).json()
    assert body["spoken"] == "Here is your recap." and body["mode"] == "bedrock"
    assert [c["tool"] for c in body["calls"]] == ["catch_me_up"] and log
    assert body["history"][-2:] == [
        {"role": "user", "content": "catch me up on X s1e3"},
        {"role": "assistant", "content": "Here is your recap."},
    ]


def test_app_reports_bedrock_problems_in_the_chat_instead_of_a_500():
    class Broken:
        def create(self, *a):
            raise PermissionError("no model access")

    resp = make_client(Broken()).post("/api/ask", json={"text": "hi"})
    body = resp.json()
    assert resp.status_code == 200 and body["error"] is True
    assert "PermissionError" in body["spoken"] and "no model access" in body["spoken"]


@pytest.mark.parametrize("mode", ["rules"])
def test_rules_mode_still_works_without_bedrock(mode):
    async def fake(tool, args):
        return {"text": "A recap.", "covered_through": "season 1, episode 3"}

    client = TestClient(create_app(fake, mode=mode))
    body = client.post("/api/ask", json={"text": "Recap The Bear through season 1"}).json()
    assert body["mode"] == "rules" and body["calls"][0]["tool"] == "get_recap"


# ---- OpenAI-compatible providers (OpenRouter, OpenAI, Ollama) ----------------------------------


def openai_chat(*replies):
    """An OpenAIChat whose HTTP calls are answered with scripted chat-completion messages."""
    sent = []
    queue = list(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((str(request.url), dict(request.headers), json.loads(request.content)))
        return httpx.Response(200, json={"choices": [{"message": queue.pop(0)}]})

    client = httpx.Client(
        base_url="https://llm.example/v1/",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer k"},
    )
    return OpenAIChat(model="m", client=client), sent


def test_openai_adapter_turns_tool_calls_into_tool_use_blocks():
    chat, sent = openai_chat(
        {
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "catch_me_up", "arguments": '{"show": "X", "season": 1}'},
                }
            ],
        }
    )
    resp = chat.create("sys", [{"role": "user", "content": "hi"}], SPECS)
    assert resp.stop_reason == "tool_use"
    (block,) = resp.content
    assert (block.type, block.id, block.name) == ("tool_use", "c1", "catch_me_up")
    assert block.input == {"show": "X", "season": 1}
    url, _headers, payload = sent[0]
    assert url == "https://llm.example/v1/chat/completions"
    assert payload["tools"][0]["function"] == {
        "name": "catch_me_up",
        "description": "d",
        "parameters": {"type": "object"},
    }
    assert payload["messages"][0] == {"role": "system", "content": "sys"}


def test_openai_adapter_plain_answer_ends_the_turn():
    chat, _ = openai_chat({"content": "Hello there."})
    resp = chat.create("sys", [{"role": "user", "content": "hi"}], SPECS)
    assert resp.stop_reason == "end_turn" and resp.content[0].text == "Hello there."


def test_conversation_is_converted_to_openai_format():
    messages = [
        {"role": "user", "content": "catch me up"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "one sec"},
                {"type": "tool_use", "id": "c1", "name": "catch_me_up", "input": {"season": 1}},
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "c1", "content": '{"ok": 1}'}],
        },
    ]
    out = to_openai_messages("sys", messages)
    assert out[1] == {"role": "user", "content": "catch me up"}
    assert out[2]["tool_calls"][0]["function"] == {
        "name": "catch_me_up",
        "arguments": '{"season": 1}',
    }
    assert out[2]["content"] == "one sec"
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": '{"ok": 1}'}


def test_agent_loop_works_end_to_end_over_the_openai_adapter():
    chat, sent = openai_chat(
        {
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "catch_me_up", "arguments": "{}"},
                }
            ],
        },
        {"content": "Here you go."},
    )

    async def call(name, args):
        return {"found": True, "text": "A recap."}

    out = asyncio.run(run_agent(chat, SPECS, call, "catch me up"))
    assert out.spoken == "Here you go." and out.calls[0]["tool"] == "catch_me_up"
    assert sent[1][2]["messages"][-1]["role"] == "tool"


def test_openai_mode_needs_a_model_and_unknown_modes_are_rejected(monkeypatch):
    monkeypatch.delenv("WEB_DEMO_MODEL_ID", raising=False)
    with pytest.raises(ValueError, match="WEB_DEMO_MODEL_ID"):
        make_chat("openai")
    with pytest.raises(ValueError, match="unknown WEB_DEMO_LLM"):
        make_chat("nope")


@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, "rules"),
        ({"AWS_BEARER_TOKEN_BEDROCK": "k"}, "bedrock"),
        ({"AWS_PROFILE": "p"}, "bedrock"),
        ({"ANTHROPIC_API_KEY": "k", "AWS_BEARER_TOKEN_BEDROCK": "k"}, "anthropic"),
        ({"OPENAI_API_KEY": "k", "ANTHROPIC_API_KEY": "k"}, "openai"),
        ({"OPENAI_BASE_URL": "http://localhost:11434/v1"}, "openai"),
    ],
)
def test_provider_is_detected_from_the_credentials_present(monkeypatch, env, expected):
    for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert detect_mode() == expected
