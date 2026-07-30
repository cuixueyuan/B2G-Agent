from __future__ import annotations

from pathlib import Path

from x2g_agent.io import write_rows_csv
from x2g_agent.tools.opendss import run_hourly_power_flow


class OpenDSSAgent:
    def __init__(self, config: dict, output_root: Path):
        self.config = config
        self.output_root = output_root

    def run(self, mapped_load_rows: list[dict]) -> tuple[list[dict], Path]:
        if mapped_load_rows:
            self.config.setdefault("target_bus", mapped_load_rows[0]["target_bus"])
        rows = run_hourly_power_flow(mapped_load_rows, self.config)
        path = write_rows_csv(self.output_root / "opendss_hourly_results.csv", rows)
        return rows, path
