# Building Cluster to Grid Sample

## Purpose

This sample extends the single-building workflow to a 50-building residential cluster. It demonstrates how X2G-Agent can coordinate building-stock energy simulation outputs with distribution-grid simulation.

## Current Implementation

- `synthetic` backend: runnable now, no ResStock/BuildStockBatch required.
- `resstock` backend: scaffolded for future integration.

The synthetic backend mimics ResStock-style heterogeneous residential load profiles, but it is not a real ResStock simulation.

## Run

```bash
cd samples/building-cluster-to-grid
python src/run_case.py --backend synthetic
```

## Expected Outputs

- `outputs/building_loads/building_loads.csv`
- `outputs/bus_loads/bus_loads.csv`
- `outputs/grid_results/grid_results.csv`
- `outputs/grid_results/summary.json`

## Future ResStock/BuildStockBatch Workflow

1. Clone/configure ResStock.
2. Install BuildStockBatch.
3. Prepare a precomputed 50-building sample.
4. Run BuildStockBatch locally.
5. Collect EnergyPlus time-series outputs.
6. Convert them to the same `building_loads.csv` interface.
7. Run the same bus aggregation and grid simulation pipeline.
