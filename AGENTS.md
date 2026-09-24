# AGENTS.md

This project is B2G-Agent, a simulation-grounded AI mediator for building-grid co-design.

The primary vertical slice is the Harborview residential renewal scenario. A human participates as either a Building Engineer or Distribution Power Engineer, an AI NPC represents the counterpart, and B2G-Agent manages translation, simulation evidence, decision tracking, and final review.

## Repository Rules

- Keep reusable source code under `src/b2g_agent/`.
- Keep API keys and local simulator paths only in `.env`; never log, return, or commit them.
- The LLM may interpret intent and propose tool plans, but deterministic code must validate parameters and compute engineering metrics.
- Clearly distinguish deterministic vertical-scenario results from calibrated EnergyPlus/OpenDSS results.
- External software and MCP calls must be isolated behind adapters.
- Material model changes require an explicit confirmation policy.
- Unit tests must not require a real API key, EnergyPlus, OpenDSS, or MCP server unless marked as integration tests.
- Do not hard-code local paths. Use configuration, environment variables, or repository-relative paths.
- Large outputs belong under ignored `outputs/` or an external configured data root.

## Required Artifacts

Every mediated session must preserve:

- validated shared scenario state;
- speaker-attributed conversation turns;
- structured LLM plans without secrets;
- simulation run inputs, metrics, and backend identity;
- decision ledger;
- final Markdown review report.

## Definition Of Done

- `b2g-web` serves the four-stage local interface.
- A user can choose either role, complete a mediated turn, run the vertical scenario, and produce a final review.
- `python samples/single-building-to-grid/scripts/run_building_to_grid.py --config samples/single-building-to-grid/configs/building_to_grid.yaml` succeeds in mock mode.
- `pytest` passes.
- Secret scanning confirms no API key or populated `.env` is tracked.
