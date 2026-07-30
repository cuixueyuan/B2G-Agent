from __future__ import annotations

from typing import Any


def summarize_power_flow_risk(rows: list[dict[str, Any]], thresholds: dict[str, Any]) -> dict[str, Any]:
    voltage_min = float(thresholds.get("voltage_min_pu", 0.95))
    voltage_max = float(thresholds.get("voltage_max_pu", 1.05))
    line_limit = float(thresholds.get("line_overload_pct", thresholds.get("line_loading_limit_pct", 100.0)))

    voltage_violations = 0
    convergence_failures = 0
    line_overloads = 0
    feeder_peak_kw = 0.0
    minimum_voltage = None

    for row in rows:
        min_voltage = float(row["min_voltage_pu"])
        feeder_peak_kw = max(feeder_peak_kw, float(row["feeder_kw"]))
        minimum_voltage = min(minimum_voltage, min_voltage) if minimum_voltage is not None else min_voltage
        if min_voltage < voltage_min or min_voltage > voltage_max:
            voltage_violations += 1
        if str(row.get("converged", True)).lower() not in {"true", "1", "yes"}:
            convergence_failures += 1
        loading = row.get("max_line_loading_pct", "")
        if loading != "" and float(loading) > line_limit:
            line_overloads += 1

    return {
        "hours": len(rows),
        "voltage_violations": voltage_violations,
        "feeder_peak_kw": round(feeder_peak_kw, 6),
        "convergence_failures": convergence_failures,
        "line_overloads": line_overloads,
        "minimum_voltage_pu": round(minimum_voltage, 6) if minimum_voltage is not None else "",
    }
