# Catch Me Up (youcantrememberme)

Spoiler-safe TV catch-up as an **Alexa+ MCP add-on**, built for the
[Build, Ship, Shape: Amazon Developer Hackathon 2026](https://amazonappdev2026.devpost.com/)
(Alexa+ track, deadline Oct 23, 2026). Tell it a show and how far you got; it speaks a short
recap of the story so far, never revealing anything past that episode.

## How it works
Summaries are computed **offline**; the server only looks them up, so answers are fast
(Alexa+ requires < 500 ms).

```
pipeline/  TVmaze (+Wikipedia) -> per-episode digests -> per-season digests -> data/shows/*.json
server/    MCP server (Streamable HTTP): find_show, catch_me_up, get_recap, get_previously_on
common/     shared models + storage
evals/     spoiler-leak and speakability checks
addon-package/  Alexa add-on listing (addon.json, images, privacy/terms)
web_demo/  fallback client that mimics Alexa+ calling the server
examples/  fictional offline demo show (no network needed)
scripts/   run_demo.sh starts the server + web demo
```

Spoiler safety (see `server/assemble.py`, covered by `tests/test_assemble.py`):
an episode digest only ever sees that episode; a season digest is used only when the requested
range covers the *whole* season; long ranges drop the *oldest* events, never the newest.

## Quick start (fresh clone)
Prerequisites: [`uv`](https://docs.astral.sh/uv/) (it fetches Python 3.11+ itself) and
[`task`](https://taskfile.dev). Docker is only needed for the DynamoDB Local steps.
```bash
git clone https://github.com/himanshuc3/youcantrememberme && cd youcantrememberme
task setup          # creates .venv and installs dependencies; nothing to activate
task test           # automated tests (no server, no Docker, no network)
task server         # MCP server on :8000 with the offline demo data
task inspect        # MCP Inspector UI, preconnected to it (primary way to test the tools)
task inspect:smoke  # or: scripted walkthrough of every tool in the terminal
task demo           # demos only: server + chat-style web UI -> http://127.0.0.1:8080
```
Everything at once, on DynamoDB Local (what production uses), with on-demand fetching:
```bash
task dev            # DynamoDB (Docker) + MCP server + worker + Inspector; Ctrl+C stops the lot
```
Edit anything under `server/`, `common/` or `pipeline/` and the server/worker restart by
themselves; the Inspector stays connected (re-run the tool call). Then in the Inspector call
`catch_me_up` with `show` = a real show we haven't stored, e.g. "Severance": the reply says it's
being fetched, the worker pulls it from TVmaze into DynamoDB (seconds in the default
`baseline` mode), and asking again returns the recap. `task dev WORKER_MODE=llm` builds
recaps with Claude on Bedrock instead (needs AWS credentials). `task db:down` / `task db:reset`
stop or wipe the local database.
Configuration: copy [`.env.example`](.env.example) to `.env` (git-ignored; `task` loads it) to
change host/port, limits, Bedrock model, AWS profile. Every variable is documented there.
`task` lists every task. Without Task/uv: `python3 -m venv .venv && . .venv/bin/activate &&
pip install -e ".[dev]" && pytest && scripts/run_demo.sh`.
Full instructions, a scripted walkthrough, real shows, Bedrock, tunnels:
**[docs/testing.md](docs/testing.md)**. How it works: **[docs/how-it-works.md](docs/how-it-works.md)**.

Docs: [Bedrock setup](docs/bedrock.md) · [alexa-ai CLI on Pop!_OS](docs/setup-alexa-ai-cli-popos.md) ·
[hackathon requirements](docs/hackathon-requirements.md) · [friction log](docs/friction-log.md) ·
[status and open questions](docs/day1-findings.md).

## Tools
| Tool | Use |
|---|---|
| `find_show` | is a show available, and how many seasons/episodes |
| `catch_me_up` | recap from the start through the episode the user last watched (show, season, episode) |
| `get_recap` | recap between two explicit points |
| `get_previously_on` | "previously on": the last few episodes before the one they're about to watch |

The server is **stateless and profile-agnostic**: it stores nothing about users, so there is no
login, account linking or per-user data. The caller (Alexa+) passes the show and the episode the
user says they have reached on every call.

## Storage backends
Digests and the on-demand job queue go through one interface
([`common/backend.py`](common/backend.py)). Pick it with `STORAGE_BACKEND`:

| Value | Where | Use |
|---|---|---|
| `file` (default) | JSON files under `$DATA_DIR` | tests, offline demo |
| `dynamodb` | tables `<prefix>shows`, `<prefix>jobs` (`DYNAMODB_TABLE_PREFIX`, `AWS_REGION`, `DYNAMODB_ENDPOINT_URL`) | DynamoDB Local in development, AWS in production |

```bash
task db:up                       # DynamoDB Local + tables + demo data (scripts/dynamo_local.sh)
task server:dynamo               # server against it
# or by hand:
export STORAGE_BACKEND=dynamodb DYNAMODB_ENDPOINT_URL=http://localhost:8001 \
       AWS_REGION=us-east-1 AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local
python -m common.migrate --from file --src-dir data --create-tables   # copy data/ into DynamoDB
python -m pipeline.run --mode baseline "Severance"
```
DynamoDB tables have a single string hash key `id` (`--create-tables` creates them for
DynamoDB Local; production should provision them in IaC).
The raw-text and LLM caches stay on local disk under `$DATA_DIR/cache` in every mode.

## Shows we don't have yet (on demand)
With `ON_DEMAND=1` the server answers an unknown show honestly, checks the name against TVmaze,
and queues it (one job per show, a daily cap). A worker fills the store:
```bash
ON_DEMAND=1 python -m server.main            # enqueues misses
python -m pipeline.worker                    # --mode llm for Bedrock digests, --once to drain
```
Code: [`server/on_demand.py`](server/on_demand.py), [`common/jobs.py`](common/jobs.py),
[`pipeline/worker.py`](pipeline/worker.py). Limits: `ON_DEMAND_DAILY_LIMIT` (20), `ON_DEMAND_USER_LIMIT` (3).

## License
[MIT](LICENSE).

## Attribution
Episode data from [TVmaze](https://www.tvmaze.com) (CC BY-SA 4.0).
