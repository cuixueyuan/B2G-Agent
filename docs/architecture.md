# B2G-Agent Architecture

## Product Boundary

B2G-Agent is a mediator and orchestrator. It does not replace professional judgment or numerical simulation. The LLM is allowed to interpret language, propose a structured plan, generate role-aware explanations, and guide the negotiation. It is not allowed to invent engineering metrics, bypass parameter validation, or silently apply material model changes.

## Runtime Components

```text
Four-stage browser UI
        |
        v
FastAPI session service
        |
        +-- CollaborationSession
        |     +-- participant roles
        |     +-- shared ScenarioParameters
        |     +-- conversation history
        |     +-- simulation runs
        |     +-- decision ledger
        |
        +-- B2GMediator
        |     +-- planning pass -> MediatorPlan
        |     +-- parameter whitelist
        |     +-- confirmation policy
        |     +-- response pass -> MediatedReply
        |     +-- offline fallback
        |
        +-- Simulation adapter boundary
        |     +-- ResidentialCommunitySimulator (implemented)
        |     +-- legacy EnergyPlus/OpenDSS wrappers (available)
        |     +-- EnergyPlus-MCP adapter (planned)
        |     +-- PowerMCP/OpenDSS adapter (planned)
        |
        +-- outputs/web_sessions/<session-id>/
              +-- session.json
              +-- final_plan.md
```

## Two-Pass LLM Design

The first pass is a planner. It receives the human role, counterpart role, current shared case, recent conversation, and new message. It must return a `MediatorPlan` JSON object containing:

- interpreted professional intent;
- counterpart-facing translation;
- changes limited to the scenario whitelist;
- building, grid, coupled, or no-simulation scope;
- assumptions, confidence, and confirmation requirement.

Typed Pydantic models validate this response. Unsupported parameter names or out-of-range values are rejected before execution.

The second pass is an evidence communicator. It receives the validated plan, the current case, and—only if a run occurred—the computed simulation result. It produces separate mediator and counterpart messages. This ordering prevents the LLM from presenting invented numbers as simulation evidence.

## Shared Boundary Object

`ScenarioParameters` is the current cross-domain boundary object. Both roles see and modify the same state:

- cooling setpoint;
- number of buildings;
- retrofit level;
- rooftop PV;
- demand response;
- connection bus;
- transformer capacity;
- line capacity.

Each simulation run stores an immutable copy of these inputs with its metrics and hourly timeseries. Conversation messages refer to run identifiers rather than an untracked “current result.”

## Confirmation Policy

The LLM may mark an interpretation as requiring confirmation. B2G-Agent then stores the proposed change without applying it. Only a subsequent explicit confirmation executes the change and simulation. The next MCP integration phase should extend this policy with per-tool risk levels:

- read-only inspection: automatic;
- reversible scenario edit: automatic or configurable;
- topology, equipment, or broad file modification: explicit confirmation;
- action outside the scenario root: prohibited.

## Backend Contract

A simulation backend must accept validated shared state and return:

- backend identity and run identifier;
- complete parameter snapshot;
- hourly load, voltage, and loading evidence;
- aggregate constraint metrics;
- convergence or execution status;
- findings derived from computed values;
- paths or identifiers sufficient for reproduction.

The UI and mediator consume this contract and do not depend on a particular simulator implementation.
