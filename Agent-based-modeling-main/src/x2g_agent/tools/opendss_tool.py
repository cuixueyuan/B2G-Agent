from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from x2g_agent.tools.load_parser import read_csv


@dataclass(frozen=True)
class OpenDSSRunResult:
    power_flow_rows: list[dict[str, Any]]
    bus_voltage_rows: list[dict[str, Any]]
    feeder_power_rows: list[dict[str, Any]]
    convergence_rows: list[dict[str, Any]]


class OpenDSSTool:
    """OpenDSSDirect.py wrapper for hourly Building-to-Grid snapshots."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def run_hourly(self, mapped_rows: list[dict[str, Any]]) -> OpenDSSRunResult:
        mode = self.config.get("mode", self.config.get("backend", "mock"))
        if mode == "mock":
            return run_mock_power_flow_detailed(mapped_rows, self.config)
        if mode in {"direct", "opendssdirect"}:
            return run_opendssdirect_detailed(mapped_rows, self.config)
        raise ValueError(f"Unsupported OpenDSS mode: {mode}")

    def run_hourly_from_csv(self, mapped_load_csv: str | Path) -> OpenDSSRunResult:
        return self.run_hourly(read_csv(Path(mapped_load_csv)))


def write_opendss_loadshape_files(
    mapped_rows: list[dict[str, Any]],
    opendss_config: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    loadshape_path = output_dir / "building_loadshape.csv"
    injection_path = output_dir / "building_load_injection.dss"
    load_name = opendss_config.get("load_name", "building_load")
    target_bus = opendss_config.get("target_bus", "loadbus")
    base_kv = float(opendss_config.get("base_kv", opendss_config.get("kv", 12.47)))

    peak_kw = max((float(row["building_kw"]) for row in mapped_rows), default=1.0)
    with loadshape_path.open("w", encoding="utf-8") as fh:
        fh.write("hour,mult,kw,kvar\n")
        for index, row in enumerate(mapped_rows):
            kw = float(row["building_kw"])
            kvar = float(row.get("building_kvar", 0.0))
            fh.write(f"{index},{kw / peak_kw if peak_kw else 0.0:.8f},{kw:.6f},{kvar:.6f}\n")

    injection_path.write_text(
        "\n".join(
            [
                f"New Loadshape.{load_name}_shape npts={len(mapped_rows)} interval=1 mult=(file={loadshape_path.name}, col=2, header=yes)",
                f"Edit Load.{load_name} bus1={target_bus} kv={base_kv} kw={peak_kw:.6f} yearly={load_name}_shape",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {"loadshape_csv": loadshape_path, "load_injection_dss": injection_path}


def run_opendss_or_mock(mapped_rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    return OpenDSSTool(config).run_hourly(mapped_rows).power_flow_rows


def run_opendss_detailed(mapped_rows: list[dict[str, Any]], config: dict[str, Any]) -> OpenDSSRunResult:
    return OpenDSSTool(config).run_hourly(mapped_rows)


def run_mock_power_flow(mapped_rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    return run_mock_power_flow_detailed(mapped_rows, config).power_flow_rows


def run_mock_power_flow_detailed(mapped_rows: list[dict[str, Any]], config: dict[str, Any]) -> OpenDSSRunResult:
    mock = config.get("mock", {})
    feeder_base_kw = float(mock.get("feeder_base_kw", 120.0))
    line_rating_kw = float(mock.get("line_rating_kw", 350.0))
    source_voltage = float(mock.get("source_voltage_pu", 1.0))
    drop_per_100kw = float(mock.get("voltage_drop_per_100kw", 0.012))
    target_bus = config.get("target_bus", "loadbus")

    power_flow_rows = []
    bus_voltage_rows = []
    feeder_power_rows = []
    convergence_rows = []
    for hour, row in enumerate(mapped_rows):
        building_kw = float(row["building_kw"])
        building_kvar = float(row.get("building_kvar", 0.0))
        feeder_kw = feeder_base_kw + building_kw
        feeder_kvar = building_kvar
        min_voltage = source_voltage - (feeder_kw / 100.0) * drop_per_100kw
        line_loading = feeder_kw / line_rating_kw * 100.0 if line_rating_kw else math.nan
        timestamp = row["timestamp"]
        power_flow_rows.append(
            {
                "hour": hour,
                "timestamp": timestamp,
                "bus": target_bus,
                "building_kw": round(building_kw, 6),
                "building_kvar": round(building_kvar, 6),
                "feeder_kw": round(feeder_kw, 6),
                "feeder_kvar": round(feeder_kvar, 6),
                "min_voltage_pu": round(min_voltage, 6),
                "max_line_loading_pct": round(line_loading, 6),
                "converged": True,
            }
        )
        for bus, voltage in _mock_bus_voltages(source_voltage, min_voltage):
            bus_voltage_rows.append(
                {
                    "hour": hour,
                    "timestamp": timestamp,
                    "bus": bus,
                    "voltage_pu": round(voltage, 6),
                }
            )
        feeder_power_rows.append(
            {
                "hour": hour,
                "timestamp": timestamp,
                "feeder_kw": round(feeder_kw, 6),
                "feeder_kvar": round(feeder_kvar, 6),
            }
        )
        convergence_rows.append(
            {
                "hour": hour,
                "timestamp": timestamp,
                "converged": True,
            }
        )
    return OpenDSSRunResult(power_flow_rows, bus_voltage_rows, feeder_power_rows, convergence_rows)


def run_opendssdirect(mapped_rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    return run_opendssdirect_detailed(mapped_rows, config).power_flow_rows


def run_opendssdirect_detailed(mapped_rows: list[dict[str, Any]], config: dict[str, Any]) -> OpenDSSRunResult:
    try:
        import opendssdirect as dss
    except ImportError as exc:
        raise RuntimeError("OpenDSSDirect.py is required for non-mock OpenDSS runs.") from exc

    master_file = Path(config["master_file"])
    load_name = config.get("load_name", "building_load")
    target_bus = config.get("target_bus", "loadbus")
    base_kv = float(config.get("base_kv", config.get("kv", 12.47)))

    _compile_feeder(dss, master_file)
    _ensure_target_load(dss, load_name, target_bus, base_kv)

    power_flow_rows = []
    bus_voltage_rows = []
    feeder_power_rows = []
    convergence_rows = []
    for hour, row in enumerate(mapped_rows):
        timestamp = row["timestamp"]
        building_kw = float(row["building_kw"])
        building_kvar = float(row.get("building_kvar", 0.0))
        dss.Text.Command(f"Edit Load.{load_name} bus1={target_bus} kv={base_kv} kw={building_kw} kvar={building_kvar}")
        dss.Text.Command("Set Mode=Snap")
        dss.Solution.Solve()
        converged = bool(dss.Solution.Converged())
        bus_voltages = _bus_voltage_rows(dss, hour, timestamp)
        voltage_values = [float(item["voltage_pu"]) for item in bus_voltages]
        total_power = dss.Circuit.TotalPower()
        feeder_kw = -float(total_power[0]) if total_power else building_kw
        feeder_kvar = -float(total_power[1]) if len(total_power) > 1 else building_kvar
        line_loading = _max_line_loading_pct(dss)
        power_flow_rows.append(
            {
                "hour": hour,
                "timestamp": timestamp,
                "bus": target_bus,
                "building_kw": round(building_kw, 6),
                "building_kvar": round(building_kvar, 6),
                "feeder_kw": round(max(feeder_kw, building_kw), 6),
                "feeder_kvar": round(feeder_kvar, 6),
                "min_voltage_pu": round(min(voltage_values), 6) if voltage_values else "",
                "max_line_loading_pct": round(line_loading, 6) if not math.isnan(line_loading) else "",
                "converged": converged,
            }
        )
        bus_voltage_rows.extend(bus_voltages)
        feeder_power_rows.append(
            {
                "hour": hour,
                "timestamp": timestamp,
                "feeder_kw": round(max(feeder_kw, building_kw), 6),
                "feeder_kvar": round(feeder_kvar, 6),
            }
        )
        convergence_rows.append(
            {
                "hour": hour,
                "timestamp": timestamp,
                "converged": converged,
            }
        )
    return OpenDSSRunResult(power_flow_rows, bus_voltage_rows, feeder_power_rows, convergence_rows)


def _compile_feeder(dss: Any, master_file: Path) -> None:
    dss.Basic.ClearAll()
    dss.Text.Command(f'Compile "{master_file}"')


def _ensure_target_load(dss: Any, load_name: str, target_bus: str, base_kv: float) -> None:
    loads = {name.lower(): name for name in dss.Loads.AllNames() or []}
    if load_name.lower() in loads:
        dss.Text.Command(f"Edit Load.{load_name} bus1={target_bus} kv={base_kv}")
        return
    dss.Text.Command(f"New Load.{load_name} phases=3 bus1={target_bus} conn=wye model=1 kv={base_kv} kw=1 kvar=0")


def _bus_voltage_rows(dss: Any, hour: int, timestamp: str) -> list[dict[str, Any]]:
    rows = []
    for bus in dss.Circuit.AllBusNames() or []:
        dss.Circuit.SetActiveBus(bus)
        magnitudes = dss.Bus.puVmagAngle()[0::2]
        if not magnitudes:
            continue
        rows.append(
            {
                "hour": hour,
                "timestamp": timestamp,
                "bus": bus,
                "voltage_pu": round(min(float(value) for value in magnitudes), 6),
            }
        )
    return rows


def _mock_bus_voltages(source_voltage: float, min_voltage: float) -> list[tuple[str, float]]:
    step = (source_voltage - min_voltage) / 3.0
    return [
        ("bus_1", source_voltage),
        ("bus_2", source_voltage - step),
        ("bus_3", source_voltage - 2.0 * step),
        ("bus_4", min_voltage),
    ]


def _max_line_loading_pct(dss: Any) -> float:
    values = []
    for name in dss.Lines.AllNames() or []:
        dss.Lines.Name(name)
        normal_amps = dss.Lines.NormAmps()
        currents = dss.CktElement.CurrentsMagAng()[0::2]
        if normal_amps and currents:
            values.append(max(currents) / normal_amps * 100.0)
    return max(values) if values else math.nan
