# Friction log (Amazon developer tools)

The rules give up to a 10% score bonus for friction logs. Fields per entry: task, steps,
expected vs actual, severity, workaround, suggestion.

> **Status: DRAFT.** Entries 1-3 come from reading the docs, not yet from running the
> CLI or the simulator (entry 4 is first-hand). Re-verify each one against the live docs, and replace with first-hand
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
- **Actual:** the quickstart says to return 401 _without_ a `WWW-Authenticate` header and
  lists "`WWW-Authenticate` in 401 responses" as not yet supported, while the hackathon
  blog post says to return 401 _with_ a `WWW-Authenticate` header. MCP's own spec points
  clients to the resource-metadata URL via that header.
- **Severity:** low–medium (affects anyone implementing auth).
- **Suggestion:** state the current expected behaviour in one place and say when it will change.

## 3. Add-on category unclear for non-ride-booking add-ons

- **Task:** scaffold an entertainment (TV recap) MCP add-on.
- **Actual:** the MCP add-on page lists only `ride_booking` as a category for `--category`;
  it isn't clear whether the flag is optional or whether other kinds of add-on are allowed.
- **Severity:** medium (could block listing).
- **Suggestion:** document the uncategorized path explicitly.

## 4. Amazon Bedrock refuses every model call even with AWS credits on the account

First-hand (observed while building and testing this project, not from the docs).

- **Task:** call Claude on Amazon Bedrock, both for the offline recap pipeline and for the web
  demo's chat agent, using the AWS credits we received for the hackathon.
- **Steps:**
  1. Created a Bedrock API key in the console and set `AWS_BEARER_TOKEN_BEDROCK`.
  2. Called the Messages-API endpoint (`AnthropicBedrockMantle`, `bedrock-mantle.us-east-1.api.aws`)
     with each model it lists.
  3. Called the standard Bedrock API (`InvokeModel` through the Anthropic SDK, and boto3
     `converse`) with `anthropic.claude-sonnet-5-5` and its `us.` / `global.` inference profiles.
  4. Tried non-Anthropic models (`amazon.nova-lite-v1:0`, `amazon.nova-micro-v1:0`,
     `mistral.mistral-7b-instruct-v0:2`), then the Bedrock playground in the console.
- **Expected:** a funded account can call the models it lists as available.
- **Actual:**
  - Standard API, every model and every ID form: `Error 002: Access to Bedrock models is not
    allowed for this account`. The playground shows the same error. Amazon's own Nova models fail
    identically, so it isn't a per-model or Anthropic use-case approval problem.
  - `ListFoundationModels` and `ListInferenceProfiles` still work and show the Claude models as
    `ACTIVE` for the account, so the console and API suggest the models are available.
  - Messages-API endpoint: its model list returned 6 Claude models, and calling each gave `403
    ... is not available for this account`. It does not list `anthropic.claude-sonnet-5-5` at
    all (404 "does not exist"), although the standard API lists that model, as an inference
    profile only, so the two endpoints disagree about which models exist.
  - The Bedrock API key authenticated only in `us-east-1`; `us-west-2`, `us-east-2`, `eu-west-1`
    and `ap-northeast-1` returned 401. The docs we found don't say keys are region-bound.
  - Nothing we found documents "Error 002", so we could not tell whether the cause is billing or
    account status, a free or restricted plan, an Organizations policy, or something else. We
    could not confirm that the credits are what is missing.
- **Severity:** high. It blocked every use of an LLM on AWS: the Claude-written recap pipeline
  (`--mode llm`) has never run against real Bedrock output, and the web demo's Bedrock agent could
  not be tested.
- **Workaround:** made the web demo's LLM provider pluggable (`WEB_DEMO_LLM`): Anthropic API,
  any OpenAI-compatible API (OpenRouter, local Ollama), or an offline rules parser. Recaps for real
  shows use TVmaze's own blurbs (`--mode baseline`) instead of Claude-written digests.
- **Suggestions:**
  - Make the error actionable: say what is wrong (billing, plan, policy, or region) and link to
    the fix, instead of a bare "Error 002".
  - Have the console and `ListFoundationModels` reflect whether the account may actually invoke a
    model, so "ACTIVE" doesn't imply "usable".
  - When credits are granted for a hackathon, document any extra step needed to enable model
    invocation and how to check eligibility.
  - Keep the model lists of the Messages-API endpoint and the standard API consistent, or
    document the difference and how model IDs map between them.
  - State on the API-keys page that a key is tied to one region.
