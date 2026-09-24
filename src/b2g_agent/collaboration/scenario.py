from __future__ import annotations

from typing import Any

from b2g_agent.collaboration.models import EngineerRole, ScenarioParameters


SCENARIO_ID = "harborview_residential_renewal"


ROLE_LABELS = {
    EngineerRole.BUILDING: "Building Engineer",
    EngineerRole.POWER: "Distribution Power Engineer",
}


ALLOWED_PARAMETER_DESCRIPTIONS = {
    "cooling_setpoint_c": "Cooling setpoint in degrees Celsius (20-28).",
    "building_count": "Number of new or renovated residential buildings (10-300).",
    "retrofit_level": "Envelope/HVAC retrofit: none, standard, or deep.",
    "pv_kw_per_building": "Average rooftop PV capacity per building in kW (0-15).",
    "demand_response_pct": "Peak-period demand reduction percentage (0-35).",
    "target_bus": "Connection bus: bus_3 through bus_8.",
    "transformer_capacity_kva": "Substation transformer capacity in kVA (250-1500).",
    "line_capacity_kw": "Feeder thermal capacity proxy in kW (200-1500).",
}


def counterpart_role(role: EngineerRole) -> EngineerRole:
    if role == EngineerRole.BUILDING:
        return EngineerRole.POWER
    return EngineerRole.BUILDING


def role_label(role: EngineerRole) -> str:
    return ROLE_LABELS[role]


def scenario_brief() -> dict[str, Any]:
    return {
        "scenario_id": SCENARIO_ID,
        "title": "Harborview Residential Renewal",
        "location": "A representative U.S. coastal community",
        "summary": (
            "Harborview plans a phased residential expansion and retrofit program. "
            "The building team must preserve occupant comfort and control retrofit cost, "
            "while the distribution team must keep voltage and equipment loading within limits."
        ),
        "user_roles": [
            {
                "id": EngineerRole.BUILDING.value,
                "label": role_label(EngineerRole.BUILDING),
                "mission": "Define comfort, retrofit, electrification, PV, and demand-flexibility choices.",
            },
            {
                "id": EngineerRole.POWER.value,
                "label": role_label(EngineerRole.POWER),
                "mission": "Define connection, feeder capacity, voltage, and upgrade choices.",
            },
        ],
        "hard_constraints": [
            "Minimum service voltage must remain at or above 0.95 p.u.",
            "Feeder line loading must not exceed 100%.",
            "Transformer loading must not exceed 100%.",
        ],
        "building_objectives": [
            "Maintain a defensible cooling setpoint and occupant comfort.",
            "Limit retrofit cost and avoid unnecessary equipment changes.",
            "Use PV and demand flexibility where they improve the joint plan.",
        ],
        "grid_objectives": [
            "Serve the planned buildings without voltage violations.",
            "Avoid thermal overloads and preserve operating margin.",
            "Use targeted upgrades rather than unconstrained expansion.",
        ],
        "allowed_parameters": ALLOWED_PARAMETER_DESCRIPTIONS,
        "defaults": ScenarioParameters().model_dump(mode="json"),
        "simulation_note": (
            "This vertical slice uses a deterministic, auditable residential-load and radial-feeder backend. "
            "The EnergyPlus-MCP and PowerMCP adapters are explicit extension points for the next integration stage."
        ),
    }


def validate_parameter_changes(current: ScenarioParameters, changes: dict[str, Any]) -> ScenarioParameters:
    unknown = sorted(set(changes) - set(ALLOWED_PARAMETER_DESCRIPTIONS))
    if unknown:
        raise ValueError(f"Unsupported scenario parameter(s): {', '.join(unknown)}")
    payload = current.model_dump(mode="json")
    payload.update(changes)
    return ScenarioParameters.model_validate(payload)


def compact_case_context(parameters: ScenarioParameters) -> str:
    values = parameters.model_dump(mode="json")
    return "; ".join(f"{name}={value}" for name, value in values.items())
