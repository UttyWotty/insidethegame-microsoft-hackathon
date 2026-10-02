<!--
Architecture overview of Inside the Game: the five-stage pipeline, the multi-agent workflow, and the Azure deployment.
Diagrams are Mermaid so they render on GitHub and stay versioned with the code.
Each section maps a challenge requirement to the component that fulfils it.
-->

# Architecture

## Five-stage pipeline

```mermaid
flowchart LR
    subgraph S1[1 Ingest]
        SIM[Seeded match simulator<br/>possession chains, styles, fatigue]
    end
    subgraph S2[2 Interpret]
        AN[MatchAnalyzer<br/>xG, pass difficulty, stats,<br/>momentum, control vs chaos]
        KM[Key moment detector<br/>importance + facts]
    end
    subgraph S3[3 Explain]
        WF[Agent Framework workflow<br/>analyst, commentator]
    end
    subgraph S4[4 Render]
        CUE[Timed overlay cues<br/>layout, timing, provenance]
    end
    subgraph S5[5 Personalize]
        PER[Personalizer + translator<br/>5 personas, any language]
        QA[Match Companion<br/>viewer questions]
    end
    SIM -->|events| AN --> KM -->|moments| WF --> PER --> CUE
    AN -. live stats .-> QA
    CUE -->|SSE per viewer segment| UI[Broadcast UI<br/>pitch, overlays, multiview]
    AN -. tools .-> MCP[MCP server /mcp]
    SIM --> DS[Dataset generator<br/>JSON Lines + card]
```

Stages 1 and 2 are deterministic code, so the event feed keeps match pace and is fully testable. Language models
are used only where judgement and language matter (stages 3 to 5), and every model output is validated.

## Multi-agent workflow (per key moment)

```mermaid
flowchart LR
    P[Producer policy<br/>pacing, relevance] --> I[Intake<br/>writes job to shared state]
    I --> A[Match Analyst<br/>tools: player stats,<br/>team comparison, recent moments]
    A -->|explanation in shared state| N[Lead Commentator]
    A --> Z[Personalization Producer<br/>one card per viewer segment, concurrent]
    Z -->|language is not English| T[Broadcast Translator]
    N --> J[Assembler<br/>fan-in, reads shared state]
    Z --> J
    T --> J
    J --> C[Overlay cues with provenance]
```

| Agent | Role | Output |
|---|---|---|
| Match Analyst | Why a moment matters, with tool-based evidence | `Explanation` |
| Lead Commentator | One live commentary line | `Commentary` |
| Personalization Producer | Persona card in voice, vocabulary, perspective, budget | `PersonaCard` |
| Broadcast Translator | Localised card with names and numbers preserved | `TranslatedCard` |
| Match Editor | Half-time and full-time recaps | `MatchRecap` |
| Match Companion | Answers viewer questions, any persona and language | `CompanionAnswer` |

### Reliability: every agent call

```mermaid
flowchart LR
    C[Agent call] --> V{Valid schema and<br/>numbers grounded?}
    V -->|yes| OK[Use output<br/>source: model]
    V -->|no| R[Retry once with<br/>the rejection reason]
    R --> V2{Valid?}
    V2 -->|yes| OK2[Use output<br/>source: model_retry]
    V2 -->|no| F[Grounded template<br/>source: fallback]
    C -->|timeout| F
```

If the workflow itself fails, a degraded template path still produces cues for every viewer. Every cue records
the source, attempts, and latency of each agent that produced it.

## Live delivery

- Interpretation runs inline at match pace; agent workflows and recaps run as background tasks.
- Viewers with identical preferences share a segment, so model cost scales with distinct preferences.
- Late joiners receive the current snapshot, recent cues, recaps, and personalized backfill of recent moments.
- Slow clients drop their oldest queued messages, never the newest.

## Azure deployment

```mermaid
flowchart LR
    U[Viewers] --> CA[Azure Container Apps<br/>FastAPI + React, /api, /mcp]
    GH[GitHub Copilot or<br/>Foundry agents] -->|MCP| CA
    CA -->|managed identity, no keys| F[Microsoft Foundry<br/>project + model deployment]
    CA -->|OpenTelemetry| AI[Application Insights]
    CR[Container Registry] -->|managed identity pull| CA
    GA[GitHub Actions<br/>CI + OIDC deploy] -->|azd up| CA
```

Provisioned by `azd up` from Bicep in `infra/`. See [DEPLOYMENT.md](DEPLOYMENT.md).
