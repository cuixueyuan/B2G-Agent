from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from utils import building_to_bus_csv_path, buildings_csv_path, load_case_config, write_csv


BUILDING_TYPES = ["single_family_detached", "townhouse", "multifamily_unit"]
VINTAGES = ["pre_1980", "1980_2000", "post_2000"]
HVAC_TYPES = ["electric_resistance", "heat_pump", "gas_furnace_ac"]
LEVELS = ["low", "medium", "high"]
BUS_IDS = ["bus_3", "bus_4", "bus_5", "bus_6", "bus_7", "bus_8"]


def generate_building_samples(config: dict[str, Any], *, overwrite: bool = False) -> dict[str, Path]:
    buildings_path = buildings_csv_path()
    mapping_path = building_to_bus_csv_path()

    artifacts = {}
    if overwrite or not buildings_path.exists():
        artifacts["buildings"] = write_csv(buildings_path, _building_rows(config))
    else:
        artifacts["buildings"] = buildings_path

    if overwrite or not mapping_path.exists():
        artifacts["building_to_bus"] = write_csv(mapping_path, _building_to_bus_rows(config))
    else:
        artifacts["building_to_bus"] = mapping_path

    return artifacts


def _building_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    synthetic = config.get("synthetic", {})
    seed = int(synthetic.get("seed", 2026))
    rng = random.Random(seed)
    rows = []
    for index in range(1, int(config.get("n_buildings", 50)) + 1):
        building_type = rng.choice(BUILDING_TYPES)
        has_pv = rng.random() < 0.35
        has_battery = has_pv and rng.random() < 0.45

        rows.append(
            {
                "building_id": f"home_{index:03d}",
                "building_type": building_type,
                "vintage": rng.choice(VINTAGES),
                "floor_area_m2": round(rng.uniform(70.0, 250.0), 1),
                "num_stories": _num_stories(building_type, rng),
                "hvac_type": rng.choice(HVAC_TYPES),
                "heating_setpoint_c": round(rng.uniform(19.0, 22.0), 1),
                "cooling_setpoint_c": round(rng.uniform(23.0, 27.0), 1),
                "envelope_level": rng.choice(LEVELS),
                "occupancy_level": rng.choice(LEVELS),
                "has_pv": has_pv,
                "pv_kw": round(rng.uniform(1.0, 8.0), 2) if has_pv else 0.0,
                "has_battery": has_battery,
                "battery_kwh": round(rng.uniform(5.0, 20.0), 2) if has_battery else 0.0,
            }
        )
    return rows


def _num_stories(building_type: str, rng: random.Random) -> int:
    if building_type == "multifamily_unit":
        return rng.choice([1, 1, 2])
    if building_type == "townhouse":
        return rng.choice([2, 2, 3])
    return rng.choice([1, 2])


def _building_to_bus_rows(config: dict[str, Any]) -> list[dict[str, str]]:
    buses = [str(bus) for bus in config.get("grid", {}).get("buses", [])] or BUS_IDS
    return [
        {
            "building_id": f"home_{index:03d}",
            "bus_id": buses[(index - 1) % len(buses)],
        }
        for index in range(1, int(config.get("n_buildings", 50)) + 1)
    ]


def main() -> int:
    config = load_case_config()
    artifacts = generate_building_samples(config)
    for name, path in artifacts.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
