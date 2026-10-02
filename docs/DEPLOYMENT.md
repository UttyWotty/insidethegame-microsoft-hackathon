<!--
Step-by-step guide to deploying Inside the Game to Azure with the Azure Developer CLI.
It covers prerequisites, one-command provisioning, verification, CI/CD setup, costs, and teardown.
The infrastructure is defined in infra/ and the service in azure.yaml.
-->

# Deploying to Azure

One command provisions everything and deploys the app:

```bash
azd up
```

## What gets created

| Resource | Purpose |
|---|---|
| Microsoft Foundry (AI Services account) with a project | Hosts the model deployment used by all five agents |
| Model deployment (`gpt-4.1-mini`, GlobalStandard, 30K TPM by default) | Analyst, commentator, personalizer, translator, editor |
| Azure Container Apps (1 replica, 1 vCPU, 2 GiB) | Runs the single container: API under `/api`, frontend at `/` |
| Azure Container Registry (Basic) | Stores the image built from `Dockerfile` |
| User-assigned managed identity | Pulls the image and calls the model; no keys anywhere |
| Log Analytics + Application Insights | Container logs plus Agent Framework OpenTelemetry traces |

Security defaults: local (key) auth is **disabled** on the Foundry resource, the app authenticates with its
managed identity (`Cognitive Services OpenAI User` role only), the registry has no admin user, and the
container runs as a non-root user. Prompt and response contents are not sent to telemetry unless
`TELEMETRY_SENSITIVE_DATA=true`.

The app runs a single replica because live match sessions are held in memory.

## Prerequisites

1. An Azure subscription (a new free account includes credit).
2. Azure Developer CLI: `brew install --formula azure/azd/azd` (macOS) or see the azd docs.
3. Docker running locally (azd builds the image).

## Deploy

```bash
azd auth login
azd up
```

`azd up` asks for an environment name (for example `itg-dev`) and a region. Pick a region where your
subscription has quota for the model, for example `eastus2` or `swedencentral`. When it finishes it prints
the app URL (`SERVICE_WEB_URI`).

Optional overrides before `azd up`:

```bash
azd env set AZURE_MODEL_NAME gpt-4.1-mini
azd env set AZURE_MODEL_VERSION 2025-04-14
azd env set AZURE_MODEL_CAPACITY 30
```

## Verify

```bash
curl https://<app-url>/api/health        # configuration only, instant
curl https://<app-url>/api/diagnostics   # one real model call through the managed identity
```

Then open the app URL, kick off a match, and switch personas. Agent traces (each agent run, tool call, and
workflow step) appear in Application Insights under Transaction search.

## Run locally against the deployed model

`azd up` grants your own account model access, so after `azd auth login` you can run:

```bash
export MODEL_PROVIDER=foundry
export AZURE_OPENAI_ENDPOINT=$(azd env get-value AZURE_OPENAI_ENDPOINT)
export MODEL_NAME=$(azd env get-value AZURE_MODEL_DEPLOYMENT)
.venv/bin/python -m insidegame.main
```

`DefaultAzureCredential` picks up the azd sign-in, so no key is needed.

## Continuous deployment

```bash
azd pipeline config
```

This creates a federated credential for GitHub Actions and sets the repository variables used by
`.github/workflows/deploy.yml`. Deployments then run from the Actions tab (`Deploy`, manual trigger) without
any stored secrets.

## Costs and teardown

Costs are driven by model tokens, one always-on Container Apps replica, and a Basic registry. Remove
everything when you are done:

```bash
azd down --purge
```

`--purge` also permanently deletes the soft-deleted Foundry resource so its name can be reused.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `InsufficientQuota` during provisioning | Choose another region or lower `AZURE_MODEL_CAPACITY` |
| `/api/diagnostics` returns 401 or 403 | Role assignments can take a few minutes to propagate; retry |
| Overlays show the `Template` chip | The model call failed or timed out; check `/api/diagnostics` and Application Insights |
