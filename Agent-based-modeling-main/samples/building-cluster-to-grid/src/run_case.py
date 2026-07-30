from __future__ import annotations

import argparse
import json
from pathlib import Path

from aggregate_loads_to_buses import aggregate_loads_to_buses
from generate_building_samples import generate_building_samples
from resstock_backend import run_resstock_backend
from run_grid_simulation import run_grid_simulation
from synthetic_backend import run_synthetic_backend
from utils import ensure_output_dirs, load_case_config, log_message


SAMPLE_ROOT = Path(__file__).resolve().parents[1]


def run_case(backend: str = "synthetic", config_path: str | Path = "config/case_config.yaml") -> dict[str, Path]:
    config = load_case_config(config_path)
    ensure_output_dirs(config)
    log_message(config, f"Starting Building-Cluster-to-Grid sample with backend={backend}")

    generate_building_samples(config)

    if backend == "resstock":
        run_resstock_backend(config)
    else:
        run_synthetic_backend(config)

    bus_loads_csv = aggregate_loads_to_buses(config)
    grid_artifacts = run_grid_simulation(config)

    artifacts = {
        "bus_loads_csv": bus_loads_csv,
        **grid_artifacts,
    }
    log_message(config, f"Completed Building-Cluster-to-Grid run with backend={backend}.")
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Building-Cluster-to-Grid sample.")
    default_backend = load_case_config().get("default_backend", "synthetic")
    parser.add_argument("--backend", choices=["synthetic", "resstock"], default=default_backend)
    parser.add_argument("--config", default="config/case_config.yaml", help="Path to sample case config.")
    args = parser.parse_args()

    try:
        artifacts = run_case(args.backend, args.config)
    except RuntimeError as exc:
        print(str(exc))
        return 2

    if args.backend == "synthetic":
        print_final_summary(args.backend, artifacts)
    return 0


def print_final_summary(backend: str, artifacts: dict[str, Path]) -> None:
    summary_path = artifacts["summary_json"]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    print(f"Building-Cluster-to-Grid run completed with backend={backend}.")
    print("Final summary:")
    print(f"- feeder_peak_load_kw: {summary['feeder_peak_load_kw']}")
    print(f"- feeder_peak_net_load_kw: {summary['feeder_peak_net_load_kw']}")
    print(f"- min_voltage_pu: {summary['min_voltage_pu']}")
    print(f"- max_line_loading_percent: {summary['max_line_loading_percent']}")
    print(f"- total_energy_kwh: {summary['total_energy_kwh']}")
    print(f"- total_net_energy_kwh: {summary['total_net_energy_kwh']}")
    print("Output paths:")
    for name, path in sorted(artifacts.items()):
        print(f"- {name}: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
