# Identity and remembered progress

Remembered progress (`save_progress` → `catch_me_up`) needs to know *who* is asking.

## What Amazon's docs say
- Alexa+ puts **no user id** in MCP requests. `tools/call` carries just the tool name and
  arguments. The lifecycle page ties a "session" to the customer's earlier Alexa+
  conversations but gives no session id or user header.
- A user's identity reaches the server only through **account linking** (optional):
  Alexa adds the customer's OAuth access token to every request. The docs say the server
  "uses it to identify the customer", but they **don't document the token's claims or
  the user-id format**. Per the SDK docs, trust only a *verified* principal.
- Account linking requires **your own OAuth 2.1 authorization server** (authorization-code
  flow + PKCE S256, refresh tokens), metadata at `/.well-known/oauth-authorization-server`,
  protected-resource metadata, 401/403 on unauthenticated tool calls, then
  `alexa-ai configure-account-linking`. Dynamic Client Registration is not supported.

## What is built (`IDENTITY_MODE`)
| Mode | Who counts as the user | Use |
|---|---|---|
| `guest` (default) | everyone shares one profile | single-person demo |
| `header` | the `X-Demo-User` request header | web demo, one profile per browser. **Never in production**: a header is client input, not proof of identity |
| (always first) | the SDK-verified OAuth principal | works once a token verifier is configured |

Progress is stored per user in `data/users/` (user id hashed for the file name). On AWS
Lambda the disk is ephemeral, so deployment needs a DynamoDB-backed `ProgressStore`.

## Next step: real account linking (not started)
Smallest credible route, **unverified**: Amazon Cognito as the authorization server (it
supports the code flow with PKCE and refresh tokens, and fits the AWS Builder story). Open
questions to check before committing to it:
1. Alexa requires metadata at `/.well-known/oauth-authorization-server`; Cognito serves its
   own discovery document elsewhere, so we'd probably publish a small metadata file from
   our server that points at Cognito's endpoints.
2. Which OAuth client id/redirect URIs Alexa registers (see `alexa-ai
   configure-account-linking`).
3. Wire a token verifier into `MCPServer` (it has `auth` and `token_verifier` options) so
   `authenticated_principal` returns the Cognito `sub`.

Rough cost: 1–2 days. Without it the feature still works for a single-user demo and in the
web demo; with it, multi-user "remembers you" works on a real Alexa+ device.
