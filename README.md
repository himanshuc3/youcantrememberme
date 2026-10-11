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
server/    MCP server (Streamable HTTP): find_show, get_recap, get_previously_on
common/     shared models + storage
evals/     spoiler-leak and speakability checks
addon-package/  Alexa add-on listing (addon.json, images, privacy/terms)
web-demo/  fallback client that mimics Alexa+ calling the server
```

Spoiler safety (see `server/assemble.py`, covered by `tests/test_assemble.py`):
an episode digest only ever sees that episode; a season digest is used only when the requested
range covers the *whole* season; long ranges drop the *oldest* events, never the newest.

## Quick start
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest

python -m pipeline.run --mode baseline "Severance" "The Bear"   # fetch from TVmaze, no LLM
python -m server.main                                           # http://127.0.0.1:8000/mcp
```

Status and open questions: [`docs/day1-findings.md`](docs/day1-findings.md).

## Attribution
Episode data from [TVmaze](https://www.tvmaze.com) (CC BY-SA 4.0).
