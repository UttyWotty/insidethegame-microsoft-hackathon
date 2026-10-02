<!--
Open follow-ups and technical debt for Inside the Game, tracked in the repository so nothing is forgotten.
Resolved items are wrapped in HTML comments rather than deleted, preserving history.
Ordered by priority within each section.
-->

# Tech Debt and Follow-ups

## Azure go-live (needs a personal Azure subscription)

- Create the Azure free account (needs a credit card; do it on a personal machine, not the work laptop).
- Deploy: `azd auth login && azd up` from the repo root; pick a region with model quota (for example `eastus2` or `swedencentral`). See `docs/DEPLOYMENT.md`.
- Optionally protect MCP before deploying: `azd env set MCP_API_KEY "$(openssl rand -hex 24)"`.
- Verify: open `https://<app-url>/api/diagnostics` (one real model call through the managed identity), then use the app.
- Register the Foundry hosted agent: `uv pip install --python .venv/bin/python -e "backend[foundry]"`, then `eval "$(azd env get-values)"` and `.venv/bin/python -m insidegame.foundry.register --ask "Which matches are live?"`.
- Set up continuous deployment: `azd pipeline config`.
- Run the agent evaluation against Foundry and commit the report to `docs/evaluations/`.

## Submission (deadline 2026-10-27 23:59 PT)

- Record the demo video from `docs/DEMO_SCRIPT.md` (under 2 minutes, no copyrighted music) and upload it publicly.
- Make the GitHub repository public before submitting.
- Paste `docs/SUBMISSION.md` into the hackathon project page with the app URL and video link.
- Keep the deployment running until judging ends on 2026-11-10, then `azd down --purge`.

## Engineering

- Agents were last tested on a real model (MLX gemma-3-12b) before the Match Companion, distance tags, and recap changes; re-run the evaluation on a real model.
- Live sessions are in memory, so the app runs a single replica; move session state to a shared store before scaling out.
- `/api/matches` (match creation) has no per-client rate limit beyond the 20-session cap.
