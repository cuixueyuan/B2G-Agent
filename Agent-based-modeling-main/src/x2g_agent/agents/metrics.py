from __future__ import annotations

from pathlib import Path

from x2g_agent.io import write_rows_csv


class MetricsAgent:
    def __init__(self, config: dict, output_root: Path):
        self.config = config
        self.output_root = output_root

    def run(self, power_flow_rows: list[dict]) -> tuple[dict, Path]:
        voltage_min = float(self.config.get("voltage_min_pu", 0.95))
        voltage_max = float(self.config.get("voltage_max_pu", 1.05))
        overload_limit = float(self.config.get("line_overload_pct", 100.0))

        voltage_violations = 0
        convergence_failures = 0
        line_overloads = 0
        feeder_peak_kw = 0.0
        min_voltage_seen = None

        for row in power_flow_rows:
            min_v = float(row["min_voltage_pu"])
            feeder_peak_kw = max(feeder_peak_kw, float(row["feeder_kw"]))
            min_voltage_seen = min(min_voltage_seen, min_v) if min_voltage_seen is not None else min_v
            if min_v < voltage_min or min_v > voltage_max:
                voltage_violations += 1
            if str(row.get("converged", True)).lower() not in {"true", "1", "yes"}:
                convergence_failures += 1
            loading = row.get("max_line_loading_pct", "")
            if loading != "" and float(loading) > overload_limit:
                line_overloads += 1

        metrics = {
            "hours": len(power_flow_rows),
            "voltage_violations": voltage_violations,
            "feeder_peak_kw": round(feeder_peak_kw, 6),
            "convergence_failures": convergence_failures,
            "line_overloads": line_overloads,
            "minimum_voltage_pu": round(min_voltage_seen, 6) if min_voltage_seen is not None else "",
        }
        path = write_rows_csv(self.output_root / "metrics_summary.csv", [metrics])
        return metrics, path
