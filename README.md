<!--
Inside the Game is an entry for the Microsoft x Premier League Developer Hackathon.
It turns synthetic, football-realistic match events into explainable match intelligence, live narratives, and personalized recaps.
This README describes the project status, setup, usage, and repository structure.
-->

# Inside the Game

AI-powered match intelligence built on synthetic football event data: ingest live events, interpret them into statistics and patterns, explain why moments matter, render overlay-ready output, and personalize it for analysts and casual fans in multiple languages.

## Status

- Stage 1 (Ingest source): synthetic match engine implemented and calibrated.
- Stages 2-5 (Interpret, Explain, Render, Personalize): in progress.

## Synthetic Match Engine

A seeded, deterministic possession-chain simulator generates full 90-minute matches between fictional clubs.
Each team has a tactical style (possession, direct, high press, counter) that adapts to the game state:
trailing teams chase late, leading teams protect. Outcomes are driven by player attributes, pitch geometry,
pressure, and fatigue.

Calibrated averages over 100 simulated matches:

| Metric | Simulated | Typical top-flight range |
|---|---|---|
| Shots per match | 25.7 | 22-28 |
| Goals per match | 2.88 | 2.5-3.0 |
| Goals per shot | 0.11 | 0.10-0.12 |
| Pass accuracy | 80% | 75-88% |
| Passes per match | ~1,090 | 900-1,200 |

Event types: `period_start`, `period_end`, `kick_off`, `pass`, `carry`, `shot`, `goal`, `save`, `pressure`,
`tackle`, `interception`, `foul`, `possession_change`. Coordinates are metres on a 105 x 68 pitch, relative to the
acting team (attacking toward x = 105).

## Planned Stack

- Microsoft Foundry (models and hosted agents)
- Microsoft Agent Framework (multi-agent orchestration)
- Azure cloud-native services for deployment

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

## Project Structure

```
backend/
  src/insidegame/
    core/         constants, pitch geometry, domain exceptions
    domain/       immutable event, team, and match models
    simulation/   seeded synthetic match engine
  tests/          unit and integration tests
```

Dependency direction: `simulation -> domain -> core`. Lower layers never import higher ones.

## Branching

This repository follows Git Flow: `main` holds released code, `develop` is the integration branch, and work happens on `feature/*` branches merged into `develop` via pull request.

## License

MIT. See [LICENSE](LICENSE).
