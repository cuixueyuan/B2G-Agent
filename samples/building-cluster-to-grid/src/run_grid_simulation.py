from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from utils import ensure_output_dirs, load_case_config, read_csv, write_csv


def run_grid_simulation(config: dict[str, Any]) -> dict[str, Path]:
    paths = ensure_output_dirs(config)
    bus_loads = read_csv(paths["bus_loads_csv"])
    if not bus_loads:
        raise RuntimeError("No bus loads found. Run aggregate_loads_to_buses.py first.")

    feeder = SyntheticRadialFeeder.from_bus_loads(bus_loads, config)
    grid_rows = []
    for timestamp, rows in sorted(group_by_timestamp(bus_loads).items()):
        grid_rows.append(feeder.solve(timestamp, rows))

    grid_results_csv = write_csv(paths["grid_results_csv"], grid_rows)
    summary_json = write_summary(paths["summary_json"], summarize_grid_results(grid_rows))
    return {
        "grid_results_csv": grid_results_csv,
        "summary_json": summary_json,
    }


class SyntheticRadialFeeder:
    """Small deterministic radial feeder for the cluster sample.

    This mirrors the single-building sample's mock grid style: it is not a
    detailed OpenDSS model, but it preserves the important coupling behavior by
    mapping bus-level net load onto feeder locations and producing hourly grid
    risk signals.
    """

    def __init__(
        self,
        bus_order: list[str],
        line_rating_kw: float,
        source_voltage_pu: float,
        voltage_drop_per_100kw: float,
        loss_at_rating_kw: float,
    ) -> None:
        self.bus_order = bus_order
        self.line_rating_kw = line_rating_kw
        self.source_voltage_pu = source_voltage_pu
        self.voltage_drop_per_100kw = voltage_drop_per_100kw
        self.loss_at_rating_kw = loss_at_rating_kw

    @classmethod
    def from_bus_loads(cls, bus_loads: list[dict[str, str]], config: dict[str, Any]) -> SyntheticRadialFeeder:
        grid = config.get("grid", {})
        bus_order = [str(bus) for bus in grid.get("buses", [])] or sorted({row["bus_id"] for row in bus_loads}, key=bus_sort_key)
        return cls(
            bus_order=bus_order,
            line_rating_kw=600.0,
            source_voltage_pu=1.0,
            voltage_drop_per_100kw=0.006,
            loss_at_rating_kw=6.0,
        )

    def solve(self, timestamp: str, rows: list[dict[str, str]]) -> dict[str, Any]:
        by_bus = {row["bus_id"]: row for row in rows}
        bus_net_kw = {bus: float(by_bus.get(bus, {}).get("net_load_kw", 0.0)) for bus in self.bus_order}
        bus_load_kw = {bus: float(by_bus.get(bus, {}).get("load_kw", 0.0)) for bus in self.bus_order}

        downstream_flows = self.downstream_line_flows(bus_net_kw)
        voltages = self.bus_voltages(downstream_flows)
        line_loading = [
            abs(flow_kw) / self.line_rating_kw * 100.0 if self.line_rating_kw else 0.0
            for flow_kw in downstream_flows
        ]
        losses = [
            (abs(flow_kw) / self.line_rating_kw) ** 2 * self.loss_at_rating_kw if self.line_rating_kw else 0.0
            for flow_kw in downstream_flows
        ]

        total_load_kw = sum(bus_load_kw.values())
        total_net_load_kw = sum(bus_net_kw.values())
        return {
            "timestamp": timestamp,
            "min_voltage_pu": round(min(voltages), 6) if voltages else round(self.source_voltage_pu, 6),
            "max_line_loading_percent": round(max(line_loading), 6) if line_loading else 0.0,
            "total_load_kw": round(total_load_kw, 6),
            "total_net_load_kw": round(total_net_load_kw, 6),
            "grid_loss_kw": round(sum(losses), 6),
        }

    def downstream_line_flows(self, bus_net_kw: dict[str, float]) -> list[float]:
        flows = []
        for index in range(len(self.bus_order)):
            downstream_buses = self.bus_order[index:]
            flows.append(sum(bus_net_kw[bus] for bus in downstream_buses))
        return flows

    def bus_voltages(self, downstream_flows: list[float]) -> list[float]:
        voltages = []
        voltage = self.source_voltage_pu
        for flow_kw in downstream_flows:
            if flow_kw >= 0:
                voltage -= (flow_kw / 100.0) * self.voltage_drop_per_100kw
            else:
                voltage += (abs(flow_kw) / 100.0) * self.voltage_drop_per_100kw * 0.35
            voltages.append(voltage)
        return voltages


def group_by_timestamp(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["timestamp"], []).append(row)
    return grouped


def summarize_grid_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "feeder_peak_load_kw": round(max((float(row["total_load_kw"]) for row in rows), default=0.0), 6),
        "feeder_peak_net_load_kw": round(max((float(row["total_net_load_kw"]) for row in rows), default=0.0), 6),
        "min_voltage_pu": round(min((float(row["min_voltage_pu"]) for row in rows), default=0.0), 6),
        "max_line_loading_percent": round(max((float(row["max_line_loading_percent"]) for row in rows), default=0.0), 6),
        "total_energy_kwh": round(sum(float(row["total_load_kw"]) for row in rows), 6),
        "total_net_energy_kwh": round(sum(float(row["total_net_load_kw"]) for row in rows), 6),
    }


def write_summary(path: Path, summary: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path


def bus_sort_key(bus_id: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", bus_id)
    if match:
        return (int(match.group(1)), bus_id)
    return (10_000, bus_id)


def main() -> int:
    config = load_case_config()
    artifacts = run_grid_simulation(config)
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
