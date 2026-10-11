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

## Quick start (offline, no keys)
```bash
python3 -m venv .venv && . .venv/bin/activate     # Python 3.11+
pip install -e ".[dev,web]"
pytest                                            # 64 tests
scripts/run_demo.sh                               # then open http://127.0.0.1:8080
```
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

## License
[MIT](LICENSE).

## Attribution
Episode data from [TVmaze](https://www.tvmaze.com) (CC BY-SA 4.0).
