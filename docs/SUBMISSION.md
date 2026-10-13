<!--
Submission text for the Inside the Game hackathon entry: elevator pitch, technologies, problem, and testing notes.
It is written to be pasted into the hackathon project page with minimal editing.
Numbers quoted here are reproducible from the repository's tests and evaluation reports.
-->

# Inside the Game: Submission

## Elevator pitch

Inside the Game turns synthetic football events into explainable, personalized match intelligence in real time.
A seeded simulator streams football-realistic events; a deterministic analytics engine interprets them into xG,
pass difficulty, momentum, and control-versus-chaos; and a team of seven Microsoft Agent Framework agents explains
why each key moment matters, narrates it, personalizes it for five audiences, from data-hungry analysts to
newcomers learning the game, in any language, and fact-checks it before it airs. Every overlay is timed,
machine-readable, and grounded: agents may only cite numbers and players that exist in the match data, a
Standards Editor agent sends wrong cards back for revision, a producer can hold AI output for approval, and a
grounded fallback guarantees the broadcast never goes blank.

## What it does

- **Ingest:** a seeded possession-chain simulator generates full 90-minute matches between fictional clubs with
  distinct tactical styles that adapt to the scoreline and fatigue; averages match real top-flight football
  (about 25 shots, 2.9 goals, 80% pass accuracy, and a realistic home advantage), checked by a calibration
  report against top-flight reference bands (11 of 13 metrics within band over 480 matches, including where
  shots are taken from; results by venue sit just outside their bands). A tracking model
  adds formation-aware positions for all 22 players after every event, with every step capped at the player's
  pace-based top speed and players starting toward their next action, so movement and sprint speeds stay human;
  the dataset generator exports events, players, moments, and tracking as JSON Lines with a dataset card.
- **Interpret:** streaming analytics compute xG, an explainable 0-100 pass difficulty, running player and team
  statistics, rolling momentum, control, and chaos, and detect key moments with importance scores and facts.
- **Explain:** the Match Analyst agent explains why a moment matters, calling statistics tools for evidence; the
  Lead Commentator writes a broadcast line on top of continuous play-by-play; the Standards Editor fact-checks
  attribution and outcomes before anything airs. Commentary can be spoken aloud, and it reacts: goals, close
  calls, and bold passes are called with raised energy and cut in over calmer lines. A Studio view draws the
  evidence on the pitch (space control, pass networks, heat and pressing maps), and the Analyst's own tactical
  theme picks which visual backs its explanation.
- **Render:** each moment becomes timed overlay cues (layout, display time, duration, priority, stats, provenance)
  rendered over the match in a 3D broadcast view (running players, stands, a touchline camera that follows the
  ball) or a broadcast-angle pitch, with live name tags, sprint speed tags, shot traces sized by xG, and a goal
  banner, as a stat panel, lower third, hype banner, player tag, or explainer card. A producer
  console, updated live over server-sent events, shows pipeline health, a live trace of the agents handing work
  to each other for every moment, every moment's full broadcast record, and hold-and-release control of AI
  overlays. At half-time and full-time an automated highlights package replays the key moments with narration.
- **Personalize:** five personas (Analyst, Casual Fan, Superfan, Player Tracker, Newcomer) with their own voice,
  vocabulary, word budget, statistical focus, relevance rules, and overlay style; any language; favourite club and
  player. Half-time and full-time recaps carry a take written for each persona, and viewers can ask the Match
  Companion questions about the live match.

## Microsoft technologies

- **Microsoft Agent Framework:** seven agents (Match Analyst, Lead Commentator, Personalization Producer,
  Broadcast Translator, Standards Editor, Match Editor, Match Companion) with structured outputs and function
  tools, orchestrated in a workflow with shared state, fan-out and fan-in, a fact-check revision loop, and
  OpenTelemetry instrumentation.
- **Microsoft Foundry:** project and model deployment, accessed keylessly with a managed identity, plus a hosted
  agent in Foundry Agent Service that uses this project's MCP server to answer questions about live matches.
- **Azure AI Speech:** neural voices read commentary aloud in each viewer's language, keyless through the app's
  managed identity on the same AI Services account; only lines the match produced can be voiced.
- **Model Context Protocol:** the live match intelligence is an MCP server, usable from GitHub Copilot agent mode
  or Foundry agents.
- **Azure Container Apps, Container Registry, Application Insights, Log Analytics:** one container, provisioned
  with the Azure Developer CLI and Bicep.
- **GitHub Actions:** CI on every pull request and OIDC-based deployment without stored secrets.
- **Microsoft Fabric ready:** the dataset generator outputs analytics-ready JSON Lines with a dataset card.

## Problem it solves

Broadcasters and streaming platforms have more data than they can explain, and one feed must serve audiences
with very different needs. Inside the Game makes every match feel made for every fan: the same live intelligence
becomes a tactical breakdown, a quick summary, a supporter's reaction, a player-focused feed, or a gentle lesson,
in the viewer's language, while staying factually grounded enough for a live production environment.

## Enterprise readiness

- Grounding validation on every number, a roster rule and fact-checking agent on every model-written card,
  self-correcting retries, and deterministic fallbacks with provenance shown on screen.
- Human in the loop: a producer console to hold AI overlays and release them per moment or all at once, behind an
  optional producer key.
- Keyless model access, least-privilege roles, non-root container, optional MCP bearer token.
- Agent evaluation harness reporting per-agent model, corrected, and fallback rates and latency.
- 201 automated backend tests and 67 frontend tests; infrastructure as code.

## Testing instructions

1. Open the app URL and press **Watch a demo match** on the landing screen (or **Kick off**; 30x speed gives a
   three-minute match).
2. Switch personas and language in **Your experience** and watch the overlay style, voice, and language change.
3. Open **All personas** to see the same match through five audiences side by side.
4. Ask a question in **Ask the analyst**.
5. Overlays show an **AI** or **Template** chip with latency, and a **Fact-checked** or **Corrected by editor**
   chip, showing where each output came from.
6. Open the **Producer** console to see pipeline health and every moment's broadcast record, and try holding AI
   overlays for approval.

All clubs, players, and matches are fictional and generated by the project.
