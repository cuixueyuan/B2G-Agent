from __future__ import annotations

from pathlib import Path
from typing import Any

from utils import ensure_output_dirs, load_case_config, read_csv, write_csv


def extract_building_loads(config: dict[str, Any]) -> Path:
    paths = ensure_output_dirs(config)
    rows = []
    load_rows = read_csv(paths["building_loads_csv"])
    by_building: dict[str, list[dict[str, str]]] = {}
    for row in load_rows:
        by_building.setdefault(row["building_id"], []).append(row)
    for building_id, building_rows in sorted(by_building.items()):
        peak_kw = max(float(row["net_load_kw"]) for row in building_rows)
        total_kwh = sum(float(row["net_load_kw"]) for row in building_rows)
        rows.append(
            {
                "building_id": building_id,
                "load_csv": paths["building_loads_csv"].as_posix(),
                "hours": len(building_rows),
                "peak_kw": round(peak_kw, 6),
                "total_kwh": round(total_kwh, 6),
            }
        )
    return write_csv(paths["building_loads"] / "extracted_loads_manifest.csv", rows)


def main() -> int:
    config = load_case_config()
    path = extract_building_loads(config)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
