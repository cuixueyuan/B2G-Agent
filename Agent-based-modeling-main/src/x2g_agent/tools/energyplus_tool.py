from __future__ import annotations

import csv
import math
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only used in minimal runtimes
    load_dotenv = None


def run_energyplus_or_mock(config: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    mode = config.get("mode", "mock")
    if mode == "mock":
        return generate_mock_building_load(config)
    if mode in {"real", "direct", "energyplus"}:
        return run_energyplus(config, output_dir)
    raise ValueError(f"Unsupported EnergyPlus mode: {mode}")


def generate_mock_building_load(config: dict[str, Any]) -> list[dict[str, Any]]:
    mock = config.get("mock", {})
    start = datetime.fromisoformat(str(mock.get("start", "2024-01-01T00:00:00")))
    hours = int(mock.get("hours", 24))
    base_kw = float(mock.get("base_kw", 80.0))
    amplitude_kw = float(mock.get("daily_amplitude_kw", 35.0))
    load_scale = float(config.get("load_scale", mock.get("load_scale", 1.0)))
    power_factor = float(mock.get("power_factor", config.get("power_factor", 0.95)))
    kvar_ratio = math.tan(math.acos(max(min(power_factor, 1.0), 0.01)))

    rows = []
    for hour in range(hours):
        timestamp = start + timedelta(hours=hour)
        occupancy_shape = max(0.0, math.sin((hour % 24 - 6) / 24.0 * 2.0 * math.pi))
        kw = (base_kw + amplitude_kw * occupancy_shape) * load_scale
        rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "electricity_kw": round(kw, 6),
                "electricity_kvar": round(kw * kvar_ratio, 6),
            }
        )
    return rows


def run_energyplus(config: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    _load_dotenv_files()
    executable = _required_path(config, "executable", label="EnergyPlus executable")
    idf_path = _required_path(config, "idf_path", fallback_key="idf", label="EnergyPlus IDF")
    epw_path = _required_path(config, "epw_path", fallback_key="epw", label="EnergyPlus EPW")
    output_dir.mkdir(parents=True, exist_ok=True)

    _run_energyplus_subprocess(executable, epw_path, output_dir, idf_path)
    output_path = _find_energyplus_output(output_dir)
    if output_path is None:
        raise FileNotFoundError(
            f"EnergyPlus completed but no supported output was found in {output_dir}. "
            "Expected one of: eplusout.csv, eplusout.sql, eplusout.mtr."
        )

    rows = parse_energyplus_load_output(output_path, int(config.get("timestep_per_hour", 1)))
    if rows:
        return rows

    rerun_idf = _create_idf_with_hourly_electricity_meter(idf_path, output_dir)
    _run_energyplus_subprocess(executable, epw_path, output_dir, rerun_idf)
    output_path = _find_energyplus_output(output_dir)
    if output_path is None:
        raise FileNotFoundError(
            f"EnergyPlus rerun completed but no supported output was found in {output_dir}. "
            "Expected one of: eplusout.csv, eplusout.sql, eplusout.mtr."
        )
    rows = parse_energyplus_load_output(output_path, int(config.get("timestep_per_hour", 1)))
    if not rows:
        raise RuntimeError(
            f"EnergyPlus {output_path.name} does not contain hourly Electricity:Facility data "
            "even after appending Output:Meter,Electricity:Facility,hourly; to a temporary IDF."
        )
    return rows


def parse_energyplus_load_output(path: Path, timestep_per_hour: int = 1) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_eplusout_electricity_facility(path, timestep_per_hour)
    if suffix == ".sql":
        return parse_eplusout_sql(path, timestep_per_hour)
    if suffix == ".mtr":
        return parse_eplusout_mtr(path)
    raise ValueError(f"Unsupported EnergyPlus output type: {path}")


def parse_eplusout_electricity_facility(csv_path: Path, timestep_per_hour: int = 1) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"EnergyPlus output CSV is missing: {csv_path}")
    with csv_path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise RuntimeError(f"EnergyPlus output CSV has no header: {csv_path}")
        meter_column = _find_hourly_electricity_facility_column(reader.fieldnames)
        if meter_column is None:
            return []
        rows = []
        for index, row in enumerate(reader):
            value = row.get(meter_column, "")
            if value == "":
                continue
            rows.append(
                {
                    "timestamp": _clean_timestamp(row.get("Date/Time") or row.get("timestamp") or str(index)),
                    "electricity_kw": round(_meter_value_to_kw(float(value), meter_column, timestep_per_hour), 6),
                }
            )
    return rows


def parse_eplusout_sql(sql_path: Path, timestep_per_hour: int = 1) -> list[dict[str, Any]]:
    if not sql_path.exists():
        raise FileNotFoundError(f"EnergyPlus SQL output is missing: {sql_path}")
    query = """
        SELECT Time.Month, Time.Day, Time.Hour, Time.Minute,
               ReportData.Value, ReportDataDictionary.Units
        FROM ReportData
        JOIN ReportDataDictionary
          ON ReportData.ReportDataDictionaryIndex = ReportDataDictionary.ReportDataDictionaryIndex
        JOIN Time
          ON ReportData.TimeIndex = Time.TimeIndex
        WHERE ReportDataDictionary.Name = 'Electricity:Facility'
          AND lower(ReportDataDictionary.ReportingFrequency) = 'hourly'
        ORDER BY ReportData.TimeIndex
    """
    try:
        with sqlite3.connect(sql_path) as connection:
            rows = connection.execute(query).fetchall()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Could not read EnergyPlus SQL output {sql_path}: {exc}") from exc
    return [
        {
            "timestamp": _format_energyplus_timestamp(month, day, hour, minute),
            "electricity_kw": round(_meter_value_to_kw(float(value), f"[{units}]", timestep_per_hour), 6),
        }
        for month, day, hour, minute, value, units in rows
    ]


def parse_eplusout_mtr(mtr_path: Path) -> list[dict[str, Any]]:
    if not mtr_path.exists():
        raise FileNotFoundError(f"EnergyPlus MTR output is missing: {mtr_path}")

    text_lines = mtr_path.read_text(encoding="utf-8", errors="replace").splitlines()
    time_code: str | None = None
    meter_code: str | None = None
    meter_units = "J"
    available_meters: list[str] = []
    in_dictionary = True
    data_start = 0

    for index, raw_line in enumerate(text_lines):
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("end of data dictionary"):
            in_dictionary = False
            data_start = index + 1
            break
        if not in_dictionary:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        descriptor = ",".join(parts[2:]).strip()
        descriptor_lower = descriptor.lower()
        if "day of simulation" in descriptor_lower and "month" in descriptor_lower and "hour" in descriptor_lower:
            time_code = parts[0]
            continue
        meter_name = _meter_name_from_mtr_descriptor(descriptor)
        if meter_name:
            available_meters.append(meter_name)
        if meter_name == "Electricity:Facility":
            meter_code = parts[0]
            meter_units = _units_from_descriptor(descriptor) or "J"

    if meter_code is None:
        names = ", ".join(sorted(set(available_meters))) or "none"
        raise RuntimeError(
            "EnergyPlus eplusout.mtr does not contain the exact meter name Electricity:Facility. "
            f"Available meter names: {names}"
        )

    current_timestamp = ""
    rows = []
    for raw_line in text_lines[data_start:]:
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        code = parts[0]
        if code == time_code:
            current_timestamp = _timestamp_from_mtr_time_row(parts)
        elif code == meter_code and len(parts) > 1:
            rows.append(
                {
                    "timestamp": current_timestamp or str(len(rows)),
                    "electricity_kw": round(_mtr_energy_to_kw(float(parts[1]), meter_units), 6),
                }
            )
    return rows


def _required_path(
    config: dict[str, Any],
    key: str,
    *,
    fallback_key: str | None = None,
    label: str,
) -> str:
    value = config.get(key) or (config.get(fallback_key) if fallback_key else None)
    if not value:
        raise ValueError(f"{label} is required. Set energyplus.{key} in config or provide the matching .env variable.")
    expanded = _expand_env_placeholders(str(value))
    if "${" in expanded:
        raise ValueError(f"{label} contains an unresolved environment variable placeholder: {value}")
    path = Path(expanded)
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    return str(path)


def _run_energyplus_subprocess(executable: str, epw_path: str, output_dir: Path, idf_path: str | Path) -> None:
    command = [executable, "-w", epw_path, "-d", str(output_dir), str(idf_path)]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"EnergyPlus executable could not be launched: {executable}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"EnergyPlus failed with exit code {exc.returncode}. Command: {' '.join(command)}"
        ) from exc


def _find_hourly_electricity_facility_column(fieldnames: list[str]) -> str | None:
    for field in fieldnames:
        lower = field.lower()
        if "electricity:facility" in lower and "hourly" in lower:
            return field
    return None


def _meter_value_to_kw(value: float, column_name: str, timestep_per_hour: int) -> float:
    lower = column_name.lower()
    if "[j]" in lower or "(j)" in lower:
        return value * max(timestep_per_hour, 1) / 3_600_000.0
    if "[kj]" in lower or "(kj)" in lower:
        return value * max(timestep_per_hour, 1) / 3_600.0
    if "[wh]" in lower or "(wh)" in lower:
        return value * max(timestep_per_hour, 1) / 1_000.0
    if "[kwh]" in lower or "(kwh)" in lower:
        return value * max(timestep_per_hour, 1)
    if "[w]" in lower or "(w)" in lower:
        return value / 1_000.0
    return value


def _mtr_energy_to_kw(value: float, units: str) -> float:
    lower = units.lower()
    if lower == "j":
        return value / 3_600_000.0
    if lower == "kj":
        return value / 3_600.0
    if lower == "wh":
        return value / 1_000.0
    if lower == "kwh":
        return value
    if lower == "w":
        return value / 1_000.0
    if lower == "kw":
        return value
    return value


def _find_energyplus_output(output_dir: Path) -> Path | None:
    for filename in ["eplusout.csv", "eplusout.sql", "eplusout.mtr"]:
        candidate = output_dir / filename
        if candidate.exists():
            return candidate
    return None


def _meter_name_from_mtr_descriptor(descriptor: str) -> str:
    without_comment = descriptor.split("!", 1)[0].strip()
    without_units = re.split(r"\s*[\[\(]", without_comment, maxsplit=1)[0].strip()
    return without_units


def _units_from_descriptor(descriptor: str) -> str | None:
    match = re.search(r"\[([^\]]+)\]", descriptor)
    if match:
        return match.group(1).strip()
    match = re.search(r"\(([A-Za-z]+)\)", descriptor)
    if match:
        value = match.group(1).strip()
        if value.lower() != "hourly":
            return value
    return None


def _timestamp_from_mtr_time_row(parts: list[str]) -> str:
    if len(parts) >= 8:
        try:
            return _format_energyplus_timestamp(
                int(float(parts[2])),
                int(float(parts[3])),
                int(float(parts[5])),
                int(float(parts[7])),
            )
        except ValueError:
            return ",".join(parts[1:])
    return ",".join(parts[1:])


def _format_energyplus_timestamp(month: Any, day: Any, hour: Any, minute: Any) -> str:
    hour_int = int(float(hour))
    minute_int = int(float(minute))
    if minute_int >= 60:
        minute_int = 0
    return f"{int(float(month)):02d}/{int(float(day)):02d} {hour_int:02d}:{minute_int:02d}:00"


def _create_idf_with_hourly_electricity_meter(idf_path: str, output_dir: Path) -> Path:
    source = Path(idf_path)
    if not source.exists():
        raise FileNotFoundError(f"Cannot create temporary IDF because source IDF is missing: {source}")
    target = output_dir / f"{source.stem}_x2g_hourly_meter.idf"
    shutil.copyfile(source, target)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(
            "\n\n"
            "! Added by X2G-Agent real-mode EnergyPlus run.\n"
            "Output:Meter,Electricity:Facility,hourly;\n"
            "OutputControl:Table:Style,Comma;\n"
        )
    return target


def _load_dotenv_files() -> None:
    if load_dotenv is None:
        return
    load_dotenv()


def _expand_env_placeholders(value: str) -> str:
    expanded = os.path.expandvars(value)
    return re.sub(r"\$\{([^}]+)\}", lambda match: os.environ.get(match.group(1), match.group(0)), expanded)


def _clean_timestamp(value: str) -> str:
    return " ".join(str(value).strip().split())


def _find_energyplus_csv(output_dir: Path) -> Path | None:
    candidates = sorted(output_dir.glob("*Meter*.csv")) + sorted(output_dir.glob("*.csv"))
    return candidates[0] if candidates else None
