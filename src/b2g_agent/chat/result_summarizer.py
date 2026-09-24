from __future__ import annotations

from pathlib import Path
from typing import Any


class ResultSummarizer:
    def summarize_run(self, state: dict[str, Any]) -> str:
        artifacts = state.get("artifacts", {})
        risk = state.get("risk_summary", {})
        lines = [
            "Building-to-Grid run completed.",
            f"Building load CSV: {artifacts.get('building_load_csv', 'not available')}",
            f"Power-flow results: {artifacts.get('power_flow_result_csv', 'not available')}",
            f"Grid risk summary: {artifacts.get('risk_summary_csv', 'not available')}",
            f"Markdown report: {artifacts.get('markdown_report', 'not available')}",
            f"Voltage violation hours: {risk.get('voltage_violations', 'not available')}",
            f"Minimum voltage p.u.: {risk.get('minimum_voltage_pu', 'not available')}",
            f"Peak feeder kW: {risk.get('feeder_peak_kw', 'not available')}",
        ]
        return "\n".join(lines)

    def summarize_voltage(self, state: dict[str, Any] | None) -> str:
        if not state:
            return "No run has completed yet. Try: run mock Building-to-Grid"
        risk = state.get("risk_summary", {})
        return (
            f"Voltage violation hours: {risk.get('voltage_violations', 'not available')}\n"
            f"Minimum voltage p.u.: {risk.get('minimum_voltage_pu', 'not available')}"
        )

    def output_paths(self, state: dict[str, Any] | None) -> str:
        if not state:
            return "No output paths yet. Run a case first."
        artifacts = state.get("artifacts", {})
        if not artifacts:
            return "No artifacts were recorded for the last run."
        return "\n".join(f"{name}: {Path(path)}" for name, path in sorted(artifacts.items()))
