from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta
from pathlib import Path

from x2g_agent.io import write_rows_csv
from x2g_agent.tools.energyplus import run_energyplus


class EnergyPlusAgent:
    def __init__(self, config: dict, output_root: Path):
        self.config = config
        self.output_root = output_root

    def run(self) -> tuple[list[dict], Path]:
        mode = self.config.get("mode", "mock")
        if mode == "mock":
            rows = self._mock_rows()
        elif mode == "direct":
            run = run_energyplus(self.config, self.output_root / self.config.get("output_subdir", "energyplus"))
            if run.meter_csv is None:
                raise RuntimeError("EnergyPlus completed but no CSV output was found.")
            rows = self._read_energyplus_meter(run.meter_csv)
        else:
            raise ValueError(f"Unsupported EnergyPlus mode: {mode}")

        path = write_rows_csv(self.output_root / "building_load.csv", rows)
        return rows, path

    def _mock_rows(self) -> list[dict]:
        mock = self.config.get("mock", {})
        start = datetime.fromisoformat(mock.get("start", "2024-01-01T00:00:00"))
        hours = int(mock.get("hours", 24))
        base_kw = float(mock.get("base_kw", 80.0))
        amplitude_kw = float(mock.get("daily_amplitude_kw", 35.0))
        noise_kw = float(mock.get("noise_kw", 0.0))
        pf = float(mock.get("power_factor", 0.96))
        kvar_ratio = math.tan(math.acos(max(min(pf, 1.0), 0.01)))

        rows = []
        for hour in range(hours):
            timestamp = start + timedelta(hours=hour)
            daily_shape = max(0.0, math.sin((hour % 24 - 6) / 24.0 * 2.0 * math.pi))
            deterministic_noise = noise_kw * math.sin(hour * 1.618)
            kw = max(0.0, base_kw + amplitude_kw * daily_shape + deterministic_noise)
            rows.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "electricity_kw": round(kw, 6),
                    "electricity_kvar": round(kw * kvar_ratio, 6),
                }
            )
        return rows

    def _read_energyplus_meter(self, csv_path: Path) -> list[dict]:
        with csv_path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            rows = []
            for idx, row in enumerate(reader):
                kw_key = _find_key(row, ["Electricity:Facility", "electricity", "kw"])
                if kw_key is None:
                    raise ValueError(f"Could not find an electricity column in {csv_path}.")
                rows.append(
                    {
                        "timestamp": row.get("Date/Time") or row.get("timestamp") or str(idx),
                        "electricity_kw": round(float(row[kw_key]), 6),
                        "electricity_kvar": 0.0,
                    }
                )
        return rows


def _find_key(row: dict, fragments: list[str]) -> str | None:
    lowered = {key.lower(): key for key in row}
    for lower, original in lowered.items():
        if any(fragment.lower() in lower for fragment in fragments):
            return original
    return None
