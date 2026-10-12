# Architecture and user flows

Legend: **[built]** exists in the repo today, **[planned]** is a design proposal, not code.

## 1. System overview

```mermaid
flowchart LR
    subgraph OFFLINE["Offline pipeline  (python -m pipeline.run)  [built]"]
        TV[TVmaze API] --> SRC[sources/tvmaze.py]
        WK[Wikipedia] -.stub.-> SRC2[sources/wikipedia.py]
        SRC --> EP[Episode records<br/>pipeline-internal]
        SRC2 -.-> EP
        EP --> DG[digest.py<br/>baseline or LLM]
        DG <--> LLM[llm.py<br/>BedrockLLM + DiskCachedLLM]
        DG --> SE[season.py<br/>complete seasons only]
        SE --> SD[(ShowStore<br/>data/shows/ID.json)]
        DG --> SD
    end

    subgraph ONLINE["Online MCP server  (python -m server.main)  [built]"]
        MAIN[main.py<br/>5 MCP tools] --> TOOLS[tools.py]
        TOOLS --> RES[resolve.py<br/>fuzzy show name]
        TOOLS --> ASM[assemble.py<br/>spoiler-safe recap]
        MAIN --> IDN[identity.py<br/>guest / header / oauth]
        TOOLS --> PS[(ProgressStore<br/>data/users/HASH.json)]
    end

    SD -- read only --> RES
    SD -- read only --> ASM

    ALEXA[Alexa+ <br/> own NLU picks the tool] -- "Streamable HTTP tools/call" --> MAIN
    WEB[web_demo<br/>rule-based intent parser<br/>real MCP client] -- "Streamable HTTP + X-Demo-User" --> MAIN
```

Boundary rule: the pipeline only **writes** `ShowStore`; the server only **reads** it. The server
never calls an LLM. Per-user progress is the only state the server writes.

## 2. Data model

```
Show            id, name, aliases, season_sizes{season: n_episodes}
Episode         raw TVmaze/Wikipedia text   (pipeline-internal, never served)
EpisodeDigest   season, number, digest, title, title_is_spoiler
SeasonDigest    season, digest, episode_count   (only built when season is complete)
ShowData        show + [EpisodeDigest] + [SeasonDigest] + attribution   -> one JSON file per show
Recap           show, text, starts_at, covered_through, truncated, attribution
Progress        show_id, season, episode, updated_at   -> one JSON file per user
```

## 3. Spoiler-safety rules (server/assemble.py)

1. Only episodes inside `[start, end]` are used.
2. A season digest is used only when the range covers the whole season.
3. Over the word budget (brief 90, standard 220): first sentences only, then drop the oldest.
4. `covered_through` is never later than requested; `truncated` is reported honestly.

## 4. User flows

### 4.1 Pipeline run (operator) [built]
```mermaid
sequenceDiagram
    participant Op as Operator
    participant P as pipeline.run
    participant T as TVmaze
    participant L as Claude on Bedrock
    participant S as ShowStore
    Op->>P: --mode llm "Severance"
    P->>T: singlesearch + episodes
    T-->>P: show + episodes
    loop each episode in order
        P->>L: this episode text + last 3 digests only
        L-->>P: {digest, title_is_spoiler}
    end
    loop each COMPLETE season
        P->>L: that season's episode digests only
        L-->>P: {digest}
    end
    P->>S: save ShowData JSON
```

### 4.2 "I'm on season 2 episode 4 of The Bear" -> save_progress [built]
1. Alexa+ NLU picks `save_progress(show, season, episode)`.
2. `resolve_user_id` -> oauth principal, else `X-Demo-User`, else `guest`.
3. `resolve_show` normalizes and fuzzy-matches against stored shows.
4. Unknown show -> "I don't have that yet" (see 4.6). Episode out of range -> spoken error.
5. `ProgressStore.set` (atomic write). Reply: "Got it. I'll remember you're through ...".

### 4.3 "Catch me up" -> catch_me_up [built]
1. Show named: use that show's saved progress. No show: the most recently updated progress.
2. No saved progress -> `needs_progress: true`, "Which season and episode did you last watch?".
3. `assemble_recap(show, (1,1), saved.pos)` -> season digests for complete seasons, episode
   digests for the partial one, trimmed oldest-first to the word budget.
4. Returns `text`, `covered_through`, `truncated`, `attribution`.

### 4.4 "Recap X through season 1" -> get_recap [built]
Same assembly with explicit from/to. No `to_episode` means "through the end of that season".

### 4.5 "Previously on" -> get_previously_on [built]
Explicit season/episode: the `count` episodes before it. Otherwise: the last `count` episodes
up to and including saved progress. Only episode digests, never a season digest.

### 4.6 Show or episode not in the store [built; on-demand needs ON_DEMAND=1]
```mermaid
flowchart TD
    Q[any tool call] --> R{resolve_show hit?}
    R -- no --> V{"ON_DEMAND=1 and TVmaze knows it?"}
    V -- no --> U["text: 'I don't have recaps for that show yet. I can recap: A, B, C.'<br/>found:false"]
    V -- yes --> D["enqueue job (deduped on TVmaze id, daily + per-user caps)<br/>text: 'I've started getting it ready, ask again in a few minutes'"]
    D -.-> W["pipeline.worker -> ShowStore"]
    R -- yes --> E{episode exists in season_sizes?}
    E -- no --> B["spoken error: 'Season 2 has 10 episodes' [built]"]
    E -- yes --> H{digest present?}
    H -- no --> G["LookupError -> 'I don't have recaps between X and Y' [built]"]
    H -- yes --> OK[assemble recap]
```

### 4.7 Web demo [built]
Browser -> `POST /api/ask` -> `intent.parse` (regex) -> real MCP `tools/call` with
`X-Demo-User` -> JSON result -> page shows tool call, result and spoken text.

## 5. Planned extensions (not built)

- **On-demand show generation**: built (`server/on_demand.py`, `common/jobs.py`,
  `pipeline/worker.py`). Still open: SQS/DynamoDB backing for the queue, upgrading a baseline
  show to LLM digests later, a per-user "notify me when ready".
- **Cumulative "story so far" digests**: one per episode, built from the previous cumulative
  digest plus the new episode. Makes `catch_me_up` a lookup of an already-smoothed summary.
- **Request-time synthesis with fallback**: optional small LLM over the selected digests, with a
  hard timeout, a cache keyed by (show, from, to, detail) and a concatenation fallback.
- **Account linking** (Cognito), DynamoDB/S3 stores, Lambda or App Runner deployment.
