from __future__ import annotations

from pathlib import Path

from x2g_agent.io import write_rows_csv


class LoadMappingAgent:
    def __init__(self, config: dict, output_root: Path):
        self.config = config
        self.output_root = output_root

    def run(self, building_rows: list[dict]) -> tuple[list[dict], Path]:
        target_bus = self.config["target_bus"]
        load_name = self.config.get("target_load_name", "building_load")
        phases = int(self.config.get("phases", 3))
        kv = float(self.config.get("kv", 12.47))

        rows = []
        for row in building_rows:
            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "target_bus": target_bus,
                    "load_name": load_name,
                    "phases": phases,
                    "kv": kv,
                    "building_kw": round(float(row["electricity_kw"]), 6),
                    "building_kvar": round(float(row.get("electricity_kvar", 0.0)), 6),
                }
            )
        path = write_rows_csv(self.output_root / "mapped_building_load.csv", rows)
        return rows, path
