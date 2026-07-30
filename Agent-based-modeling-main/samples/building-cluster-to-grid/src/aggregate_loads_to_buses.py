from __future__ import annotations

from pathlib import Path
from typing import Any

from utils import building_to_bus_csv_path, ensure_output_dirs, load_case_config, read_csv, write_csv


def aggregate_loads_to_buses(config: dict[str, Any]) -> Path:
    paths = ensure_output_dirs(config)
    assignments = {
        row["building_id"]: row["bus_id"]
        for row in read_csv(building_to_bus_csv_path())
    }
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    load_rows = read_csv(paths["building_loads_csv"])

    for row in load_rows:
        building_id = row["building_id"]
        bus_id = assignments[building_id]
        key = (bus_id, row["timestamp"])
        if key not in grouped:
            grouped[key] = {
                "timestamp": row["timestamp"],
                "bus_id": bus_id,
                "load_kw": 0.0,
                "pv_kw": 0.0,
                "net_load_kw": 0.0,
            }
        grouped[key]["load_kw"] += float(row["load_kw"])
        grouped[key]["pv_kw"] += float(row["pv_kw"])
        grouped[key]["net_load_kw"] += float(row["net_load_kw"])

    bus_rows = []
    for (_bus_id, _timestamp), row in sorted(grouped.items()):
        bus_rows.append(
            {
                "timestamp": row["timestamp"],
                "bus_id": row["bus_id"],
                "load_kw": round(row["load_kw"], 6),
                "pv_kw": round(row["pv_kw"], 6),
                "net_load_kw": round(row["net_load_kw"], 6),
            }
        )

    output_path = write_csv(paths["bus_loads_csv"], bus_rows)
    print_summary(load_rows, bus_rows)
    return output_path


def print_summary(load_rows: list[dict[str, str]], bus_rows: list[dict[str, Any]]) -> None:
    building_ids = {row["building_id"] for row in load_rows}
    bus_ids = {row["bus_id"] for row in bus_rows}
    by_timestamp: dict[str, dict[str, float]] = {}
    for row in bus_rows:
        timestamp = row["timestamp"]
        if timestamp not in by_timestamp:
            by_timestamp[timestamp] = {"load_kw": 0.0, "net_load_kw": 0.0}
        by_timestamp[timestamp]["load_kw"] += float(row["load_kw"])
        by_timestamp[timestamp]["net_load_kw"] += float(row["net_load_kw"])

    peak_total_load = max((values["load_kw"] for values in by_timestamp.values()), default=0.0)
    min_total_net_load = min((values["net_load_kw"] for values in by_timestamp.values()), default=0.0)
    print("Bus load aggregation summary:")
    print(f"- number of buildings: {len(building_ids)}")
    print(f"- number of buses: {len(bus_ids)}")
    print(f"- peak total load: {peak_total_load:.3f} kW")
    print(f"- minimum total net load: {min_total_net_load:.3f} kW")


def main() -> int:
    config = load_case_config()
    path = aggregate_loads_to_buses(config)
    print(f"bus_loads_csv: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
