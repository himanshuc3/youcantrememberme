"""Fallback demo client that mimics how Alexa+ calls the MCP server. STUB.

    pip install -e ".[web]"
    uvicorn app:app --app-dir web-demo --port 8080      # MCP server must be on :8000

Plan:
  * GET  /            -> static/index.html (chat-style page)
  * POST /api/ask     -> {"text": "..."} -> picks a tool + args, calls the MCP server with the
                         Python MCP client (Streamable HTTP, MCP_URL env var), returns the
                         tool call and the recap so the page can show both
  * Tool picking: a tiny rule-based parser is enough for the demo; optionally an LLM.
  * Browser speechSynthesis reads the recap aloud.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI(title="Catch Me Up: web demo")
STATIC = Path(__file__).parent / "static"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
