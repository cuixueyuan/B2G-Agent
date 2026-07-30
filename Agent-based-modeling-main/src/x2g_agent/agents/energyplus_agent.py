from __future__ import annotations

from pathlib import Path

from x2g_agent.agents.base import Agent, WorkflowState
from x2g_agent.tools.energyplus_tool import run_energyplus_or_mock
from x2g_agent.tools.load_parser import write_csv


class EnergyPlusAgent(Agent):
    def run(self, state: WorkflowState) -> WorkflowState:
        config = state["config"]
        output_root = Path(state["output_root"])
        energyplus_output = output_root / "energyplus"
        rows = run_energyplus_or_mock(config["energyplus"], energyplus_output)
        if config["energyplus"].get("mode") == "real":
            path = write_csv(output_root / "load_profiles" / "building_load.csv", rows)
        else:
            path = write_csv(output_root / "building_load.csv", rows)
        state["building_load_rows"] = rows
        state["artifacts"]["building_load_csv"] = path
        return state
