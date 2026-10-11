# How Catch Me Up works

## The idea in one paragraph
You paused a show months ago. You tell Alexa+ how far you got and it speaks a short recap of
the story so far, **never** revealing anything past that point. The trick that makes it both
fast and spoiler-safe: all summarizing happens **ahead of time**, one episode at a time. When you
ask, the server only looks up and stitches together summaries it already has.

## The two halves

```
 OFFLINE  (you run it before the demo)                 ONLINE  (every time someone asks)

 TVmaze  ──┐                                           Person: "catch me up on Severance"
 (+Wikipedia later)                                           │
           ▼                                                  ▼
   pipeline/sources        raw episode text            Alexa+  (language understanding)
           │                                                  │  picks a tool + arguments
           ▼                                                  ▼
   pipeline/digest  ← Claude on Bedrock            MCP over HTTPS  (tools/call)
   one digest per episode, seeing ONLY that               │
   episode + earlier digests                              ▼
           │                                         server/  (this repo, no LLM here)
           ▼                                          ├─ identity   who is asking?
   pipeline/season  one digest per finished season    ├─ progress   where did they get to?
           │                                          └─ assemble   stitch digests, never
           ▼                                                         past that episode
   data/shows/<id>.json  ───────────────────────────────►  reads digests
                                                              │
                                                              ▼
                                                    spoken text back to Alexa+ → the person
```

Why not call an LLM at request time? Alexa+ expects an answer in under about half a second,
and a model call can't promise that. Precomputing also lets us test spoiler safety once,
offline.

## A conversation, step by step

| You say | Alexa+ calls | What the server does |
|---|---|---|
| "Do you have Severance?" | `find_show(query)` | fuzzy-matches the name, lists seasons and episode counts |
| "I'm on season 1 episode 3 of Severance" | `save_progress(show, 1, 3)` | checks that episode exists, stores *"through S1E3"* for this user |
| *(weeks later, new conversation)* "Catch me up" | `catch_me_up()` | finds the show you last mentioned and your saved point, returns the recap of S1E1 to S1E3 |
| "Previously on" | `get_previously_on()` | recaps the last two episodes you already watched |
| "Recap Severance through season 1" | `get_recap(show, to_season=1)` | no memory needed: recaps exactly the range asked for |
| "Catch me up" (nothing saved) | `catch_me_up()` | asks "Which season and episode did you last watch?" instead of guessing |

The reply is a small object; `text` is what Alexa+ speaks. It also carries `covered_through`
(the last episode actually included) so Alexa+ can say "through season 1, episode 3".

## How a recap is assembled (the spoiler-safety rules)
`server/assemble.py`, each rule covered by a test:
1. Only episodes inside the requested range are ever used.
2. A **season** summary is used only if the range covers the *whole* season, because a
   season summary can mention that season's last episode. A partly covered season uses
   its individual episode summaries instead.
3. If the result is too long to say aloud (about 220 words), shorten episodes to their first
   sentence, then drop the **oldest** parts, never the newest, and report that via
   `starts_at` / `truncated`.
4. `covered_through` is never later than what was asked.

And at generation time (`pipeline/digest.py`): each episode summary is written from that
episode's text plus the summaries of the 3 episodes before it, never anything later, and the
model is told to use nothing from its own memory of the show.

## Who is "you"? (`server/identity.py`)
Alexa+ sends no user id. Remembered progress needs one, which only account linking provides.
Today: everyone shares a "guest" profile; the web demo gives each browser its own profile
via a header (demo only). Details and the next step: [identity-and-account-linking.md](identity-and-account-linking.md).

## Where the pieces live
| Folder | Role |
|---|---|
| `server/` | the MCP server Alexa+ calls (tools, identity, assembly) |
| `common/` | data models and storage shared by pipeline and server |
| `pipeline/` | offline: fetch, summarize with Bedrock, write `data/` |
| `web_demo/` | stand-in for Alexa+: a chat page + a rule-based sentence parser |
| `examples/` | the fictional offline demo show |
| `evals/` | spoiler-leak and quality checks (stubs, still to build) |
| `addon-package/` | the Alexa+ store listing (draft) |

## What is real and what isn't (honest status)
- **Real and tested:** the MCP server over Streamable HTTP, all five tools, spoiler-safe
  assembly, remembered progress, the web demo.
- **Written, never run live:** the Bedrock summarizer (fake-model tests only).
- **Not built:** account linking, hosting on AWS, the Alexa+ add-on registration, the
  Wikipedia source, the leak eval, a visual card.
