<!--
This file records all notable changes to the project in Keep a Changelog format.
Entries are added under Unreleased by each feature pull request.
Releases move those entries under a versioned, dated heading.
-->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Dataset export writes `tracking.jsonl`: ball and all 22 player positions every fifth event, in the same absolute
  home frame as the events; the dataset card documents it, and the two-match sample in `data/sample/` is refreshed.
- Landing screen with the value proposition, four differentiators, and a one-click demo match.
- Shot traces on the pitch (xG bubble sized by chance quality, result label) and a full-width GOAL banner in the
  scoring club's colours; the half-time recap closes itself after 15 seconds so play is not covered.
- Producer console: pipeline health tiles, a timeline of every detected moment with air status, full broadcast
  records (analyst reasoning, commentary, every audience's overlay with source and fact-check verdict), and
  human-in-the-loop hold and release of AI overlays, with an optional producer key.
- Standards Editor (fact-checker) agent: a roster rule rejects invented players, then the agent checks
  attribution and outcomes of model-written cards and commentary; rejected cards go back to the personalizer with
  the issues for one revision, then a grounded template replaces anything still wrong. Verdicts are recorded in
  cue provenance and shown as "Fact-checked" or "Corrected by editor" chips.
- Synthetic 22-player tracking: formation-aware positions after every event (teams push and spread in possession,
  compact and shift when defending, press higher by style; actors placed on the ball), streamed with each event.
  Distance covered is realistic (about 11 km per outfield player).
- Broadcast pitch: all 22 players with shirt numbers and live name tags for the players in the action, a ringed
  tracked player, and a broadcast camera mode tilting the pitch like a TV angle (with a flat tactical mode).

### Changed

- Submission text and demo script describe the seven agents, fact-checking, the producer console, tracking, and
  the Copilot-via-MCP segment; the script requires real AI output before recording and uses the exact UI labels.
- Agent evaluation takes one moment per kind (instead of the first few in time order) so every persona, the
  translator, and the fact-checker are exercised, and the report tallies fact-check verdicts.
- The Lead Commentator uses the right verb for the action (passes are not strikes) and avoids repeated words.
- Continuous play-by-play commentary from kick-off (kick-offs, final-third attacks, long passes, dribbles, tackles,
  interceptions, high pressing, long spells, half-time and full-time), paced at about one line per match minute and
  shared by every viewer.
- Switching persona or language keeps match-wide state (commentary, momentum, trail, stats) and swaps only
  persona-specific overlays and recaps; moment commentary is de-duplicated across segments.
- Moment commentary is translated for non-English viewers, and recap takes are written in the viewer's language
  when a model is available.
- The viewer panel explains what persona and language change, and says when translation is unavailable offline.
- "Ask the analyst" fallback now answers the question: a deterministic engine recognises best-player, who-is-on-top,
  momentum, named-player, and score questions and answers from live statistics in each persona's voice (the
  superfan in first person, the player tracker with their player's numbers, the newcomer with a term explained).
- Half-time and full-time recaps are personalized: each viewer segment receives a persona take (model-written when
  available, grounded template otherwise) above the shared recap.

### Fixed

- The producer console showed moments whose agents were still working as "Not aired"; they now show as
  "In production" until their broadcast record arrives.
- Player surnames are unique within a fixture (surname pool enlarged to 56), so short names such as "Varga" in
  agent output always identify one player; seeded rosters and matches differ from earlier releases.
- The full-time drain could spin forever on finished tasks awaiting removal; it now waits only on unfinished work.
- A failing background task (agent workflow or recap) could stop a match from ever ending; failures now degrade
  to grounded templates and the end message is always sent.
- Viewers joining during the full-time drain could lose their backfilled cues; the session now drains until no
  work remains.
- Brace and hat-trick milestones rarely aired because the goal on the same event started the overlay gap; all now air.
- Replayed history cues (on reconnect or language switch) and stale late cues were shown as live overlays.
- Starting a second match kept the first match's recap state and questions.
- Analyst tools could cite statistics and moments from after the moment being explained.
- Unvalidated club and player ids created unlimited viewer segments; ids are validated, unused preferences
  dropped, and segments capped at 10 per match.
- Decimal commas (for example 0,38) broke grounding and translation checks.
- Reconnecting re-produced cues the segment already had.
- Shutdown hung while live streams were open; a five-second graceful timeout applies and agent work is cancelled.

### Added

- `techdebt.md` tracking Azure go-live steps, submission tasks, and engineering follow-ups.
- Foundry Agent Service hosted agent: definition builder restricted to read and question MCP tools, registration
  CLI with an optional test question, `AZURE_AI_PROJECT_ENDPOINT` deployment output, and `foundry` extra.
- README screenshots of the broadcast view and five-persona multiview.
- Metadata loading with exponential backoff and a visible retry banner when the service is unreachable.

### Changed

- Mobile layout: wrapping header, full-width view tabs, live pitch first, overlays sized for phones.
- Recap turning points only include moments with importance of at least 0.45, with readable labels.
- Carry milestone headline reads "tops 300 m carried with the ball".

## [0.1.0] - 2026-10-02

### Added

- Sliding-window rate limit (default 20 questions per match per minute) on `/ask` and the MCP companion tool,
  returning 429 with a retry hint.

- Distance indicators for player tagging: completed passes of 40 m or more and players passing 300 m and 400 m
  carried, with explanation templates and a newcomer glossary entry.

- Architecture documentation with Mermaid diagrams, submission text, and a timed two-minute demo script.

- Synthetic dataset generator: matches, enriched events (absolute coordinates, xG, pass difficulty, momentum,
  rhythm, triggered moments), player statistics, and labelled key moments as JSON Lines, with a generated
  dataset card; two-match sample in `data/sample/`.

- MCP server at `/mcp` (streamable HTTP, MCP SDK 2) with eight tools over the live session registry, including
  starting matches and questioning the Match Companion; optional bearer-token guard and host allow-list, wired
  into the Bicep deployment.

- Match Companion agent and "Ask the analyst" panel: grounded answers to viewer questions in the viewer's persona
  and language, with statistics tools, supporting stats, follow-up suggestions, and a grounded fallback.
- `POST /api/matches/{id}/ask` endpoint with input validation.

- Azure deployment: multi-stage Dockerfile serving API and frontend from one non-root container, azd project,
  and Bicep for Microsoft Foundry (account, project, model deployment), Container Apps, Container Registry,
  managed identity with least-privilege roles, Log Analytics, and Application Insights.
- Keyless Foundry provider using managed identity (`DefaultAzureCredential`), with optional key auth.
- OpenTelemetry export of Agent Framework traces to Application Insights.
- GitHub Actions CI (backend tests, frontend typecheck/tests/build, container build) and OIDC deploy workflow.
- Deployment guide in `docs/DEPLOYMENT.md`.

- MLX model provider (mlx_lm.server) with inline JSON schema prompting for servers without structured output.
- Per-runtime concurrency gate; local providers default to one call at a time, timed after the gate.
- Agent evaluation harness (`insidegame.evaluation`) reporting per-role model, corrected, and fallback rates,
  latency percentiles, rejection reasons, and persona samples; first MLX report in `docs/evaluations/`.
- Tracked players' live statistics in moment context and point-of-view framing for the Player Tracker.

- Broadcast frontend (React, TypeScript, Vite): live pitch, score bug, five persona overlay layouts with
  provenance, team stats, momentum chart, commentary ticker, recap dialog, and five-persona multiview.
- Backfill of recent relevant moments when a viewer segment joins mid-match.
- Broadcast minute labels with added time (45+3') shared by recaps, prompts, and the UI.

- FastAPI service with lifespan startup, lightweight health, model diagnostics, and metadata endpoints.
- Live match sessions replaying simulated matches at configurable speed, with background agent work.
- Personalized server-sent event streams per viewer segment (event, snapshot, cue, recap, end).
- Offline model provider that serves grounded templates without any model server.

- Multi-agent moment workflow on Microsoft Agent Framework: intake, analyst, parallel narrator and
  personalizer (with per-viewer translation), and assembler joined through shared workflow state.
- Timed overlay cues per viewer with layout, timing, priority, stat callouts, and per-agent provenance.
- Producer policy pacing overlays (goals always air, 45-second gap otherwise, two moments per event cap).
- Automated half-time and full-time recaps with grounded standout-player validation.
- Match intelligence service running the full pipeline per event, with a degraded template path when the
  workflow fails.

- Five Microsoft Agent Framework agents (analyst, commentator, personalization producer, translator, editor)
  with structured Pydantic outputs.
- Five personas (Analyst, Casual Fan, Superfan, Player Tracker, Newcomer) with distinct voice, vocabulary,
  word budget, statistical focus, relevance rules, and overlay style.
- Numeric grounding check with an evidence ledger for analyst tool results.
- Resilient agent runner with timeout, self-correcting retry, and deterministic template fallbacks.
- Analyst statistics tools and environment-driven model client adapter (Ollama locally, Foundry in deployment).

- Streaming match analyzer (stage 2) combining xG, pass difficulty, running player/team statistics,
  possession share, rolling momentum/control/chaos, and rule-based key moment detection.
- Explainable pass difficulty rating with per-factor breakdown.
- Key moments with importance scores and structured facts: goals, big chances, great saves, speed alerts,
  difficult passes, momentum swings, chaos spells, and milestones.
- Synthetic match engine: seeded possession-chain simulator producing full 90-minute event streams
  (passes, carries, shots, goals, saves, pressure, tackles, interceptions, fouls, possession changes).
- Fictional club presets with distinct tactical styles that adapt to game state and fatigue.
- Immutable, JSON-serialisable domain models for matches, teams, players, and events.
- Test suite covering geometry, probability models, roster generation, and statistical realism.
- Repository scaffolding: README, changelog, license, and ignore rules.

### Changed

- All API routes are served under `/api`; `/api/diagnostics` now makes one minimal real model call.
- Default local provider is MLX instead of Ollama.
- Momentum and chaos moments wait five minutes into each period before firing.
- Fallback commentary no longer repeats the minute.
- Match service split into fast interpretation and background production with dynamic viewer segments.
- Superfan fallback tone distinguishes own-club setbacks from successes.
- Cues for fallback translations are labelled English.
- Recalibrated simulator tackle and scoring rates toward realistic top-flight averages.

### Fixed

- A viewer joining a finished match received the end of the stream before its backfilled cues; the end
  message now follows that viewer's backfill (found by CI timing).
- The first viewer of a match nobody had watched received no cues, because backfill only drew on moments
  already aired to someone; the session now keeps recent key moments regardless of audience.
- Fenced JSON from local models was rejected because the framework's lazy structured value raised before the
  runner's own parser ran; the runner now falls back to its parser.
- Template punctuation no longer doubles a trailing period from model headlines.
- `httpx` pinned below 1.0 to avoid an incompatible pre-release.

[Unreleased]: https://github.com/UttyWotty/inside-the-game/compare/v0.1.0...develop
[0.1.0]: https://github.com/UttyWotty/inside-the-game/releases/tag/v0.1.0
