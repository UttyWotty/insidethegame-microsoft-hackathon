<!--
Open follow-ups and technical debt for Inside the Game, tracked in the repository so nothing is forgotten.
Resolved items are wrapped in HTML comments rather than deleted, preserving history.
Ordered by priority within each section; status as of 2026-10-16 (develop at PR #64, release v0.1.0 on main).
-->

# Tech Debt and Follow-ups

Every item that needs neither a model run nor Azure is done. Suggested order for the remaining work: Azure deploy
and verification (diagnostics, AI chips, neural voice), a Foundry evaluation report, README screenshots and the
Copilot-through-MCP recording, the demo video, then the submission steps. Fabric is optional polish.

## Next up (first thing next session)

<!--
- Analysis replay (planned 2026-10-16, not started; branch `feature/analysis-replay`, PR open). The instant replay
  looks like the scorer walks the ball into the goal. Measured on seed 201:
  - The shot and the goal share a `match_second`, so the frame with the ball in the goal is skipped, and the goal
    event (`end=None`) puts the ball back at the shooter's feet. On all 7 goals the ball never goes in.
  - The 6 s + 2.5 s window holds only 3 to 5 frames (one per event, 1.4 to 3.7 s apart), so the build-up is cut
    off: the 77' winner's 34.4 m assist is never shown.
  - Each frame puts the ball at the action's end point as the action starts, while players are speed-capped, so the
    ball runs ahead of them.
  Plan: a pure backend builder turns the last 4 or fewer completed passes and dribbles (within 12 s), the shot, and
  the ball's flight to the goal line into replay keyframes, with the ball at each action's real start point. The
  replay then shows analysis only during the replay, all from existing analytics: xG, goal chance, distance, angle,
  shot speed, defenders and keeper inside the angle to the posts, pressure, build-up pass count, time, and xT, and
  the assist with its xT and line break. The analyst gets the full set and other personas a simpler one. The 2D
  pitch draws the shot cone and the build-up path; the live broadcast is unchanged outside the replay. Full plan
  with 10 acceptance criteria: `.loop/analysis-replay/plan.md` (local). Run it through the agent loop: builder, QA,
  then evaluator.
  Resolved 2026-10-16: built on `feature/analysis-replay` (replay story, analysis card, shot cone, build-up path).
-->
<!--
- Follow-up (separate task): the highlights reel has the same ball-flight bug; fix it with the replay builder.
  Resolved 2026-10-16: built on `feature/reel-real-action` (shot clips replay the story keyframes, `playback`).
-->
- Follow-up (separate task): non-shot reel clips (distance thresholds, difficult or line-breaking passes, pass and
  carry milestones, momentum swings, chaos spells) still play stored frames, so the ball runs ahead of the players
  on passes (seed 194's 15' momentum swing). Needs keyframes for single passes and carries and a new story kind.
- Follow-up (separate task): a qualifying replay is dropped, not queued, while another replay is playing (seed 194's
  65' save, xG 0.55, got no replay), and the full-time recap opens over a replay that starts after 90 minutes.
- Follow-up (separate task): in the default broadcast camera the highlights caption covers the bottom strip of the
  pitch, hiding the start of the 77' build-up (the assist starts near that touchline). Move or shrink the caption
  during story clips, or frame the camera higher.
- Follow-up (separate task): `highlights/reel.py` imports `agents.recap_context` (a higher layer); move
  `MIN_TURNING_POINT_IMPORTANCE`, `RecapStage`, and `moment_actor` down a layer.
<!--
- Follow-up (separate task): a saved shot in the replay still flies to its spot on the goal line with no keeper
  interaction, so it can look like it went in; stop it at the keeper the way blocked shots stop at the blocker.
  Resolved 2026-10-16: built on `feature/replay-keeper-save` (saved ball stops at the keeper, keeper shown at the save).
-->
<!--
- Follow-up (separate task, needs regenerated xT grid, calibration doc, and sample data): 4 of the 7 seed-201 goals
  (15', 19', 52', 62') come from dribbles that stop at the `CARRY_MAX_X_M` limit (x = 103.0, 2 to 3 m out), with
  the tracked keeper level or behind. Across 60 seeds these shots are 8.3% of shots but 35% of goals. The new
  replay will show the passes and the ball going in, but these goals will still look like walk-ins.
  Resolved 2026-10-17: built on `feature/realistic-finishing` (carry stop band, keeper narrows the angle, demo seed 1407).
-->
- Follow-up (separate tuning task): the pass-target clamp `MAX_PASS_X_M = 99.0` (`simulation/open_play.py`) makes
  a spike of shots from exactly x = 99 (6 m out). It is not a walk-in (the keeper is in front), but replays show
  many shots from the same depth: 17.8% of shots and 19.1% of goals before the finishing change, 20.4% and 33.1%
  after (seeds 1-60, Kestrel Bay vs Ironvale). Spreading it (`pass=92:101`, `pass=93:102`) was prototyped, but
  goals fell to 2.40-2.57 per match and draws rose out of band, so it needs its own calibration tuning.
- Follow-up (separate task): the superfan persona card for a goal linked to a `flank_exposed` Scout flag
  (`agents/templates.py`, prefix plus the full `why_it_matters`) can exceed the superfan's 40-word limit (x 1.3)
  on seeds 779, 802, 1176, and 1809 (and 3693, the only late-winner demo candidate). Fix: prefix plus the leading
  whole sentences of `why_it_matters` within `max_words`. Seed 1407 (the demo) is not affected.

## Blockers before submitting

<!--
- Check the employment contract (or get written permission): the project was built on a work laptop, and the rules
  require the submission to be solely owned by the entrant (rules 4.6 and 4.11). Use a personal machine from now on.
  Resolved 2026-10-12: the owner confirmed this machine is approved for the project.
-->
- Agents have been validated on a real model only through the evaluation harness, not yet in the live UI. Validate
  the live path (MLX locally, then Foundry) before recording anything.
  Done 2026-10-13 with Qwen3.8 27B 6-bit on the MLX gateway at `127.0.0.1:8081` (launchd agent
  `local.mlx-serve-qwen38`; reuse it, never start a separate server): the evaluation over five moment kinds plus
  the full-time recap was 100% model output for analyst, translator, and recap editor, 92% first-time and 8%
  corrected for persona cards, with 8 fact-check approvals and 4 revisions
  (`docs/evaluations/2026-10-13-mlx-qwen3.8-27b-6bit.json`). Fixes found by the run: unique surnames per fixture,
  commentator verbs, eval coverage of every persona, fact-check issues in the report, and "In production" status
  in the producer console.
  Still open:
  <!--
  1. Live UI check. The 2026-10-13 attempt (seed 7, speed 20, analyst and Spanish casual viewers) produced no
     broadcast record in 12 minutes: all 18 detected moments started at once and shared the single local model
     slot, so none finished, and a `godot` process from another project was saturating the machine at the same
     time. Retry when the machine is idle (check `ps -Ao pid,%cpu,comm -r | head` as well as `lsof` on 8080/8081)
     now that moment production has backpressure, with one viewer at speed 10 or lower:
     `MODEL_PROVIDER=mlx MODEL_NAME=ailexleon/Huihui-Qwen3.8-27B-abliterated-mlx-6Bit
     MODEL_BASE_URL=http://127.0.0.1:8081/v1 MODEL_TIMEOUT_S=240 MODEL_MAX_CONCURRENCY=1 API_PORT=8000
     .venv/bin/python -m insidegame.main`, then confirm the chips show AI (not Template) and the producer console
     shows model sources and fact-check verdicts.
  -->
     Done 2026-10-16 (seed 201, speed 10, one analyst viewer, Qwen3.8 27B 6-bit on 8081, browser closed after
     kick-off and checked through the producer API): the 15' goal aired with explanation, commentary, and card all
     from the model and a model fact-check approval with no issues; the 1' long-pass card aired with model
     commentary and card, a model fact-check approval, and a fallback explanation after the Match Analyst hit the
     240 s timeout. No tracebacks; backpressure skipped 2 moments. Local latency is 4 to 11 minutes per card, so
     the local model cannot keep up with a live match at any useful speed; record the video on Foundry.
  2. Rerun the evaluation once to read `fact_check_issues` and judge whether the 4 revisions were real catches.

## Azure go-live (needs a personal Azure subscription)

- Create the Azure free account (needs a credit card; do it on a personal machine, not the work laptop).
- Deploy: `azd auth login && azd up` from the repo root; pick a region with model quota (for example `eastus2` or `swedencentral`). See `docs/DEPLOYMENT.md`.
- Before deploying, protect write and cost endpoints: `azd env set MCP_API_KEY "$(openssl rand -hex 24)"` and set `PRODUCER_KEY` on the container app.
- Verify: open `https://<app-url>/api/diagnostics` (one real model call through the managed identity), then use the app.
- Register the Foundry hosted agent: `uv pip install --python .venv/bin/python -e "backend[foundry]"`, then `eval "$(azd env get-values)"` and `.venv/bin/python -m insidegame.foundry.register --ask "Which matches are live?"`.
- Set up continuous deployment: `azd pipeline config`.
- Verify neural speech: `curl https://<app-url>/api/speech/status` shows available, then turn on Voice in the app.
  The REST path (`/tts/cognitiveservices/v1` on the custom-domain endpoint with an Entra token) is untested
  against Azure; if it returns 401, check the Speech User role assignment and the custom subdomain.
- Run `python -m insidegame.evaluation.run --max-moments 6` against Foundry, fix prompt or quality issues it shows, and commit the report to `docs/evaluations/`.

## Features that raise the chance of winning

<!--
- Spoken commentary with Azure AI Speech (neural text to speech per language); strongest "multi-language
  storytelling" and Microsoft-service showcase. Browser speech synthesis already reads commentary (Voice toggle,
  2026-10-13); remaining: a `/api/speech` adapter on Azure AI Speech with managed identity, a Speech resource in
  Bicep, and the frontend preferring it when configured (needs the Azure subscription to verify).
  Resolved 2026-10-13: `/api/matches/{id}/speech`, Speech role and endpoint in Bicep, frontend prefers it.
-->
- Microsoft Fabric: load `datasets.generate` output into a Fabric lakehouse and build a small Power BI report; reference it in the submission.
- Foundry evaluations (groundedness, relevance) on agent outputs, linked from the producer console or docs.
- GitHub Copilot: record Copilot agent mode in VS Code querying the live match through the MCP server (`.vscode/mcp.json` example in README); also register the Foundry hosted agent and show it in the portal.
<!--
- Tracking frames in the dataset export (`tracking.jsonl`, sampled) to strengthen the synthetic data story.
  Resolved 2026-10-13 in PR #30.
-->

## Submission (deadline 2026-10-27 23:59 PT)

- Retake README screenshots (`docs/images/`): they predate the 22-player broadcast pitch, sprint tags, landing screen, fact-check chips, and producer console; capture them with real AI output.
- Record the demo video from `docs/DEMO_SCRIPT.md` (under 2 minutes, no copyrighted music, Voice on); dry-run the
  script first. The demo match is now seed 201 (4-3), chosen after the weak-flank tendency changed every seeded match;
  its 35' and 77' goals are linked to earlier Tactical Scout flags.
<!--
- Update the demo script to include the broadcast camera, fact-checker, producer console, and Copilot or Foundry
  agent via MCP. Resolved 2026-10-13 in PR #31; spoken commentary and sprint tags added in PR #48.
-->
<!--
- Update `docs/SUBMISSION.md` with the seven agents, tracking, fact-checking, and producer console.
  Resolved 2026-10-13: submission text and demo script refreshed; spoken commentary, sprint tags, and test counts
  added in PR #48.
-->
- Cut release `v0.2.0` through Git Flow once deployed and validated.
- Make the GitHub repository public before submitting.
- Paste `docs/SUBMISSION.md` into the hackathon project page with the app URL and video link.
- Keep the deployment running until judging ends on 2026-11-10, then `azd down --purge`.

## Engineering

<!--
- Backpressure for moment production: every detected moment starts its agent workflow at once, so with a slow
  or rate-limited model they all share the gate and finish late together (seen live on 2026-10-13). Produce
  moments in order with a small in-flight limit, and skip non-goal moments that are stale by the time a slot frees.
  Resolved 2026-10-13: production slots, stale skipping, and console statuses.
-->
<!--
- Simulator realism: many shots start on the byline (x 103 to 104 m), some from the corner flag at a near-zero
  angle, because a carry that reaches the byline ends in a shot instead of a cross or cutback. Calibration still
  passes, but the shot card and 3D view expose it. Fix in the possession chain (cross or cut back from wide byline
  positions), then rerun `insidegame.datasets.calibrate`; this changes seeded matches, including the seed 7 demo.
  Resolved 2026-10-13 in PR #58: shots weighted by openness to goal, cutbacks and crosses from wide byline
  positions; byline shots 55% to 1.8% of all shots.
-->
- Results by venue sit just outside their bands after the shot-location fix (home wins 38.8% against 40 to 48%,
  draws 32.1% against 22 to 30%, 480 matches). Raise scoring slightly or strengthen home advantage, then rerun
  `insidegame.datasets.calibrate`.
- `npm audit` reports advisories in vitest's dependencies (tinypool, @vitest/mocker); they affect only the test
  runner, not the shipped bundle. Upgrade to vitest 4 (a breaking change) in its own pull request.
- Live sessions are in memory, so the app runs a single replica; move session state to a shared store before scaling out.
<!--
- `/api/matches` (match creation) has no per-client rate limit beyond the 20-session cap.
  Resolved 2026-10-13: per-client sliding-window limit (MATCH_CREATE_MAX_PER_MINUTE).
-->
<!--
- Blocked shots are not modelled, so shots on target run slightly above the reference band (40% against 30 to 40%
  in `docs/CALIBRATION.md`); a block outcome in `resolve_shot` would fix it.
  Resolved 2026-10-13: blocks were already modelled; the cause was the save share (0.40 to 0.32), now 35%.
-->
<!-- - Tracking-derived player speeds are unrealistic (teleporting event actors), so speed indicators use modelled shot and ball speeds only; smoothing or a kinematic model would allow real sprint tags. -->
- Local MLX runs are slow (10 to 35 seconds per call with one call at a time); try the Qwen 35B A3B MoE model or a concurrency of 2 if local testing matters.
<!-- - The producer console polls every 2 seconds; move it to the event stream if it needs to scale. -->
- The GitHub CLI's active account on this machine switched to UtkuGulbardak; commands for this repo use `GH_TOKEN=$(gh auth token --user UttyWotty)`.
