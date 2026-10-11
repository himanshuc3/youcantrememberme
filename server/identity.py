"""Who is calling? Needed for per-user watch progress.

Alexa+ does not put a user id in MCP requests. Per Amazon's docs, a user's identity reaches
the server only through **account linking**: an OAuth access token Alexa adds to every
request once the customer has linked their account. Account linking needs an OAuth 2.1
authorization server (PKCE S256, refresh tokens) and is not built yet, so there are three
tiers, selected by `IDENTITY_MODE`:

* `guest` (default): every caller shares one "guest" profile. Fine for a one-person demo.
  Not fine for a real multi-user deployment.
* `header`: trust an `X-Demo-User` request header. Demo use only (the web demo uses it to
  give each browser its own profile). The MCP SDK's own docs warn that a header is client
  input, never a proof of identity, so never use this mode in production.
* `oauth`: use the SDK-verified principal (`authenticated_principal`). Today this returns
  nothing until a token verifier is configured on the server (the account-linking work);
  until then requests fall back to the guest profile.

An authenticated principal always wins over the other tiers.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import authenticated_principal

GUEST = "guest"
DEMO_HEADER = "x-demo-user"


def resolve_user_id(request_context: Any, headers: Any = None, mode: str | None = None) -> str:
    mode = mode or os.environ.get("IDENTITY_MODE", "guest")
    principal = authenticated_principal(request_context) if request_context is not None else None
    if principal:
        return f"oauth:{principal}"
    if mode == "header" and headers is not None:
        value = (headers.get(DEMO_HEADER) or "").strip()
        if value:
            return f"demo:{value[:64]}"
    return GUEST
