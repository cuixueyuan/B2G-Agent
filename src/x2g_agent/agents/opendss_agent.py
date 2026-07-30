from __future__ import annotations

from pathlib import Path

from x2g_agent.agents.base import Agent, WorkflowState
from x2g_agent.tools.load_parser import write_csv
from x2g_agent.tools.opendss_tool import run_opendss_detailed, write_opendss_loadshape_files


class OpenDSSAgent(Agent):
    def run(self, state: WorkflowState) -> WorkflowState:
        config = state["config"]
        output_root = Path(state["output_root"])
        opendss_dir = output_root / "opendss"
        opendss_config = dict(config["opendss"])
        if state["mapped_load_rows"]:
            opendss_config["target_bus"] = state["mapped_load_rows"][0]["target_bus"]

        opendss_inputs = write_opendss_loadshape_files(state["mapped_load_rows"], opendss_config, opendss_dir)
        dss_result = run_opendss_detailed(state["mapped_load_rows"], opendss_config)
        result_csv = write_csv(output_root / "power_flow_results.csv", dss_result.power_flow_rows)
        bus_voltage_csv = write_csv(output_root / "bus_voltage_pu_by_hour.csv", dss_result.bus_voltage_rows)
        feeder_power_csv = write_csv(output_root / "feeder_power_by_hour.csv", dss_result.feeder_power_rows)
        convergence_csv = write_csv(output_root / "convergence_status_by_hour.csv", dss_result.convergence_rows)

        state["power_flow_rows"] = dss_result.power_flow_rows
        state["bus_voltage_rows"] = dss_result.bus_voltage_rows
        state["feeder_power_rows"] = dss_result.feeder_power_rows
        state["convergence_rows"] = dss_result.convergence_rows
        state["artifacts"].update(
            {
                "opendss_loadshape_csv": opendss_inputs["loadshape_csv"],
                "opendss_load_injection_dss": opendss_inputs["load_injection_dss"],
                "power_flow_result_csv": result_csv,
                "bus_voltage_pu_by_hour_csv": bus_voltage_csv,
                "feeder_power_by_hour_csv": feeder_power_csv,
                "convergence_status_by_hour_csv": convergence_csv,
            }
        )
        return state
