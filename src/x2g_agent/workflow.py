from __future__ import annotations

from pathlib import Path

from x2g_agent.cases.building_to_grid.workflow import run_building_to_grid
from x2g_agent.models import WorkflowResult


def run_building_to_grid_workflow(config_path: Path) -> WorkflowResult:
    state = run_building_to_grid(config_path)
    artifacts = state["artifacts"]

    return WorkflowResult(
        output_root=Path(state["output_root"]),
        building_load_csv=Path(artifacts["building_load_csv"]),
        mapped_load_csv=Path(artifacts["mapped_load_csv"]),
        power_flow_csv=Path(artifacts["power_flow_result_csv"]),
        metrics_csv=Path(artifacts["risk_summary_csv"]),
        report_path=Path(artifacts["markdown_report"]),
    )
