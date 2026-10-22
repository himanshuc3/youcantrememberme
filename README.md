# Catch Me Up (youcantrememberme)

Spoiler-safe TV catch-up as an **Alexa+ MCP add-on**, built for the
[Build, Ship, Shape: Amazon Developer Hackathon 2026](https://amazonappdev2026.devpost.com/)
(Alexa+ track, deadline Oct 23, 2026). Tell it a show and how far you got; it speaks a short
recap of the story so far, never revealing anything past that episode.

## How it works
Summaries are computed **offline**; the server only looks them up, so answers are fast
(Alexa+ requires < 500 ms).

```
pipeline/  TVmaze (+Wikipedia) -> per-episode digests -> per-season digests -> DynamoDB (shows table)
server/    MCP server (Streamable HTTP): find_show, catch_me_up, get_recap, get_previously_on
common/     shared models + storage
evals/     spoiler-leak and speakability checks
addon-package/  Alexa add-on listing (addon.json, images, privacy/terms)
web_demo/  fallback client that mimics Alexa+ calling the server
examples/  fictional demo show (JSON fixture, loaded into DynamoDB by `task db:up`)
scripts/   run_demo.sh starts the server + web demo
```

Spoiler safety (see `server/assemble.py`, covered by `tests/test_assemble.py`):
an episode digest only ever sees that episode; a season digest is used only when the requested
range covers the *whole* season; long ranges drop the *oldest* events, never the newest.

## Quick start (fresh clone)
Prerequisites: [`uv`](https://docs.astral.sh/uv/) (it fetches Python 3.11+ itself),
[`task`](https://taskfile.dev), Docker (DynamoDB Local) and Node (the MCP Inspector).
```bash
git clone https://github.com/himanshuc3/youcantrememberme && cd youcantrememberme
task setup          # creates .venv and installs dependencies; nothing to activate
task test           # automated tests: in-memory DynamoDB, so no Docker or network needed
task dev            # DynamoDB Local (Docker) + MCP server + worker + Inspector; Ctrl+C stops it all
```
Storage is **always DynamoDB** (DynamoDB Local in Docker here, AWS in production); there is no
file fallback. `task dev` loads the fictional demo show, so you can start testing immediately in
the Inspector (primary way to test the tools). Edit anything under `server/`, `common/` or
`pipeline/` and the server/worker restart by themselves; re-run the tool call in the Inspector.

Ask for a real show that isn't stored, e.g. `catch_me_up` with `show` = "Severance", season 1,
episode 2: the reply says it's being fetched, the worker pulls it from TVmaze into DynamoDB
(seconds in the default `baseline` mode), and asking again returns the recap. `task dev
WORKER_MODE=llm` builds recaps with Claude on Bedrock instead (needs AWS credentials).

The pieces separately: `task db:up` (DynamoDB Local + tables + demo show), `task server`,
`task worker`, `task inspect` or `task inspect:smoke`, `task db:show` (look inside the tables),
`task demo` (demos only: chat-style web UI at http://127.0.0.1:8080), `task db:down` /
`task db:reset` (stop / wipe the local database).
Configuration: copy [`.env.example`](.env.example) to `.env` (git-ignored; `task` loads it) to
change host/port, limits, Bedrock model, AWS profile. Every variable is documented there.
`task` lists every task.
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

## Storage
Digests and the on-demand job queue live in **DynamoDB**, behind one small interface
([`common/backend.py`](common/backend.py)): tables `<prefix>shows` and `<prefix>jobs`
(`DYNAMODB_TABLE_PREFIX`, `AWS_REGION`, `DYNAMODB_ENDPOINT_URL`), each with a single string hash
key `id` and the document stored as JSON in `data`. `task db:up` runs DynamoDB Local and creates
the tables; production should provision them in IaC. Tests use `moto` (in memory).
```bash
task db:up                                   # DynamoDB Local + tables + demo show
task pipeline -- "Severance"                 # batch-build a show into DynamoDB
task db:show -- shows                        # what's stored
```
The pipeline's raw-text and LLM caches are plain files under `$DATA_DIR/cache` (default `./data`);
they are a download cache, not a data store.

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
