# How to run and test it

Everything in sections 1–4 works **offline, with no accounts or API keys**, using the
fictional demo show "The Lighthouse Keepers" in `examples/demo-data/`.

## 0. Prerequisites (Pop!_OS)
- **Python 3.11 or newer.** Check with `python3 --version`. Pop!_OS 22.04 ships 3.10, which
  is too old. Pop!_OS 24.04 ships 3.12, which is fine. For 3.10, the easiest fix is
  [`uv`](https://docs.astral.sh/uv/), which downloads a Python for you:
  `curl -LsSf https://astral.sh/uv/install.sh | sh` then `uv venv --python 3.12 .venv`.
- `python3-venv` if you use plain venv: `sudo apt install python3-venv`.
- Node.js is needed for the MCP Inspector (section 3) and `alexa-ai`.

```bash
git clone https://github.com/himanshuc3/youcantrememberme && cd youcantrememberme
git checkout claude/stoic-cori-pkma81
python3 -m venv .venv && . .venv/bin/activate     # or: uv venv --python 3.12 .venv
pip install -e ".[dev]"
```

## 1. Automated tests (64)
```bash
pytest                      # all of them, about a second
ruff check . && ruff format --check .
```
What they cover:
| File | What it proves |
|---|---|
| `test_assemble.py` | spoiler-safe assembly: nothing past the requested episode, season digests only for fully covered seasons, oldest events dropped first |
| `test_demo_data.py` | a recap "through S1E3" never mentions the S1E5 twist; through the end of season 1 it does |
| `test_progress.py` | remembered progress persists, is per user, rejects non-existent episodes |
| `test_digest_llm.py` | the LLM prompt for an episode contains only that episode + earlier digests (fake model, no AWS) |
| `test_http_e2e.py` | real Streamable HTTP: protocol `2025-11-25`, tool list/descriptions, calls, per-user progress, Host-header protection |
| `test_intent.py`, `test_web_demo.py` | the web demo's sentence parser and API |

## 2. The web demo (for demos only; use the Inspector in section 3 for testing)
```bash
scripts/run_demo.sh
```
Open <http://127.0.0.1:8080>. It starts the MCP server on `:8000` and the demo page on
`:8080`. Press Ctrl+C to stop both. Click the example chips or type, in this order:

1. `Do you have The Lighthouse Keepers?` → lists seasons and episode counts.
2. `Catch me up` → it asks where you got to (nothing is remembered yet).
3. `I'm on season 1 episode 3 of The Lighthouse Keepers` → saved.
4. `Catch me up` → recap of episodes 1–3 only. **Check it never mentions the father.**
5. `Previously on` → the last two episodes you watched.
6. `Recap The Lighthouse Keepers through season 1` → full season 1 recap. **Now it does
   mention the father**, because you asked for the whole season. That contrast is the
   spoiler-safety guarantee.
7. Click "MCP call and result" under any answer to see the exact `tools/call` and reply.
8. Open the page in a private window (a different "person"): `Catch me up on The Lighthouse Keepers`
   asks where you got to. Each browser has its own remembered progress.

The page's language understanding is a small rule-based parser (`web_demo/intent.py`). It
understands the phrasings above, not free speech. On a real device Alexa+ does that part.

## 3. Test the MCP server directly (what Alexa+ talks to)
Start only the server: `python -m server.main` (port 8000; `IDENTITY_MODE=header` if you want
per-user profiles via the `X-Demo-User` header).

With curl:
```bash
H='-H Content-Type:application/json -H Accept:application/json,text/event-stream'
curl -s $H http://127.0.0.1:8000/mcp -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
curl -s $H http://127.0.0.1:8000/mcp -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_recap","arguments":{"show":"lighthouse keepers","to_season":1,"to_episode":3}}}'
```
By default it reads `./data`. For the demo show use `DATA_DIR=examples/demo-data python -m server.main`.

**`task dev` is the one-command setup** (DynamoDB Local + server + worker + Inspector, with
auto-restart on code changes and on-demand fetching on). The individual tasks below do the same
piecemeal. **The MCP Inspector is the primary way to test the server** (faster than the chat demo, and it
shows raw tool inputs and outputs). Needs Node. With `task server` running (or `task server:dynamo`):
```bash
task inspect         # web UI, already connected to http://127.0.0.1:8000/mcp (Streamable HTTP);
                     # open the URL it prints (it includes an auth token), go to Tools, call them
task inspect:list    # tools/list from the terminal
task inspect:call -- find_show query="The Lighthouse Keepers"
task inspect:smoke   # scripted walkthrough of every tool, as a fresh user
```
The Inspector is pinned (`INSPECTOR` in the Taskfile) and sends `X-Demo-User: inspector`, so
saved progress belongs to that user. Change it with `task inspect INSPECT_USER=alice`, or
edit the header in the UI, to test per-user behaviour. Without Task:
`npx @modelcontextprotocol/inspector@2.11.0 --web --transport http --server-url http://127.0.0.1:8000/mcp --header "X-Demo-User: inspector"`.

## 4. Real shows (needs internet, no keys)
```bash
python -m pipeline.run --mode baseline "Severance" "The Bear"   # TVmaze blurbs → data/
DATA_DIR=data scripts/run_demo.sh
```
Baseline recaps are just TVmaze's one-line blurbs. Good enough to see it work, thin as a
product.

## 5. Better recaps with Claude on Bedrock (needs AWS)
See [bedrock.md](bedrock.md). Short version:
```bash
pip install -e ".[pipeline]"
AWS_PROFILE=<profile> python -m pipeline.run --mode llm "Severance"
```
This is the one path that has **not** been run for real yet (no AWS credentials in my
sandbox; tests use a fake model). Expect to debug an access or parameter issue on first run.

## 6. Reach it from the internet (needed for Alexa+)
```bash
python -m server.main &
cloudflared tunnel --url http://127.0.0.1:8000       # prints https://<random>.trycloudflare.com
ALLOWED_HOSTS=<random>.trycloudflare.com python -m server.main    # restart with the host allowed
```
**Why `ALLOWED_HOSTS`:** the MCP SDK rejects requests whose `Host` header isn't on a list
(HTTP 421 "Invalid Host header", DNS-rebinding protection). Without this the server works
on localhost and fails behind any tunnel or cloud URL. `ALLOWED_HOSTS=*` turns the check off
(fine for a throwaway tunnel, not for a long-lived deployment).

## 7. Real Alexa+ (needs accounts)
Follow [setup-alexa-ai-cli-popos.md](setup-alexa-ai-cli-popos.md), then
`alexa-ai new mcp ...`, `alexa-ai deploy`, and test in Amazon's web simulator
([addon-package/README.md](../addon-package/README.md)). Not done yet.

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| `requires a different Python` on install | need Python ≥ 3.11 (see section 0) |
| `421 Invalid Host header` | set `ALLOWED_HOSTS` to the hostname you are using |
| Web demo says "couldn't reach the MCP server" | the server isn't running on `MCP_URL` (default `http://127.0.0.1:8000/mcp`) |
| "I don't have recaps for that show yet" | that show isn't in `DATA_DIR`; run the pipeline or use the demo data |
| Progress forgotten after restart (demo) | different `DATA_DIR` or browser; progress lives in `<DATA_DIR>/users/` |
