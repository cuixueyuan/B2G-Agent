from __future__ import annotations

from pathlib import Path
from typing import Any

from x2g_agent.agents.base import WorkflowState
from x2g_agent.agents.energyplus_agent import EnergyPlusAgent
from x2g_agent.agents.load_mapping_agent import LoadMappingAgent
from x2g_agent.agents.metrics_agent import MetricsAgent
from x2g_agent.agents.opendss_agent import OpenDSSAgent
from x2g_agent.agents.report_agent import ReportAgent
from x2g_agent.config import load_config


def run_building_to_grid(config_path: str | Path) -> WorkflowState:
    config = load_config(Path(config_path))
    output_root = Path(config["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "energyplus").mkdir(exist_ok=True)
    (output_root / "opendss").mkdir(exist_ok=True)
    (output_root / "figures").mkdir(exist_ok=True)

    state: dict[str, Any] = {
        "config": config,
        "output_root": output_root,
        "artifacts": {},
    }

    for agent in [
        EnergyPlusAgent(),
        LoadMappingAgent(),
        OpenDSSAgent(),
        MetricsAgent(),
        ReportAgent(),
    ]:
        state = agent.run(state)

    return state
