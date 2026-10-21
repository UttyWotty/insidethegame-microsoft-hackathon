<!--
Submission text for the Inside the Game hackathon entry: elevator pitch, technologies, problem, and testing notes.
It is written to be pasted into the hackathon project page with minimal editing.
Numbers quoted here are reproducible from the repository's tests, code, and evaluation reports.
-->

# Inside the Game: Submission

## Links

- **Live app (no sign-in):** https://ca-web-e57jcjawvpd5a.blackriver-4dd5512b.eastus2.azurecontainerapps.io/
- **Demo video (1:25):** VIDEO_URL
- **Repository:** https://github.com/UttyWotty/insidethegame-microsoft-hackathon

## Elevator pitch

Inside the Game turns synthetic football events into explainable, personalized match intelligence in real time.
A seeded simulator streams football-realistic events; a deterministic engine interprets them into xG, expected
threat, line-breaking passes, team shape, and momentum; and eight Microsoft Agent Framework agents spot tactical
patterns, explain why each moment matters, narrate it, personalize it for five audiences in any language, and
fact-check it before it airs. Instant replays re-play the real build-up with shot analysis, and highlights cut
themselves. Every overlay is timed, machine-readable, and grounded in the match data; a producer can hold AI
output, and a grounded fallback keeps the broadcast on air.

## What it does

- **Ingest:** a seeded possession-chain simulator generates full 90-minute matches between fictional clubs with
  distinct tactical styles that adapt to the scoreline and fatigue, and a weak defensive flank per club for the
  Tactical Scout to find. Averages match real top-flight football (about 27 shots, 2.89 goals, 79.5% pass
  accuracy, and a realistic home advantage), checked by a calibration report against top-flight reference bands:
  13 of 13 metrics within band over 480 matches, including where shots are taken from and results by venue.
  Finishing is realistic rather than walk-in: forward dribbles stop 3 to 12 m from the goal line, and near goal
  the keeper stands between the shooter and the goal. A tracking model adds formation-aware positions for all 22
  players after every event, capped at each player's pace-based top speed and holding attackers onside; the dataset generator exports events
  (with expected threat added), players, moments, and tracking as JSON Lines with a dataset card.
- **Interpret:** streaming analytics compute xG, an explainable 0-100 pass difficulty, expected threat (xT) from
  a grid fitted to the project's own synthetic league, line-breaking passes from tracked positions, team shape
  (back-line height, block, width) and shape shifts, running player and team statistics, and rolling momentum,
  control, and chaos. About 30 key moments are detected per match, each with an importance score and facts. A
  tactical pattern miner flags exposed flanks, channel overloads, and turnover zones, and links later goals and
  big chances back to the flag.
- **Explain:** the Match Analyst explains why a moment matters, calling statistics tools for evidence; the
  Tactical Scout explains flagged patterns and shape shifts; the Lead Commentator writes a broadcast line on top
  of continuous play-by-play; the Standards Editor fact-checks attribution and outcomes before anything airs.
  When a goal comes from a flagged pattern, the explanation and the goal banner name the earlier flag. Commentary
  can be spoken aloud and reacts to goals, close calls, and bold passes. A Studio view draws the evidence on the
  pitch (space control, pass networks, heat and pressing maps, a back-line height timeline).
- **Render:** each moment becomes timed overlay cues (layout, display time, duration, priority, stats, provenance)
  rendered over the match in a 3D broadcast view or a broadcast-angle pitch, with live name tags, sprint tags, shot
  cards, line-breaker cards, shape shift lines, win probability, and a danger leaderboard by xT. After every goal
  and big chance (xG 0.25 or more) an instant replay re-plays the real build-up at real pace and the strike in slow
  motion (blocked shots stop at the blocker, saved shots at the keeper), draws the shot cone, and ends on an
  analysis card: xG, goal chance, distance, angle, speed, defenders and keeper in the cone, the build-up, and the
  assist. A replay that comes due while another is rolling waits in a short queue (goals take priority when it is
  full, nothing more than ten match minutes old), and recaps wait until no replay is rolling. At half-time and
  full-time a highlights reel replays the real action (the passes, carries, and shot) of its clips with narration. A
  producer console, updated live over server-sent events, shows pipeline health, a live trace of the agents handing
  work to each other, every moment's broadcast record with any outcome problems, and hold-and-release control of AI
  overlays.
- **Personalize:** five personas (Analyst, Casual Fan, Superfan, Player Tracker, Newcomer) with their own voice,
  vocabulary, word budget, statistical focus, relevance rules, and overlay style; any language; favourite club and
  player. Replay analysis gives the analyst the full set and other personas a plain subset. Half-time and
  full-time recaps carry a take written for each persona, and viewers can ask the Match Companion questions about
  the live match.

## Microsoft technologies

- **Microsoft Agent Framework:** eight agents (Match Analyst, Tactical Scout, Lead Commentator, Personalization
  Producer, Broadcast Translator, Standards Editor, Match Editor, Match Companion) with structured outputs and
  function tools, orchestrated in a workflow with shared state, fan-out and fan-in, a fact-check revision loop,
  and OpenTelemetry instrumentation.
- **Microsoft Foundry:** every agent runs on gpt-4.1-mini deployed in a Foundry project (GlobalStandard), reached
  keylessly through the app's managed identity. A hosted agent in Foundry Agent Service
  (`inside-the-game-companion`) uses this project's MCP server as its tool, authenticated through a Foundry project
  connection, and answers questions about live and finished matches from the Foundry playground. An evaluation
  report for the deployed model is in `docs/evaluations/`.
- **Azure AI Speech:** neural voices read commentary aloud in each viewer's language, keyless through the app's
  managed identity on the same AI Services account; only lines the match produced can be voiced.
- **Model Context Protocol:** the live match intelligence is an MCP server with ten tools (`list_clubs`,
  `start_match`, `list_matches`, `get_match_state`, `get_key_moments`, `get_player_stats`,
  `get_threat_leaderboard`, `get_team_shape`, `get_recaps`, `ask_match_companion`), usable from GitHub Copilot
  agent mode or Foundry agents.
- **Azure Container Apps, Container Registry, Application Insights, Log Analytics:** one container, live in East
  US 2, provisioned and deployed with the Azure Developer CLI (`azd up`) and Bicep.
- **GitHub Actions:** a CI workflow for pull requests and an OIDC deployment workflow without stored secrets,
  ready for `azd pipeline config`.
- **Microsoft Fabric ready:** the dataset generator outputs analytics-ready JSON Lines with a dataset card, a
  PySpark notebook loads them into lakehouse Delta tables, and a Direct Lake semantic model (TMDL) adds
  relationships and DAX measures for a Power BI report; all of it is schema-checked offline
  (see `docs/FABRIC.md`).

## Problem it solves

Broadcasters and streaming platforms have more data than they can explain, and one feed must serve audiences
with very different needs. Inside the Game makes every match feel made for every fan: the same live intelligence
becomes a tactical breakdown, a quick summary, a supporter's reaction, a player-focused feed, or a gentle lesson,
in the viewer's language, while staying factually grounded enough for a live production environment.

## Enterprise readiness

- Grounding validation on every number, a roster rule and fact-checking agent on every model-written card,
  self-correcting retries, and deterministic fallbacks with provenance shown on screen.
- Degraded-path resilience: if the agent workflow fails, a template path still produces cues for every viewer,
  and if a template on that path fails, only that piece is replaced by a minimal grounded output, so a moment is
  never lost. The producer console lists why each output degraded or needed a retry.
- Human in the loop: a producer console to hold AI overlays and release them per moment or all at once, behind an
  optional producer key.
- Keyless model access, least-privilege roles, non-root container, optional MCP bearer token, per-client rate
  limits.
- Agent evaluation harness reporting per-agent model, corrected, and fallback rates and latency; on Foundry the
  Match Analyst and Match Editor wrote 100% of their outputs (`docs/evaluations/2026-10-21-foundry-gpt-4.1-mini.json`).
- 698 automated backend tests and 182 frontend tests, including simulator calibration, finishing-realism, and
  offside checks; infrastructure as code.

## Testing instructions

1. Open the app URL and press **Watch a demo match**: seed 1407, Kestrel Bay Athletic vs Ironvale United at 30x
   speed (a three-minute match).
2. At 58' the Tactical Scout flags Kestrel Bay beating Ironvale's right flank; at 65' Zane Brekke's winner makes
   it 2-1, and the goal banner reads "Scout flagged 58'".
3. With **Auto replays** on, the 65' goal replays its build-up and strike, then ends on the analysis card.
4. Open **All personas** before 65' to see the winner through five audiences side by side (at 30x the goal's
   cards for all five arrive a few match minutes after the goal); overlays show **AI** or **Template** and
   **Fact-checked** or **Corrected by editor** chips.
5. Ask a question in **Ask the analyst**.
6. Open the **Producer** console: hold and release AI overlays, select a moment for its agent trace, broadcast
   record, and any outcome problems.
7. At half-time press **Watch highlights** in the recap.

All clubs, players, and matches are fictional and generated by the project.
