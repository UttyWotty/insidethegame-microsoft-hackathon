<!--
Inside the Game is an entry for the Microsoft x Premier League Developer Hackathon.
It turns synthetic, football-realistic match events into explainable match intelligence, live narratives, and personalized recaps.
This README describes the project status, setup, usage, and repository structure.
-->

# Inside the Game

AI-powered match intelligence built on synthetic football event data: ingest live events, interpret them into statistics and patterns, explain why moments matter, render overlay-ready output, and personalize it for analysts and casual fans in multiple languages.

## Status

- Stage 1 (Ingest source): synthetic match engine implemented and calibrated.
- Stage 2 (Interpret): streaming analytics implemented (xG, pass difficulty, stats, rhythm, key moments).
- Stages 3-5 (Explain, Render, Personalize): multi-agent workflow, overlay cues, and recaps implemented.
- API, frontend, and cloud deployment: in progress.

## Synthetic Match Engine

A seeded, deterministic possession-chain simulator generates full 90-minute matches between fictional clubs.
Each team has a tactical style (possession, direct, high press, counter) that adapts to the game state:
trailing teams chase late, leading teams protect. Outcomes are driven by player attributes, pitch geometry,
pressure, and fatigue.

Calibrated averages over 100 simulated matches:

| Metric | Simulated | Typical top-flight range |
|---|---|---|
| Shots per match | 24.4 | 22-28 |
| Goals per match | 2.82 | 2.5-3.0 |
| Goals per shot | 0.115 | 0.10-0.12 |
| Pass accuracy | 80% | 75-88% |
| Tackles per team | ~21 | 15-22 |

Event types: `period_start`, `period_end`, `kick_off`, `pass`, `carry`, `shot`, `goal`, `save`, `pressure`,
`tackle`, `interception`, `foul`, `possession_change`. Coordinates are metres on a 105 x 68 pitch, relative to the
acting team (attacking toward x = 105).

## Planned Stack

- Microsoft Foundry (models and hosted agents)
- Microsoft Agent Framework (multi-agent orchestration)
- Azure cloud-native services for deployment

## Match Interpretation (Stage 2)

`MatchAnalyzer.ingest(event)` interprets each event as it arrives, with no I/O:

- **Expected goals (xG):** independent logistic model on shot distance, goal angle, and pressure.
- **Pass quality:** explainable 0-100 difficulty rating from length, pressure, progression, final-third target,
  and switch of play, with every factor returned for explanation.
- **Running statistics:** per player and per team, including possession share, progressive passes,
  final-third entries, shot speed, and carry distance.
- **Game rhythm:** five-minute rolling momentum (-1 away to +1 home), control (pass share), and chaos
  (turnover rate above a typical-match baseline), labelled as `balanced`, `home_control`, `away_pressure`, `chaos`, etc.
- **Key moments:** goals (with assist and game-state change such as equaliser or go-ahead), big chances missed,
  great saves, shot-speed threshold alerts, difficult passes, momentum swings, chaos spells, and milestones
  (braces, hat-tricks, pass counts). Each moment carries an importance score and structured facts for the
  explanation agents. About 16 moments are detected per match.

## Agents and Personas (Stages 3-5)

Five specialised Microsoft Agent Framework agents, each with a single role:

| Agent | Role | Output schema |
|---|---|---|
| Match Analyst | Explains why a moment matters; calls statistics tools (`get_player_stats`, `compare_teams`, `recent_moments`) | `Explanation` |
| Lead Commentator | Writes one broadcast-ready commentary line | `Commentary` |
| Personalization Producer | Rewrites the explanation for a viewer persona | `PersonaCard` |
| Broadcast Translator | Localises cards, keeping names and numbers intact | `TranslatedCard` |
| Match Editor | Writes half-time and full-time recaps | `MatchRecap` |

Five personas, each a genuinely different experience:

| Persona | Voice | Words | Sees moments from importance | Overlay |
|---|---|---|---|---|
| The Analyst | Precise, metric-first, technical vocabulary | 70 | 0.30 | Stat panel |
| The Casual Fan | Warm, quick, no jargon or decimals | 30 | 0.60 | Lower third |
| The Superfan | Passionate and partisan for a favourite club | 40 | 0.45 (own club only, plus all goals) | Hype banner |
| The Player Tracker | Everything framed around one tracked player | 45 | every moment involving the player | Player tag |
| The Newcomer | Patient teacher, explains one concept per moment | 55 | 0.55 | Explainer card |

Every viewer also chooses a language, and optionally a favourite club and player.

**Trust and resilience**

- **Structured outputs:** every agent returns a Pydantic schema, never free text.
- **Numeric grounding:** every number an agent writes must appear in the moment's evidence or in its own tool
  results (recorded in an evidence ledger). Rounding and percentage forms are accepted; invented numbers are not.
- **Self-correction:** a rejected answer is retried once with the rejection reason.
- **Fallbacks:** if a model times out or fails twice, a deterministic template produces a valid, grounded output,
  so the broadcast never shows an empty overlay. Every output records its source (`model`, `model_retry`, `fallback`),
  attempts, and latency.

## Multi-Agent Workflow

Each broadcast-worthy moment runs through a Microsoft Agent Framework workflow:

```
intake -> analyst -> +-> narrator -------+-> assembler -> overlay cues
                     +-> personalizer ---+
                         (per viewer, concurrently; translator when language is not English)
```

- **Shared state:** intake and analyst write the job and explanation to workflow state; the assembler joins the
  parallel branches using that state.
- **Producer policy:** decides what goes to air. Goals always air; other moments need a relevant viewer and a
  45-second gap since the last overlay, with at most two moments per event.
- **Overlay cues (stage 4, render):** one timed, machine-readable cue per viewer with layout, display start
  (match second), duration, priority, title, body, stat callouts, commentary line, theme, and provenance
  (source, attempts, latency per agent).
- **Recaps:** the Match Editor writes half-time and full-time recaps at each period end, with a grounded
  standout-player check.
- **Failure recovery:** each agent falls back individually; if the workflow itself fails, a degraded
  template path still produces cues for every viewer.

`MatchIntelligenceService.handle_event(event)` runs the whole pipeline for one event.

## Setup

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and optionally [Ollama](https://ollama.com) for local model testing.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e "backend[dev]"
.venv/bin/python -m pytest backend
```

Local models (development only): the agent layer uses the Agent Framework OpenAI-compatible client, so it can
target a local Ollama server during development and Microsoft Foundry in deployment.

```bash
ollama pull qwen3:8b
```

Model configuration (environment variables, all optional):

| Variable | Default | Purpose |
|---|---|---|
| `MODEL_PROVIDER` | `ollama` | `ollama` for local development, `foundry` for Microsoft Foundry |
| `MODEL_NAME` | `qwen3:8b` | Model or deployment name |
| `MODEL_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint |
| `MODEL_API_KEY` | `ollama` | API key (required for `foundry`) |
| `MODEL_TIMEOUT_S` | `45` | Per-attempt timeout |
| `MODEL_MAX_ATTEMPTS` | `2` | Attempts before falling back |
| `MODEL_PROMPT_SUFFIX` | `/no_think` | Appended to prompts for local qwen3 only |

Tests never call a model; agents are tested with a scripted fake chat client.

## Project Structure

```
backend/
  src/insidegame/
    core/         constants, pitch geometry, domain exceptions
    domain/       immutable event, team, and match models
    simulation/   seeded synthetic match engine (stage 1 source)
    analytics/    streaming interpretation: xG, pass quality, stats, rhythm, key moments (stage 2)
    agents/       personas, schemas, prompts, grounding, fallbacks, resilient agent steps (stages 3-5)
    orchestration/ producer policy, workflow executors, overlay cues, match service
    adapters/     environment-driven model client configuration
  tests/          unit and integration tests
```

Dependency direction: `adapters -> orchestration -> agents -> analytics -> domain -> core`, with `simulation -> domain -> core`. Lower layers never import higher ones.

## Branching

This repository follows Git Flow: `main` holds released code, `develop` is the integration branch, and work happens on `feature/*` branches merged into `develop` via pull request.

## License

MIT. See [LICENSE](LICENSE).
