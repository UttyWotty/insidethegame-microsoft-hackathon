<!--
Open follow-ups and technical debt for Inside the Game, tracked in the repository so nothing is forgotten.
Resolved items are wrapped in HTML comments rather than deleted, preserving history.
Ordered by priority within each section; status as of 2026-10-12 (develop at PR #28, release v0.1.0 on main).
-->

# Tech Debt and Follow-ups

## Blockers before submitting

<!--
- Check the employment contract (or get written permission): the project was built on a work laptop, and the rules
  require the submission to be solely owned by the entrant (rules 4.6 and 4.11). Use a personal machine from now on.
  Resolved 2026-10-12: the owner confirmed this machine is approved for the project.
-->
- Agents have never been seen with real AI output in the UI; every chip shows "Template" in offline mode. Validate on
  a real model (MLX locally, then Foundry) before recording anything.
  Next run (planned 2026-10-13), local model chosen by the owner: Qwen3.8 27B 6-bit
  (`ailexleon/Huihui-Qwen3.8-27B-abliterated-mlx-6Bit`) on the existing MLX gateway at `127.0.0.1:8081`
  (launchd agent `local.mlx-serve-qwen38`; do not start a separate server).
  1. Confirm no other workload is live: nothing else connected to ports 8080 and 8081
     (`lsof -nP -iTCP:8081 -sTCP:ESTABLISHED`) and no other MLX job running (on 2026-10-12 an image-generation job in
     another repo took both gateways down mid-run). Check `curl -s http://127.0.0.1:8081/v1/models` returns the model.
  2. Evaluate: `MODEL_PROVIDER=mlx MODEL_NAME=ailexleon/Huihui-Qwen3.8-27B-abliterated-mlx-6Bit
     MODEL_BASE_URL=http://127.0.0.1:8081/v1 MODEL_TIMEOUT_S=240 MODEL_MAX_CONCURRENCY=1
     .venv/bin/python -m insidegame.evaluation.run --max-moments 3
     --output docs/evaluations/2026-10-13-mlx-qwen3.8-27b-6bit.json`. The 240-second timeout is needed: warm speed
     is about 18 tokens/s prefill and 11 tokens/s decode, so the default 45 seconds would time out.
  3. Run a live match in the UI with the same variables and confirm the chips show model output (not "Template")
     for analyst, narrator, translator, persona cards, fact-checker, and recaps; note anything that falls back.
  4. Fix prompt or parsing issues found, commit the report, and update the README "Latest local run" line.

## Azure go-live (needs a personal Azure subscription)

- Create the Azure free account (needs a credit card; do it on a personal machine, not the work laptop).
- Deploy: `azd auth login && azd up` from the repo root; pick a region with model quota (for example `eastus2` or `swedencentral`). See `docs/DEPLOYMENT.md`.
- Before deploying, protect write and cost endpoints: `azd env set MCP_API_KEY "$(openssl rand -hex 24)"` and set `PRODUCER_KEY` on the container app.
- Verify: open `https://<app-url>/api/diagnostics` (one real model call through the managed identity), then use the app.
- Register the Foundry hosted agent: `uv pip install --python .venv/bin/python -e "backend[foundry]"`, then `eval "$(azd env get-values)"` and `.venv/bin/python -m insidegame.foundry.register --ask "Which matches are live?"`.
- Set up continuous deployment: `azd pipeline config`.
- Run `python -m insidegame.evaluation.run --max-moments 6` against Foundry, fix prompt or quality issues it shows, and commit the report to `docs/evaluations/`.

## Features that raise the chance of winning

- Spoken commentary with Azure AI Speech (text to speech per language) for moment commentary and play-by-play; strongest "multi-language storytelling" and Microsoft-service showcase.
- Microsoft Fabric: load `datasets.generate` output into a Fabric lakehouse and build a small Power BI report; reference it in the submission.
- Foundry evaluations (groundedness, relevance) on agent outputs, linked from the producer console or docs.
- GitHub Copilot: record Copilot agent mode in VS Code querying the live match through the MCP server (`.vscode/mcp.json` example in README); also register the Foundry hosted agent and show it in the portal.
<!--
- Tracking frames in the dataset export (`tracking.jsonl`, sampled) to strengthen the synthetic data story.
  Resolved 2026-10-13 in PR #30.
-->

## Submission (deadline 2026-10-27 23:59 PT)

- Retake README screenshots (`docs/images/`): they predate the 22-player broadcast pitch, landing screen, fact-check chips, and producer console; capture them with real AI output.
- Record the demo video from `docs/DEMO_SCRIPT.md` (under 2 minutes, no copyrighted music); update the script to include the broadcast camera, fact-checker, producer console, and Copilot or Foundry agent via MCP.
<!--
- Update `docs/SUBMISSION.md` with the seven agents, tracking, fact-checking, and producer console.
  Resolved 2026-10-13: submission text and demo script refreshed.
-->
- Cut release `v0.2.0` through Git Flow once deployed and validated.
- Make the GitHub repository public before submitting.
- Paste `docs/SUBMISSION.md` into the hackathon project page with the app URL and video link.
- Keep the deployment running until judging ends on 2026-11-10, then `azd down --purge`.

## Engineering

- Live sessions are in memory, so the app runs a single replica; move session state to a shared store before scaling out.
- `/api/matches` (match creation) has no per-client rate limit beyond the 20-session cap.
- Tracking-derived player speeds are unrealistic (teleporting event actors), so speed indicators use modelled shot and ball speeds only; smoothing or a kinematic model would allow real sprint tags.
- Local MLX runs are slow (10 to 35 seconds per call with one call at a time); try the Qwen 35B A3B MoE model or a concurrency of 2 if local testing matters.
- The producer console polls every 2 seconds; move it to the event stream if it needs to scale.
- The GitHub CLI's active account on this machine switched to UtkuGulbardak; commands for this repo use `GH_TOKEN=$(gh auth token --user UttyWotty)`.
