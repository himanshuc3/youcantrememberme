"""End to end over real HTTP: JSON-RPC `tools/call` against the Streamable HTTP app, exactly as
a remote client (Alexa+ or the web demo) would send it."""

import json

import pytest
from starlette.testclient import TestClient

from server.main import build_app

HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


@pytest.fixture
def client(shows, monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    with TestClient(build_app(shows)) as c:
        yield c


def rpc(client, method, params=None, id_=1):
    headers = dict(HEADERS)
    body = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        body["params"] = params
    resp = client.post("/mcp", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def call(client, tool, args):
    out = rpc(client, "tools/call", {"name": tool, "arguments": args})
    assert "error" not in out, out
    assert not out["result"].get("isError"), out
    return json.loads(out["result"]["content"][0]["text"])


def test_initialize_negotiates_the_required_protocol_version(client):
    out = rpc(
        client,
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    )
    assert out["result"]["protocolVersion"] == "2025-11-25"


def test_lists_all_tools(client):
    names = {t["name"] for t in rpc(client, "tools/list")["result"]["tools"]}
    assert names == {
        "find_show",
        "catch_me_up",
        "get_recap",
        "get_previously_on",
    }


def test_every_tool_has_a_description(client):
    # Alexa+ chooses tools from these strings.
    for t in rpc(client, "tools/list")["result"]["tools"]:
        assert len(t.get("description", "")) > 30, t["name"]


def test_get_recap_over_http(client):
    out = call(client, "get_recap", {"show": "the test show", "to_season": 1, "to_episode": 2})
    assert out["covered_through"] == "season 1, episode 2"
    assert "S1E3" not in out["text"]


def test_catch_me_up_is_stateless_and_uses_the_given_position(client):
    first = call(client, "catch_me_up", {"show": "The Test Show", "season": 1, "episode": 2})
    assert first["covered_through"] == "season 1, episode 2"
    assert "S1E3" not in first["text"]
    later = call(client, "catch_me_up", {"show": "The Test Show", "season": 2, "episode": 1})
    assert later["covered_through"] == "season 2, episode 1"


def test_get_previously_on_needs_a_position_and_crosses_seasons(client):
    out = call(client, "get_previously_on", {"show": "The Test Show", "season": 2, "episode": 1})
    assert "S1E3 happens." in out["text"] and "S1E2 happens." in out["text"]
    assert "S2E1" not in out["text"]
    bad = rpc(
        client, "tools/call", {"name": "get_previously_on", "arguments": {"show": "The Test Show"}}
    )
    assert bad["result"]["isError"]  # season and episode are required


def test_out_of_range_position_gets_a_spoken_error(client):
    out = call(client, "catch_me_up", {"show": "The Test Show", "season": 1, "episode": 9})
    assert out["text"] == "Season 1 of The Test Show has 3 episodes."


def test_unlisted_host_is_rejected_unless_allowed(shows, monkeypatch):
    """Without this, the server would answer 421 behind any tunnel or cloud URL."""
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    with TestClient(build_app(shows)) as c:
        resp = c.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=HEADERS
        )
        assert resp.status_code == 421

    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    with TestClient(build_app(shows)) as c:
        resp = c.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=HEADERS
        )
        assert resp.status_code == 200

    monkeypatch.setenv("ALLOWED_HOSTS", "*")
    with TestClient(build_app(shows)) as c:
        resp = c.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=HEADERS
        )
        assert resp.status_code == 200
