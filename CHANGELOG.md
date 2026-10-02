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

- Momentum and chaos moments wait five minutes into each period before firing.
- Fallback commentary no longer repeats the minute.
- Match service split into fast interpretation and background production with dynamic viewer segments.
- Superfan fallback tone distinguishes own-club setbacks from successes.
- Cues for fallback translations are labelled English.
- Recalibrated simulator tackle and scoring rates toward realistic top-flight averages.
