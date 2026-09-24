from __future__ import annotations

from b2g_agent.collaboration.models import ScenarioParameters
from b2g_agent.collaboration.simulator import ResidentialCommunitySimulator


def test_vertical_scenario_detects_baseline_constraints() -> None:
    run = ResidentialCommunitySimulator().run(ScenarioParameters(), trigger="test")

    assert run.metrics.feasible is False
    assert run.metrics.maximum_line_loading_pct > 100.0
    assert run.metrics.maximum_transformer_loading_pct > 100.0
    assert len(run.timeseries) == 24


def test_joint_building_grid_plan_can_become_feasible() -> None:
    simulator = ResidentialCommunitySimulator()
    baseline = simulator.run(ScenarioParameters(), trigger="baseline")
    joint = simulator.run(
        ScenarioParameters(
            retrofit_level="standard",
            demand_response_pct=12,
            transformer_capacity_kva=500,
            line_capacity_kw=500,
        ),
        trigger="joint plan",
    )

    assert joint.metrics.feasible is True
    assert joint.metrics.feeder_peak_kw < baseline.metrics.feeder_peak_kw
    assert joint.metrics.minimum_voltage_pu > baseline.metrics.minimum_voltage_pu
