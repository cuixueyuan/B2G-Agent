from __future__ import annotations

from pathlib import Path

from x2g_agent.agents.base import Agent, WorkflowState
from x2g_agent.tools.load_parser import write_csv


class LoadMappingAgent(Agent):
    def run(self, state: WorkflowState) -> WorkflowState:
        config = state["config"]
        mapping = config["load_mapping"]
        building = config.get("building", {})
        output_root = Path(state["output_root"])
        scale = float(building.get("load_scale", mapping.get("load_scale", 1.0)))

        rows = []
        for row in state["building_load_rows"]:
            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "target_bus": mapping["target_bus"],
                    "load_name": mapping.get("target_load_name", "building_load"),
                    "phases": int(mapping.get("phases", 3)),
                    "kv": float(mapping.get("kv", 12.47)),
                    "building_kw": round(float(row["electricity_kw"]) * scale, 6),
                    "building_kvar": round(float(row.get("electricity_kvar", 0.0)) * scale, 6),
                }
            )

        path = write_csv(output_root / "mapped_building_load.csv", rows)
        state["mapped_load_rows"] = rows
        state["artifacts"]["mapped_load_csv"] = path
        return state
