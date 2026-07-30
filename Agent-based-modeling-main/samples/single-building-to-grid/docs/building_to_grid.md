# Building-to-Grid Case Study

This document belongs to the archived sample at `samples/single-building-to-grid`. Commands below assume that directory is the current working directory.

## Research Question

How does an hourly building electricity demand profile affect distribution-feeder operating risk when it is injected at a specific grid bus?

The first X2G-Agent case study answers this question for one building and one radial feeder. It is designed as a reproducible coupling pattern rather than a final planning model: run or mock a building simulation, map the resulting load to a feeder bus, solve hourly power flow, and summarize voltage, loading, convergence, and peak-demand impacts.

## Software Coupling Logic

The coupling boundary is an hourly real-power load profile. EnergyPlus represents building energy behavior, while OpenDSS represents distribution-grid behavior.

The workflow separates responsibilities:

- EnergyPlus produces or informs building electricity demand.
- X2G-Agent standardizes that output as a clean hourly CSV.
- X2G-Agent maps the load to an OpenDSS bus and writes loadshape/input files.
- OpenDSSDirect.py solves feeder power flow for each hourly load point.
- X2G-Agent evaluates risk metrics and creates a report.

External simulator calls are wrapped under `src/x2g_agent/tools/` so agents can remain small and testable.

## Agent Workflow

The case uses simple agents with `run(state)` methods:

```text
EnergyPlusAgent
  -> LoadMappingAgent
  -> OpenDSSAgent
  -> MetricsAgent
  -> ReportAgent
```

Each agent reads the shared workflow state, adds rows or artifact paths, and returns the updated state. The executable entry point is:

```bash
python scripts/run_building_to_grid.py --config configs/building_to_grid.yaml
```

## Data Exchange Format

The core exchange format is CSV. The workflow produces standardized files under the configured `output_root`.

Key files include:

- `building_load.csv` or `load_profiles/building_load.csv`
- `mapped_building_load.csv`
- `opendss/building_loadshape.csv`
- `opendss/building_load_injection.dss`
- `power_flow_results.csv`
- `bus_voltage_pu_by_hour.csv`
- `feeder_power_by_hour.csv`
- `convergence_status_by_hour.csv`
- `risk_summary.csv`
- `report.md`

The mapped load CSV uses these main fields:

```text
timestamp,target_bus,load_name,phases,kv,building_kw,building_kvar
```

## EnergyPlus Output Standardization

In mock mode, X2G-Agent creates a deterministic hourly building load profile.

In real mode, X2G-Agent runs EnergyPlus with:

```bash
energyplus -w <epw_path> -d <energyplus_output_dir> <idf_path>
```

It reads EnergyPlus paths from `configs/building_to_grid.yaml` and `.env`:

```text
ENERGYPLUS_EXE=...
ENERGYPLUS_IDF=...
ENERGYPLUS_EPW=...
```

The standard output schema is:

```text
timestamp,electricity_kw
```

EnergyPlus outputs are searched in this order:

1. `eplusout.csv`
2. `eplusout.sql`
3. `eplusout.mtr`

For `eplusout.mtr`, the workflow extracts the exact `Electricity:Facility` meter. Hourly meter energy in Joules is converted to hourly average kW using:

```text
electricity_kw = joules / 3.6e6
```

Real-mode standardized loads are saved to:

```text
output_root/load_profiles/building_load.csv
```

## OpenDSS Load Injection

The sample feeder is:

```text
data_sample/opendss/simple_radial_feeder.dss
```

It defines a 12.47 kV four-bus radial feeder with three line segments and one building load at `bus_4`.

The OpenDSS agent writes:

```text
opendss/building_loadshape.csv
opendss/building_load_injection.dss
```

In OpenDSSDirect mode, the feeder is compiled once before the hourly loop. For each hour, the tool updates the target load kW/kvar and calls `Solve`.

## Power-Flow Risk Metrics

`MetricsAgent` summarizes:

- Voltage violation hours using configured minimum and maximum p.u. thresholds.
- Feeder peak load in kW.
- OpenDSS convergence failures.
- Line overload hours when line loading information is available.
- Minimum observed voltage.

The summary is written to:

```text
risk_summary.csv
```

## Reproduce With Anaconda

Create the environment:

```bash
conda create -n x2g-agent python=3.11 -y
conda activate x2g-agent
```

Install X2G-Agent:

```bash
python -m pip install -e ".[dev]"
```

Run mock mode:

```bash
python scripts/run_building_to_grid.py --config configs/building_to_grid.yaml
```

Run tests:

```bash
pytest
```

For real mode, install EnergyPlus separately, install OpenDSSDirect.py if needed, update `.env`, and set:

```yaml
case:
  mode: real
```

Then rerun the same script.

## Interpret Results

Start with `report.md` for the high-level summary. Then inspect:

- `risk_summary.csv` for voltage violations, feeder peak load, convergence failures, and overload counts.
- `bus_voltage_pu_by_hour.csv` to identify when and where low-voltage conditions occur.
- `feeder_power_by_hour.csv` to understand system-level demand timing.
- `power_flow_results.csv` for the combined hourly summary used by the metrics layer.
- `opendss/building_loadshape.csv` to verify the building load injected into the feeder.

For a well-behaved first run, expect zero convergence failures and voltages within the configured `thresholds`. Voltage violations or overloads indicate that the building load, placement, feeder impedance, or operating assumptions need closer review.
