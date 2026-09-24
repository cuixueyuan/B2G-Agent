from __future__ import annotations

from pathlib import Path


class ReportAgent:
    def __init__(self, config: dict, output_root: Path):
        self.config = config
        self.output_root = output_root

    def run(self, artifacts: dict[str, Path], metrics: dict, power_flow_rows: list[dict]) -> Path:
        figures_dir = self.output_root / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        load_figure = figures_dir / "building_load.svg"
        voltage_figure = figures_dir / "minimum_voltage.svg"
        _write_svg_line(load_figure, power_flow_rows, "building_kw", "Building Load (kW)")
        _write_svg_line(voltage_figure, power_flow_rows, "min_voltage_pu", "Minimum Voltage (p.u.)")

        report_path = self.output_root / "report.md"
        title = self.config.get("title", "Building-to-Grid Report")
        report_path.write_text(
            "\n".join(
                [
                    f"# {title}",
                    "",
                    "## Summary Metrics",
                    "",
                    f"- Hours simulated: {metrics['hours']}",
                    f"- Voltage violations: {metrics['voltage_violations']}",
                    f"- Feeder peak load: {metrics['feeder_peak_kw']} kW",
                    f"- Convergence failures: {metrics['convergence_failures']}",
                    f"- Line overload hours: {metrics['line_overloads']}",
                    f"- Minimum voltage: {metrics['minimum_voltage_pu']} p.u.",
                    "",
                    "## Figures",
                    "",
                    f"![Building load](figures/{load_figure.name})",
                    "",
                    f"![Minimum voltage](figures/{voltage_figure.name})",
                    "",
                    "## Artifacts",
                    "",
                    f"- Building load CSV: `{artifacts['building_load'].name}`",
                    f"- Mapped load CSV: `{artifacts['mapped_load'].name}`",
                    f"- OpenDSS hourly results CSV: `{artifacts['power_flow'].name}`",
                    f"- Metrics CSV: `{artifacts['metrics'].name}`",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return report_path


def _write_svg_line(path: Path, rows: list[dict], key: str, title: str) -> None:
    width = 760
    height = 280
    pad = 44
    values = [float(row[key]) for row in rows] if rows else [0.0]
    low = min(values)
    high = max(values)
    span = high - low if high != low else 1.0
    points = []
    for idx, value in enumerate(values):
        x = pad + (width - 2 * pad) * (idx / max(len(values) - 1, 1))
        y = height - pad - (height - 2 * pad) * ((value - low) / span)
        points.append(f"{x:.2f},{y:.2f}")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{pad}" y="28" font-family="Arial" font-size="18" fill="#1f2937">{title}</text>
  <line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#94a3b8"/>
  <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#94a3b8"/>
  <polyline points="{' '.join(points)}" fill="none" stroke="#2563eb" stroke-width="3"/>
  <text x="{pad}" y="{height-12}" font-family="Arial" font-size="12" fill="#475569">min {low:.3f} / max {high:.3f}</text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")
