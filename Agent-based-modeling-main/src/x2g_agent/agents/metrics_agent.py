from __future__ import annotations

from pathlib import Path

from x2g_agent.agents.base import Agent, WorkflowState
from x2g_agent.tools.grid_metrics import summarize_power_flow_risk
from x2g_agent.tools.load_parser import write_csv


class MetricsAgent(Agent):
    def run(self, state: WorkflowState) -> WorkflowState:
        output_root = Path(state["output_root"])
        config = state["config"]
        metrics = summarize_power_flow_risk(state["power_flow_rows"], config.get("metrics", config.get("thresholds", {})))
        path = write_csv(output_root / "risk_summary.csv", [metrics])
        state["risk_summary"] = metrics
        state["artifacts"]["risk_summary_csv"] = path
        return state
