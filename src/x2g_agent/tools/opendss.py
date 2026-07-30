from __future__ import annotations

import math
from pathlib import Path


def run_hourly_power_flow(load_rows: list[dict], config: dict) -> list[dict]:
    mode = config.get("mode", "mock")
    if mode == "direct":
        return _run_opendssdirect(load_rows, config)
    if mode == "mock":
        return _run_mock_power_flow(load_rows, config)
    raise ValueError(f"Unsupported OpenDSS mode: {mode}")


def _run_mock_power_flow(load_rows: list[dict], config: dict) -> list[dict]:
    mock = config.get("mock", {})
    source_voltage = float(mock.get("source_voltage_pu", 1.0))
    drop_per_100kw = float(mock.get("voltage_drop_per_100kw", 0.012))
    feeder_base_kw = float(mock.get("feeder_base_kw", 120.0))
    line_rating_kw = float(mock.get("line_rating_kw", 350.0))
    target_bus = config.get("target_bus") or config.get("bus") or "loadbus"

    rows = []
    for row in load_rows:
        building_kw = float(row["building_kw"])
        building_kvar = float(row.get("building_kvar", 0.0))
        feeder_kw = feeder_base_kw + building_kw
        voltage = source_voltage - (feeder_kw / 100.0) * drop_per_100kw
        line_loading_pct = feeder_kw / line_rating_kw * 100.0 if line_rating_kw else math.nan
        rows.append(
            {
                "timestamp": row["timestamp"],
                "bus": target_bus,
                "building_kw": round(building_kw, 6),
                "building_kvar": round(building_kvar, 6),
                "feeder_kw": round(feeder_kw, 6),
                "min_voltage_pu": round(voltage, 6),
                "max_line_loading_pct": round(line_loading_pct, 6),
                "converged": True,
            }
        )
    return rows


def _run_opendssdirect(load_rows: list[dict], config: dict) -> list[dict]:
    try:
        import opendssdirect as dss
    except ImportError as exc:
        raise RuntimeError("OpenDSS direct mode requires opendssdirect.py to be installed.") from exc

    master_file = Path(config["master_file"])
    load_name = config.get("load_name", "building_load")
    target_bus = config.get("target_bus", "loadbus")
    rows = []

    for row in load_rows:
        dss.Basic.ClearAll()
        dss.Text.Command(f'Compile "{master_file}"')
        kw = float(row["building_kw"])
        kvar = float(row.get("building_kvar", 0.0))
        dss.Text.Command(f"Edit Load.{load_name} kw={kw} kvar={kvar}")
        dss.Solution.Solve()

        voltages = dss.Circuit.AllBusMagPu()
        min_voltage = min(voltages) if voltages else math.nan
        line_loading = _max_line_loading_pct(dss)
        rows.append(
            {
                "timestamp": row["timestamp"],
                "bus": target_bus,
                "building_kw": round(kw, 6),
                "building_kvar": round(kvar, 6),
                "feeder_kw": round(max(dss.Circuit.TotalPower()[0] * -1.0, kw), 6),
                "min_voltage_pu": round(min_voltage, 6),
                "max_line_loading_pct": round(line_loading, 6) if not math.isnan(line_loading) else "",
                "converged": bool(dss.Solution.Converged()),
            }
        )
    return rows


def _max_line_loading_pct(dss) -> float:
    values = []
    for name in dss.Lines.AllNames() or []:
        dss.Lines.Name(name)
        normal_amps = dss.Lines.NormAmps()
        currents = dss.CktElement.CurrentsMagAng()[0::2]
        if normal_amps and currents:
            values.append(max(currents) / normal_amps * 100.0)
    return max(values) if values else math.nan
