"""End to end over real HTTP: JSON-RPC `tools/call` against the Streamable HTTP app, with
the demo-identity header, exactly as a remote client (Alexa+ or the web demo) would send it."""

import json

import pytest
from starlette.testclient import TestClient

from server.main import build_app

HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


@pytest.fixture
def client(stores, monkeypatch):
    monkeypatch.setenv("IDENTITY_MODE", "header")
    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    shows, progress = stores
    with TestClient(build_app(shows, progress)) as c:
        yield c


def rpc(client, method, params=None, user=None, id_=1):
    headers = dict(HEADERS)
    if user:
        headers["X-Demo-User"] = user
    body = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        body["params"] = params
    resp = client.post("/mcp", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def call(client, tool, args, user=None):
    out = rpc(client, "tools/call", {"name": tool, "arguments": args}, user)
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
        "save_progress",
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


def test_progress_persists_across_requests_and_is_per_user(client):
    call(
        client,
        "save_progress",
        {"show": "The Test Show", "season": 1, "episode": 2},
        user="alice",
    )
    alice = call(client, "catch_me_up", {}, user="alice")
    assert alice["covered_through"] == "season 1, episode 2"

    bob = call(client, "catch_me_up", {"show": "The Test Show"}, user="bob")
    assert bob["needs_progress"]


def test_unlisted_host_is_rejected_unless_allowed(stores, monkeypatch):
    """Without this, the server would answer 421 behind any tunnel or cloud URL."""
    shows, progress = stores
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
    with TestClient(build_app(shows, progress)) as c:
        resp = c.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=HEADERS
        )
        assert resp.status_code == 421

    monkeypatch.setenv("ALLOWED_HOSTS", "testserver")
    with TestClient(build_app(shows, progress)) as c:
        resp = c.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=HEADERS
        )
        assert resp.status_code == 200

    monkeypatch.setenv("ALLOWED_HOSTS", "*")
    with TestClient(build_app(shows, progress)) as c:
        resp = c.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=HEADERS
        )
        assert resp.status_code == 200
