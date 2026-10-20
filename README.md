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
server/    MCP server (Streamable HTTP): find_show, save_progress, catch_me_up, get_recap, get_previously_on
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
task demo           # MCP server + web demo on offline data -> http://127.0.0.1:8080
```
Against DynamoDB Local (what production uses), in separate terminals:
```bash
task db:up          # DynamoDB Local in Docker on :8001, tables created, demo data seeded
task server:dynamo  # MCP server on :8000 using DynamoDB
task mcp:list       # prove it answers (or `task inspect` for the MCP Inspector UI)
task web            # optional: web demo on :8080 pointed at that server
```
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
| `save_progress` | remember "I'm through season 2, episode 4" across conversations |
| `catch_me_up` | recap from the start through the remembered episode (no arguments needed) |
| `get_recap` | recap between two explicit points |
| `get_previously_on` | recap of the last few episodes (explicit, or from remembered progress) |

Who is "the user" is decided in [`server/identity.py`](server/identity.py) (guest / demo header /
OAuth account linking). See [docs/identity-and-account-linking.md](docs/identity-and-account-linking.md).

## Storage backends
Digests, per-user progress and the on-demand job queue go through one interface
([`common/backend.py`](common/backend.py)). Pick it with `STORAGE_BACKEND`:

| Value | Where | Use |
|---|---|---|
| `file` (default) | JSON files under `$DATA_DIR` | tests, offline demo |
| `dynamodb` | tables `<prefix>shows`, `<prefix>users`, `<prefix>jobs` (`DYNAMODB_TABLE_PREFIX`, `AWS_REGION`, `DYNAMODB_ENDPOINT_URL`) | DynamoDB Local in development, AWS in production |

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
and queues it (one job per show, daily and per-user caps). A worker fills the store:
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
