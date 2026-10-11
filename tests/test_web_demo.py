from fastapi.testclient import TestClient

from web_demo.app import create_app


def make_client(fake):
    return TestClient(create_app(fake))


def test_message_becomes_a_tool_call_and_returns_the_spoken_text():
    seen = []

    async def fake(tool, args, user):
        seen.append((tool, args, user))
        return {"text": "Season 1. A recap.", "covered_through": "season 1, episode 5"}

    out = make_client(fake).post(
        "/api/ask", json={"text": "Recap The Bear through season 1", "user": "u1"}
    )
    body = out.json()
    assert seen == [("get_recap", {"show": "The Bear", "to_season": 1}, "u1")]
    assert body["spoken"] == "Season 1. A recap."
    assert body["tool"] == "get_recap" and body["understood"]


def test_unrecognised_input_gets_help_and_no_tool_call():
    async def fake(tool, args, user):
        raise AssertionError("must not be called")

    body = make_client(fake).post("/api/ask", json={"text": "blah"}).json()
    assert body["understood"] is False and "Try:" in body["spoken"]


def test_server_down_is_reported_not_a_500():
    async def fake(tool, args, user):
        raise ConnectionError("boom")

    resp = make_client(fake).post("/api/ask", json={"text": "catch me up"})
    assert resp.status_code == 200
    assert resp.json()["error"] is True


def test_index_page_is_served():
    async def fake(tool, args, user):
        return {}

    resp = make_client(fake).get("/")
    assert resp.status_code == 200 and "Catch Me Up" in resp.text
