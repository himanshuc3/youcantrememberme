# Hackathon requirements checklist

From the official rules (Build, Ship, Shape: Amazon Developer Hackathon). Re-read the
Devpost page before submitting: the rules can be amended.

**Deadline: Fri Oct 23, 2026, 12:00 pm PT.** Judging Nov 9–20, winners ~Dec 3.
AWS credit requests are closed (out of codes as of Oct 7).

## Must have to submit
- [ ] **Working Alexa+ project**: a self-hosted MCP server, spec `2025-11-25`+, over
      Streamable HTTP. (Alternative: a simulated Alexa+ web app, exempt from the
      runtime-tech requirement.) We have the MCP server (`server/`); needs hosting.
- [ ] **Runtime use of the track tech in code**: the MCP SDK is imported and called
      (`server/main.py`). ✅ already true. Not just named in the README.
- [ ] **Code repository URL** with all source, assets and clear **setup and run
      instructions** (README ✅ started).
  - Public + an open-source **license file** visible in the repo's About section, **or**
  - Private, shared with `testing@devpost.com` and the Amazon reviewers. ⚠ Decision
    needed. I have not changed repo visibility or collaborators.
- [ ] **Text description** of features and functionality.
- [ ] **Demo video, under 3 minutes**, public on YouTube or Vimeo, showing the project
      working on the intended platform. No third-party trademarks or copyrighted music.
- [ ] **Product Feedback** for every tool/API/SDK used: what we used it for, what worked,
      what needs work, onboarding experience, would we build with it again (yes/no + why).
- [ ] Say which **primary track** (Alexa+) and which **mini challenges** we enter.
- [ ] If the project is not brand new: explain what was significantly updated during the
      window. (Ours is new.)
- [ ] Third-party data must be used within its terms: TVmaze (CC BY-SA, credit it) ✅;
      Wikipedia (CC BY-SA, credit it) when added; TMDB prohibits commercial use.

## Mini challenges (optional, one prize each on top of a track prize)
- **AWS Builder**: a primary-track project using AWS services with documented
  integrations. Our Bedrock digest pipeline fits (`docs/bedrock.md`). Describe it in the
  Product Feedback answer. Judges call "a single Bedrock call" *obvious*, so show the
  multi-step pipeline (episode → season digests, spoiler-leak eval with an LLM judge).
- **Open Source**: a new open-source repo made during the window, plus the contribution
  URL, repo URL, GitHub username and a description. Needs the license file.

## Bonus
- **Friction log**: up to +10% on the score. Specific task, steps, expected vs actual,
  severity, workaround, suggestion. Started in `docs/friction-log.md`. Add entries as we
  actually hit problems.
- Optional feature requests (description, why it matters, priority).

## Judging (equal weights) and where we stand
1. **Tech Implementation**: effective use of the required tech.
2. **Design**: complete, coherent, intuitive for the platform (voice + visual).
3. **Potential Impact**: credible case for real customers beyond the hackathon.
4. **Quality of the Idea**: creative vs obvious.

The rules' own examples for Alexa+: *Obvious* = single-turn Q&A, a basic MCP wrapper around
an existing API. *Creative* = agentic workflows, **context-aware add-ons that keep state
across sessions**, purchasing, **media support (cards, carousels)**, **MCP Apps**, Agent
Skills.

**Honest gap:** today's MVP (look up a stored recap) sits closer to "wrapper around an
existing API" than to "creative". Spoiler-safety by construction is our real strength,
but to score on Quality of the Idea and Design we should add at least:
1. **Remember where you are** per user across sessions ("I'm on season 2 episode 4",
   then later just "catch me up"). ✅ Built (`save_progress` / `catch_me_up`), working
   for a single user or the web demo. Multi-user on a real device needs account linking:
   see `docs/identity-and-account-linking.md`.
2. **A visual MCP App card** (inline recap with a season/episode timeline and a spoiler
   shield). The design guide lists inline / fullscreen / voice-only display modes.
3. **Any show on demand** (generate and cache digests in the background when asked for a
   show we don't have), which also makes the impact case stronger.
Decide which to build after the basics work end to end.
