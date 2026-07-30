from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def standardize_energyplus_rows(rows: list[dict[str, Any]], power_factor: float = 0.95) -> list[dict[str, Any]]:
    standardized = []
    for index, row in enumerate(rows):
        timestamp = row.get("timestamp") or row.get("Date/Time") or str(index)
        kw = _first_float(row, ["electricity_kw", "Electricity:Facility", "kw"])
        kvar = _first_float(row, ["electricity_kvar", "kvar"], default=None)
        if kvar is None:
            kvar = kw * _kvar_ratio(power_factor)
        standardized.append(
            {
                "timestamp": str(timestamp),
                "electricity_kw": round(kw, 6),
                "electricity_kvar": round(kvar, 6),
            }
        )
    return standardized


def _first_float(row: dict[str, Any], fragments: list[str], default: float | None = 0.0) -> float:
    for key, value in row.items():
        if any(fragment.lower() in key.lower() for fragment in fragments):
            return float(value)
    if default is None:
        raise ValueError(f"Could not find a numeric column matching {fragments}.")
    return default


def _kvar_ratio(power_factor: float) -> float:
    import math

    clipped = max(min(power_factor, 1.0), 0.01)
    return math.tan(math.acos(clipped))
