# AGENTS.md

This project is X2G-Agent, an agentic workflow library for coordinating end-use energy simulation and power-grid simulation.

The first case study is Building-to-Grid: a workflow that coordinates a single-building EnergyPlus simulation or mock building simulation with OpenDSS distribution power-flow analysis.

## Repository Rules

- Keep source code under `src/x2g_agent/`.
- External software calls must be wrapped under `src/x2g_agent/tools/`.
- Unit tests must not require real EnergyPlus or OpenDSS execution unless they are explicitly marked as integration tests.
- Do not hard-code local paths. Use config values, environment variables, and paths relative to the config file or repository root.
- Keep small sample data under each sample's `data_sample/`.
- Large outputs should go to each sample's `outputs/` or an external configured `data_root` and should not be committed.

## Workflow Artifacts

Every workflow run should produce:

- Building load CSV.
- OpenDSS input/loadshape files.
- Power-flow result CSV.
- Risk summary CSV.
- Markdown report.

## Definition Of Done

- `python samples/single-building-to-grid/scripts/run_building_to_grid.py --config samples/single-building-to-grid/configs/building_to_grid.yaml` runs successfully in mock mode.
- `pytest` passes.
