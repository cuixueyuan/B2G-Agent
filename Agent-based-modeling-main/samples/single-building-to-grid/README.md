# Single-Building To Grid

This archived sample contains the original X2G-Agent single-building Building-to-Grid case. Commands in this README assume the current directory is `samples/single-building-to-grid`.

X2G-Agent is an agentic workflow library for coordinating end-use energy simulation and power-grid simulation.

The first case study is **Building-to-Grid**: a workflow that connects a single-building EnergyPlus simulation, or a mock building load profile, to an OpenDSS distribution power-flow analysis.

## Motivation

Buildings, vehicles, industrial loads, and data centers increasingly shape distribution-grid operating conditions. Energy models and grid models often live in separate tools, with manual file conversion between them. X2G-Agent provides a lightweight, testable workflow layer for coordinating these tools, standardizing load profiles, injecting them into feeders, evaluating grid risk, and producing reproducible reports.

The project starts small by making one building-to-grid loop work end to end, then grows toward broader end-use-to-grid workflows.

## Architecture

X2G-Agent uses simple stateful agents. Each agent receives a workflow `state`, adds data or artifacts, and returns the updated state.

```text
EnergyPlusAgent
  -> LoadMappingAgent
  -> OpenDSSAgent
  -> MetricsAgent
  -> ReportAgent
```

External simulator calls are wrapped under `src/x2g_agent/tools/`:

- `energyplus_tool.py` runs EnergyPlus or mock building-load generation.
- `opendss_tool.py` runs OpenDSSDirect.py or mock power-flow analysis.
- `load_parser.py` handles CSV load profile IO.
- `grid_metrics.py` summarizes voltage, convergence, peak-load, and line-loading risk.

## Building-to-Grid Workflow

The first workflow performs these steps:

1. Run EnergyPlus in real mode, or generate a deterministic mock building load.
2. Standardize building electricity demand as hourly average kW.
3. Map the building load to a target OpenDSS bus.
4. Write OpenDSS loadshape/input files.
5. Compile a radial feeder and solve hourly power-flow snapshots.
6. Export voltage, feeder power, convergence, and risk-summary CSVs.
7. Generate a Markdown report and figures.

## Installation With Anaconda

Create and activate a Python 3.11+ environment:

```bash
conda create -n x2g-agent python=3.11 -y
conda activate x2g-agent
```

Install the package in editable mode:

```bash
python -m pip install -e ".[dev]"
```

For real OpenDSS runs, install OpenDSSDirect.py:

```bash
python -m pip install opendssdirect.py
```

EnergyPlus must be installed separately from the official EnergyPlus distribution.

## Quickstart In Mock Mode

The default workflow supports mock mode so tests and examples can run without EnergyPlus or OpenDSS installed.

```bash
python scripts/run_building_to_grid.py --config configs/building_to_grid.yaml
```

Run tests:

```bash
pytest
```

## Conversational Mode

X2G-Agent includes a terminal chat interface for running the Building-to-Grid case from natural-language requests.

Architecture:

```text
User message -> LLM/rule parser -> validated actions -> Building-to-Grid workflow -> report summary
```

Rule-based chat mode is the default and does not call the OpenAI API:

```bash
python scripts/chat_building_to_grid.py --backend rule
```

OpenAI-backed LLM chat mode uses OpenAI only to parse user intent into validated actions. It calls the OpenAI API and may incur API cost:

```bash
python scripts/chat_building_to_grid.py --backend openai
```

Required `.env` settings for OpenAI-backed mode:

```text
OPENAI_API_KEY=your_openai_api_key_here
X2G_CHAT_BACKEND=rule
X2G_CHAT_MODEL=gpt-4.1-mini
```

Example prompts:

```text
Connect the building to bus_4 and run mock Building-to-Grid.
Set the load scale to 2.0 and summarize voltage violations.
Run real Building-to-Grid and generate the report.
```

Safety design:

- The LLM only parses user intent into validated actions.
- The deterministic workflow executes EnergyPlus and OpenDSS.
- The LLM does not directly modify simulation files or run shell commands.

The chat agent writes a temporary config under `outputs/chat_sessions/` and calls the same deterministic `run_building_to_grid` workflow used by the script interface. To inspect OpenAI parser behavior, add `--debug`.

## Real EnergyPlus + OpenDSSDirect Mode

Set the EnergyPlus paths in a local `.env` file. A template is provided in `.env.example`.

```text
ENERGYPLUS_EXE=D:/Energyplus/energyplus.exe
ENERGYPLUS_IDF=D:/Energyplus/Example_agent/18zone_OfficeMedium.idf
ENERGYPLUS_EPW=D:/Energyplus/WeatherData/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw
```

Use `case.mode: real` in `configs/building_to_grid.yaml`. EnergyPlus inputs are read from:

```yaml
energyplus:
  executable: "${ENERGYPLUS_EXE}"
  idf_path: "${ENERGYPLUS_IDF}"
  epw_path: "${ENERGYPLUS_EPW}"
```

OpenDSSDirect mode uses:

```yaml
opendss:
  backend: "opendssdirect"
  feeder_template: "../data_sample/opendss/simple_radial_feeder.dss"
  target_bus: "bus_4"
```

Then run:

```bash
python scripts/run_building_to_grid.py --config configs/building_to_grid.yaml
```

## Output Files

Each workflow run writes artifacts under the configured `output_root`.

Expected outputs include:

- `load_profiles/building_load.csv` for real EnergyPlus mode.
- `building_load.csv` for mock mode.
- `mapped_building_load.csv`.
- `opendss/building_loadshape.csv`.
- `opendss/building_load_injection.dss`.
- `power_flow_results.csv`.
- `bus_voltage_pu_by_hour.csv`.
- `feeder_power_by_hour.csv`.
- `convergence_status_by_hour.csv`.
- `risk_summary.csv`.
- `figures/*.svg`.
- `report.md`.

Large outputs should stay under `outputs/` or an external configured `data_root` and should not be committed.

## Repository Structure

```text
configs/
  building_to_grid.yaml
data_sample/
  opendss/
docs/
  building_to_grid.md
scripts/
  run_building_to_grid.py
outputs/
../../src/
  x2g_agent/
```

## Limitations

- The first workflow is intentionally small: one building mapped to one distribution feeder bus.
- Mock mode is deterministic and useful for testing, but it is not a substitute for calibrated building or feeder models.
- Real EnergyPlus parsing currently focuses on `Electricity:Facility` outputs from `eplusout.csv`, `eplusout.sql`, or `eplusout.mtr`.
- OpenDSS analysis currently targets hourly snapshot studies.
- Line-overload metrics are best effort and depend on available OpenDSS line ratings.

## Roadmap

- Building-to-Grid
- EV-to-Grid
- Industry-to-Grid
- DataCenter-to-Grid
- BuildStock-to-Grid

## Citation

Citation information will be added in a future release.

```bibtex
@software{x2g_agent,
  title = {X2G-Agent},
  author = {Xueyuan Cui},
  year = {2026},
  note = {Agentic workflows for end-use-to-grid simulation}
}
```

## License

This project is released under the MIT License. See `LICENSE` for details when available.
