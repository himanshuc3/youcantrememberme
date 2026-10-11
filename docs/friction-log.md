# Friction log (Amazon developer tools)

The rules give up to a 10% score bonus for friction logs. Fields per entry: task, steps,
expected vs actual, severity, workaround, suggestion.

> **Status: DRAFT.** These entries come from reading the docs, not yet from running the
> CLI or the simulator. Re-verify each one against the live docs, and replace with first-hand
> experience as we go, before submitting.

## 1. Finding how to install the `alexa-ai` CLI
- **Task:** install the CLI to follow the MCP quickstart.
- **Steps:** opened the MCP Toolkit Quickstart, then the Alexa AI CLI Reference.
- **Expected:** an install command (e.g. `npm i -g ...`) on or next to the quickstart.
- **Actual:** the quickstart tells you to complete "Set Up Your Development Environment" and
  starts at `alexa-ai configure`. The CLI Reference has no install instructions. The real
  install (on the setup page) needs an AWS account, an IAM user that can assume a role in an
  Amazon-owned account, AWS profiles, CodeCommit git config and a 12-hour CodeArtifact npm
  login before `npm install -g @alexa-ai/cli`.
- **Severity:** medium (a hello-world developer without AWS is blocked).
- **Workaround:** found the setup page by following the sidebar.
- **Suggestion:** a 3-line summary on the quickstart ("requires an AWS account; ~10 min") with
  a prominent link, and a note in the CLI reference.

## 2. Authentication docs and hackathon guidance disagree on `WWW-Authenticate`
- **Task:** decide what an auth-protected MCP server must return on 401.
- **Actual:** the quickstart says to return 401 *without* a `WWW-Authenticate` header and
  lists "`WWW-Authenticate` in 401 responses" as not yet supported, while the hackathon
  blog post says to return 401 *with* a `WWW-Authenticate` header. MCP's own spec points
  clients to the resource-metadata URL via that header.
- **Severity:** low–medium (affects anyone implementing auth).
- **Suggestion:** state the current expected behaviour in one place and say when it will change.

## 3. Add-on category unclear for non-ride-booking add-ons
- **Task:** scaffold an entertainment (TV recap) MCP add-on.
- **Actual:** the MCP add-on page lists only `ride_booking` as a category for `--category`;
  it isn't clear whether the flag is optional or whether other kinds of add-on are allowed.
- **Severity:** medium (could block listing).
- **Suggestion:** document the uncategorized path explicitly.

## 4. Response-size and latency limits not specified
- **Task:** size voice responses.
- **Actual:** the docs state a 500 ms round-trip limit but no limit on tool-response length,
  and it isn't clear what "round trip" includes.
- **Severity:** low.
- **Suggestion:** document the max response size and what the 500 ms measures.
