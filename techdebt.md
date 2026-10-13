<!--
Open follow-ups and technical debt for Inside the Game, tracked in the repository so nothing is forgotten.
Resolved items are wrapped in HTML comments rather than deleted, preserving history.
Ordered by priority within each section; status as of 2026-10-13 (develop at PR #48, release v0.1.0 on main).
-->

# Tech Debt and Follow-ups

Every item that needs neither a model run nor Azure is done. Suggested order for the remaining work: Azure deploy
and verification (diagnostics, AI chips, neural voice), a Foundry evaluation report, README screenshots and the
Copilot-through-MCP recording, the demo video, then the submission steps. Fabric is optional polish.

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
  1. Live UI check. The 2026-10-13 attempt (seed 7, speed 20, analyst and Spanish casual viewers) produced no
     broadcast record in 12 minutes: all 18 detected moments started at once and shared the single local model
     slot, so none finished, and a `godot` process from another project was saturating the machine at the same
     time. Retry when the machine is idle (check `ps -Ao pid,%cpu,comm -r | head` as well as `lsof` on 8080/8081)
     now that moment production has backpressure, with one viewer at speed 10 or lower:
     `MODEL_PROVIDER=mlx MODEL_NAME=ailexleon/Huihui-Qwen3.8-27B-abliterated-mlx-6Bit
     MODEL_BASE_URL=http://127.0.0.1:8081/v1 MODEL_TIMEOUT_S=240 MODEL_MAX_CONCURRENCY=1 API_PORT=8000
     .venv/bin/python -m insidegame.main`, then confirm the chips show AI (not Template) and the producer console
     shows model sources and fact-check verdicts.
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
  script first, since seed 7 now has new player names, home advantage, and spoken commentary.
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
- Simulator realism: many shots start on the byline (x 103 to 104 m), some from the corner flag at a near-zero
  angle, because a carry that reaches the byline ends in a shot instead of a cross or cutback. Calibration still
  passes, but the shot card and 3D view expose it. Fix in the possession chain (cross or cut back from wide byline
  positions), then rerun `insidegame.datasets.calibrate`; this changes seeded matches, including the seed 7 demo.
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
