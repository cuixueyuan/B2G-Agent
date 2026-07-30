from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from utils import buildings_csv_path, ensure_output_dirs, read_csv, simulation_hours, time_step_minutes, write_csv


def run_synthetic_backend(config: dict[str, Any]) -> list[Path]:
    paths = ensure_output_dirs(config)
    buildings = read_csv(buildings_csv_path())
    start = datetime.fromisoformat("2024-01-01T00:00:00")
    hours = simulation_hours(config)
    step_minutes = time_step_minutes(config)
    seed = int(config.get("synthetic", {}).get("seed", 2026))

    rows = []
    for index, building in enumerate(buildings):
        rows.extend(generate_profile(building, start, hours, step_minutes, seed + index))

    path = write_csv(paths["building_loads_csv"], rows)
    return [path]


def generate_profile(building: dict[str, Any], start: datetime, hours: int, step_minutes: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows = []
    for hour_index in range(hours):
        timestamp = start + timedelta(minutes=hour_index * step_minutes)
        hour = timestamp.hour
        appliance_kw = appliance_load_kw(building, hour, rng)
        cooling_kw = cooling_load_kw(building, hour, rng)
        heating_kw = heating_load_kw(building, hour, rng)
        load_kw = appliance_kw + cooling_kw + heating_kw
        pv_kw = pv_generation_kw(building, hour)
        net_load_kw = load_kw - pv_kw
        rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "building_id": building["building_id"],
                "load_kw": round(load_kw, 6),
                "cooling_kw": round(cooling_kw, 6),
                "heating_kw": round(heating_kw, 6),
                "appliance_kw": round(appliance_kw, 6),
                "pv_kw": round(pv_kw, 6),
                "net_load_kw": round(net_load_kw, 6),
            }
        )
    return rows


def appliance_load_kw(building: dict[str, Any], hour: int, rng: random.Random) -> float:
    area = float(building["floor_area_m2"])
    occupancy = {"low": 0.75, "medium": 1.0, "high": 1.25}[building["occupancy_level"]]
    evening_bump = 0.45 * gaussian(hour, 20, 2.8)
    morning_bump = 0.22 * gaussian(hour, 7, 2.2)
    noise = rng.uniform(-0.025, 0.035)
    return max(0.08, area * 0.0032 * occupancy * (1.0 + morning_bump + evening_bump + noise))


def cooling_load_kw(building: dict[str, Any], hour: int, rng: random.Random) -> float:
    area = float(building["floor_area_m2"])
    envelope = {"low": 1.25, "medium": 1.0, "high": 0.78}[building["envelope_level"]]
    hvac = {"electric_resistance": 1.08, "heat_pump": 0.82, "gas_furnace_ac": 1.0}[building["hvac_type"]]
    setpoint = float(building["cooling_setpoint_c"])
    setpoint_factor = max(0.55, 1.0 - 0.06 * (setpoint - 24.0))
    afternoon_shape = gaussian(hour, 16, 4.0)
    small_variation = 1.0 + rng.uniform(-0.04, 0.04)
    return max(0.0, area * 0.0105 * envelope * hvac * setpoint_factor * afternoon_shape * small_variation)


def heating_load_kw(building: dict[str, Any], hour: int, rng: random.Random) -> float:
    area = float(building["floor_area_m2"])
    envelope = {"low": 1.25, "medium": 1.0, "high": 0.78}[building["envelope_level"]]
    hvac = {"electric_resistance": 1.0, "heat_pump": 0.62, "gas_furnace_ac": 0.12}[building["hvac_type"]]
    setpoint = float(building["heating_setpoint_c"])
    setpoint_factor = 0.8 + 0.08 * (setpoint - 19.0)
    early_shape = gaussian(hour, 6, 3.0)
    small_variation = 1.0 + rng.uniform(-0.03, 0.03)
    summer_demo_scale = 0.18
    return max(0.0, area * 0.004 * envelope * hvac * setpoint_factor * early_shape * small_variation * summer_demo_scale)


def pv_generation_kw(building: dict[str, Any], hour: int) -> float:
    if str(building["has_pv"]).lower() not in {"true", "1", "yes"}:
        return 0.0
    pv_capacity_kw = float(building["pv_kw"])
    daytime_shape = gaussian(hour, 13, 3.2)
    if hour < 6 or hour > 20:
        return 0.0
    return max(0.0, pv_capacity_kw * daytime_shape)


def gaussian(hour: int, center: int, width: float) -> float:
    distance = min(abs(hour - center), 24 - abs(hour - center))
    return math.exp(-0.5 * (distance / width) ** 2)
