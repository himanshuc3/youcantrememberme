# Day 1 verification findings (2026-10-11)

## Confirmed
- **TVmaze** `GET /singlesearch/shows` and `/shows/:id/episodes` work with no key, and each
  episode has a `summary` field (HTML). Severance returned 19 episodes with summaries.
- **Python MCP SDK 2.3.0** installs from PyPI. It is a breaking change from 1.x:
  `FastMCP` is now `mcp.server.mcpserver.MCPServer`. `streamable_http_app(stateless_http=True,
  json_response=True)` serves `/mcp`, and the `initialize` handshake negotiates protocol
  `2025-11-25`, which is what Alexa+ requires.
- End to end locally (`pipeline.run` -> `data/` -> `server.main`): `tools/list` shows the three
  tools and `get_recap` answers in ~5 ms, far inside the 500 ms budget (lookup path only).

## Problems / decisions
- **TVmaze summaries are thin** (1-2 sentences, ~120 chars). Baseline recaps read like a
  list of blurbs. We need richer text (Wikipedia plot summaries) plus LLM digests.
- **Wikipedia API is untested**: this container's shared egress IP was rate-limited
  ("too many requests"). Needs a test from your machine/AWS with the proper User-Agent.
- **Devpost page returned 403** to the fetch tool, so the official rules and judging
  criteria are still unread. Please open the page and paste the rules/criteria (or confirm
  the deadline: Oct 23, 2026 12:00 PM PT per a third-party listing).
- **Add-on category**: the Alexa+ docs only list `ride_booking` as an MCP add-on category.
  Must confirm a general entertainment add-on is allowed.
- **Tool results** are returned as JSON text (`content[0].text`), not `structuredContent`.
  Returning typed models from the tools would fix that. Check how Alexa+ prefers it.
- **Lambda + Mangum + stateless MCP** is unverified (see `server/handler.py`). Fallback:
  container on AWS App Runner.
- **Not done**: `alexa-ai configure` (needs your Alexa developer account / browser login),
  LLM digest generation (provider not chosen), Wikipedia source, leak eval (web demo and Bedrock summarizer have since been built; see docs/how-it-works.md).

## Needs from you (updated)
1. Bedrock credentials and model access, to run the first real `--mode llm` pipeline.
2. Run `alexa-ai configure` on your machine (browser login) and confirm the add-on category question.
3. Decide: build real account linking (multi-user "remembers you" on a device) or keep the
   one-user demo. (Superseded: the server is now stateless and stores no per-user data.)
