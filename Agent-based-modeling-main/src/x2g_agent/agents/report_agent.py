from __future__ import annotations

from pathlib import Path
from typing import Any

from x2g_agent.agents.base import Agent, WorkflowState


class ReportAgent(Agent):
    def run(self, state: WorkflowState) -> WorkflowState:
        output_root = Path(state["output_root"])
        figures_dir = output_root / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        load_figure = figures_dir / "building_load.svg"
        voltage_figure = figures_dir / "minimum_voltage.svg"
        _write_svg_line(load_figure, state["power_flow_rows"], "building_kw", "Building Load (kW)")
        _write_svg_line(voltage_figure, state["power_flow_rows"], "min_voltage_pu", "Minimum Voltage (p.u.)")

        report_path = output_root / "report.md"
        title = state["config"].get("report", {}).get("title", "Building-to-Grid")
        risk = state["risk_summary"]
        artifacts = state["artifacts"]
        report_path.write_text(
            "\n".join(
                [
                    f"# {title}",
                    "",
                    "## Risk Summary",
                    "",
                    f"- Hours simulated: {risk['hours']}",
                    f"- Voltage violations: {risk['voltage_violations']}",
                    f"- Feeder peak load: {risk['feeder_peak_kw']} kW",
                    f"- Convergence failures: {risk['convergence_failures']}",
                    f"- Line overload hours: {risk['line_overloads']}",
                    f"- Minimum voltage: {risk['minimum_voltage_pu']} p.u.",
                    "",
                    "## Figures",
                    "",
                    f"![Building load](figures/{load_figure.name})",
                    "",
                    f"![Minimum voltage](figures/{voltage_figure.name})",
                    "",
                    "## Outputs",
                    "",
                    *[f"- {name}: `{Path(path).name}`" for name, path in sorted(artifacts.items())],
                    "",
                ]
            ),
            encoding="utf-8",
        )
        state["artifacts"]["markdown_report"] = report_path
        return state


def _write_svg_line(path: Path, rows: list[dict[str, Any]], key: str, title: str) -> None:
    width = 760
    height = 280
    pad = 44
    values = [float(row[key]) for row in rows] if rows else [0.0]
    low = min(values)
    high = max(values)
    span = high - low if high != low else 1.0
    points = []
    for index, value in enumerate(values):
        x = pad + (width - 2 * pad) * (index / max(len(values) - 1, 1))
        y = height - pad - (height - 2 * pad) * ((value - low) / span)
        points.append(f"{x:.2f},{y:.2f}")
    path.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{pad}" y="28" font-family="Arial" font-size="18" fill="#1f2937">{title}</text>
  <line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#94a3b8"/>
  <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#94a3b8"/>
  <polyline points="{' '.join(points)}" fill="none" stroke="#2563eb" stroke-width="3"/>
  <text x="{pad}" y="{height-12}" font-family="Arial" font-size="12" fill="#475569">min {low:.3f} / max {high:.3f}</text>
</svg>
""",
        encoding="utf-8",
    )
