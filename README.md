# Agent-based cross-domain simulation

Here we provide a cross-domain simulation workflow agent for coordinating end-use energy simulation with power-grid simulation. It provides a lightweight Python workflow layer that standardizes load profiles, maps end-use demand into grid models, runs or mocks external simulators, evaluates grid risk, and writes reproducible artifacts.

The repository now keeps runnable and planned workflows under `samples/`, while reusable source code remains under `src/x2g_agent/`.

## Available Samples

- `samples/single-building-to-grid`: a runnable Building-to-Grid workflow that couples one building load profile with an OpenDSS feeder.
- `samples/building-cluster-to-grid`: a scaffold for cluster-scale building-stock workflows and future ResStock/BuildStockBatch integration.

## Run The Single-Building Sample

The default single-building config runs in mock mode, so it does not require EnergyPlus or OpenDSS.

```bash
python samples/single-building-to-grid/scripts/run_building_to_grid.py --config samples/single-building-to-grid/configs/building_to_grid.yaml
```

You can also run it from the sample directory:

```bash
cd samples/single-building-to-grid
python scripts/run_building_to_grid.py --config configs/building_to_grid.yaml
```

Outputs are written under `samples/single-building-to-grid/outputs/building_to_grid/`.

## Run The Building-Cluster Sample

The cluster sample defaults to a synthetic backend that requires no ResStock or BuildStockBatch installation:

```bash
python samples/building-cluster-to-grid/src/run_case.py --backend synthetic
```

The `resstock` backend is scaffold-only and reports missing ResStock/BuildStockBatch dependencies clearly.

## Dependency Status

EnergyPlus is required for the existing real building simulation path in `samples/single-building-to-grid`. Mock mode remains available for tests and local smoke runs without EnergyPlus or OpenDSS execution.

ResStock and BuildStockBatch support is planned and scaffolded in `samples/building-cluster-to-grid`, but it is not implemented as an executable stock-simulation workflow yet.

## Development

Install the package in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Run the full test suite:

```bash
pytest
```

Current definition of done:

```bash
python samples/single-building-to-grid/scripts/run_building_to_grid.py --config samples/single-building-to-grid/configs/building_to_grid.yaml
pytest
```
