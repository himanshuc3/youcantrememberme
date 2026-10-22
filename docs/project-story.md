# Catch Me Up

**Spoiler-safe TV recaps for Alexa+, served by an MCP server.**

Ask: *"Alexa, catch me up on The Office, I'm on season 1, episode 4."* You get a short spoken recap of everything up to that episode and nothing after it.

## Inspiration
Everyone has come back to a show after a few months and forgotten what happened. The usual fixes both fail: searching online spoils later episodes, and rewatching takes hours. Voice is a natural fit because you can ask while you're finding the remote. The hard part is a recap that is guaranteed not to spoil, and that was the problem we wanted to solve.

## What it does
- **`catch_me_up`** recaps from the start through the episode you last watched.
- **`get_recap`** recaps any range you name.
- **`get_previously_on`** gives a short "previously on…" before the episode you're about to watch.
- **`get_characters`** is a who's who, or "who is Mara?", limited to what's been revealed so far.
- **`find_show`** checks availability.
- **Styles:** you can ask for a recap "like a noir detective" or with another show's cast. The server hands the caller's LLM strict rewrite instructions that forbid adding plot.
- **Unknown shows:** it says it's fetching the show, a background worker builds it, and the next ask works.
- **No user data:** the server remembers nothing about you, so there are no accounts or personal data to protect.

## How we built it
- **Offline pipeline.** Episode data comes from TVmaze. Each episode digest is built from that episode and the few before it, never from anything later. Season digests are built only from complete seasons.
- **Online server.** A Python MCP server (Streamable HTTP, stateless) only looks up stored digests and stitches them together, which keeps answers well inside Alexa+'s 500 ms budget. It never calls an LLM at request time.
- **Storage.** DynamoDB only: DynamoDB Local in Docker for development, `moto` in tests, AWS in production.
- **On-demand worker.** A deduplicated job queue with daily caps. A worker fills the store, and a refresh path re-fetches a show when the requested episode is beyond what we stored.
- **Spoiler-safe characters.** A character counts as introduced only once a digest up to your position names them.
- **Demo.** A chat page where an LLM stands in for Alexa+, reading our tool list over MCP and choosing and calling tools itself.
- **Tooling.** `uv` and Task, `pytest` (103 tests, including ones that plant a twist and check it never leaks), and the MCP Inspector for fast testing.

## What we learned
- **Spoiler safety is an architecture problem.** Prompting a model to "avoid spoilers" isn't a guarantee. Making it impossible by construction is.
- **Voice changes the design.** A hard latency budget pushed all the heavy work offline.
- **Tool descriptions are the interface.** The LLM chooses tools and fills arguments from our docstrings, so clear, distinct tools matter more than clever code.
- **Stateless is a feature.** Dropping per-user progress removed the need for authentication, account linking and stored personal data.
- **Even a harmless feature can leak.** A cast list quietly reveals characters introduced later, and the same reply has to be given for "not yet introduced" and "doesn't exist".

## Challenges
- **Identity.** Alexa+ sends no user id, and real identity needs OAuth account linking. We first built remembered progress, then removed it for a stateless design.
- **Thin source text.** TVmaze summaries are only a sentence or two. The Claude-written digests exist in code but we haven't yet run them against real Bedrock output.
- **Bedrock access.** Our AWS account returned "Error 002: Access to Bedrock models is not allowed", even for Amazon's own models. We made the demo's LLM provider pluggable, so it also runs on the Anthropic API, OpenRouter or local Ollama. Free OpenRouter models rate-limited us.
- **A fast-moving SDK.** MCP 2.x renamed `FastMCP` and changed client details, and model IDs differ between Bedrock APIs.
- **Honest scope.** The Alexa+ add-on registration, the hosted AWS deployment and the privacy and terms URLs are still to do. The Wikipedia plot source is a stub.

## What's next
Richer summaries from Wikipedia plots and Claude, deploying the server on Lambda or App Runner, registering the add-on, and moving the job queue to SQS so more than one worker can run.

*Episode data: TVmaze (CC BY-SA 4.0).*
