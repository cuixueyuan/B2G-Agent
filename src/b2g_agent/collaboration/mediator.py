from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from b2g_agent.collaboration.models import (
    EngineerRole,
    MediatedReply,
    MediatorPlan,
    ScenarioParameters,
    SimulationRun,
    SimulationScope,
)
from b2g_agent.collaboration.scenario import (
    ALLOWED_PARAMETER_DESCRIPTIONS,
    compact_case_context,
    role_label,
)


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class B2GMediator:
    """LLM-first mediator with a deterministic offline fallback.

    The API key is read server-side only. The browser never receives it, and no
    key or authorization header is written to session artifacts.
    """

    def __init__(self, *, client: Any | None = None, model: str | None = None) -> None:
        _load_local_env()
        self.model = model or os.getenv("B2G_MODEL") or os.getenv("B2G_CHAT_MODEL") or "gpt-4.1-mini"
        self.enabled = os.getenv("B2G_LLM_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
        self._client = client if client is not None else self._build_client()
        self.last_backend = f"openai:{self.model}" if self._client is not None else "local-fallback"
        self.last_error: str | None = None

    @property
    def configured(self) -> bool:
        return self._client is not None and self.enabled

    def plan_turn(
        self,
        *,
        text: str,
        user_role: EngineerRole,
        counterpart_role: EngineerRole,
        parameters: ScenarioParameters,
        recent_messages: list[dict[str, Any]],
    ) -> MediatorPlan:
        if self.configured:
            try:
                plan = self._call_json(
                    MediatorPlan,
                    system=_planning_prompt(user_role, counterpart_role),
                    user=json.dumps(
                        {
                            "message": text,
                            "current_case": parameters.model_dump(mode="json"),
                            "recent_conversation": recent_messages[-8:],
                        },
                        ensure_ascii=False,
                    ),
                )
                self.last_backend = f"openai:{self.model}"
                self.last_error = None
                return plan
            except Exception as exc:  # pragma: no cover - network/provider dependent
                self.last_error = exc.__class__.__name__
        self.last_backend = "local-fallback"
        return _local_plan(text, user_role, counterpart_role)

    def compose_reply(
        self,
        *,
        original_text: str,
        user_role: EngineerRole,
        counterpart_role: EngineerRole,
        parameters: ScenarioParameters,
        plan: MediatorPlan,
        run: SimulationRun | None,
    ) -> MediatedReply:
        if self.configured and self.last_backend.startswith("openai:"):
            try:
                reply = self._call_json(
                    MediatedReply,
                    system=_reply_prompt(user_role, counterpart_role),
                    user=json.dumps(
                        {
                            "original_message": original_text,
                            "mediator_plan": plan.model_dump(mode="json"),
                            "current_case": parameters.model_dump(mode="json"),
                            "simulation": run.model_dump(mode="json") if run else None,
                        },
                        ensure_ascii=False,
                    ),
                )
                self.last_error = None
                return reply
            except Exception as exc:  # pragma: no cover - network/provider dependent
                self.last_error = exc.__class__.__name__
                self.last_backend = "local-fallback"
        return _local_reply(user_role, counterpart_role, parameters, plan, run)

    def _call_json(
        self,
        response_model: type[ResponseModel],
        *,
        system: str,
        user: str,
    ) -> ResponseModel:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The LLM returned an empty response.")
        return response_model.model_validate_json(content)

    def _build_client(self) -> Any | None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        placeholder_prefixes = ("your_", "replace_", "example_", "<")
        if not self.enabled or not api_key or api_key.lower().startswith(placeholder_prefixes):
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None
        return OpenAI(api_key=api_key)


def _planning_prompt(user_role: EngineerRole, counterpart_role: EngineerRole) -> str:
    schema = json.dumps(MediatorPlan.model_json_schema(), ensure_ascii=False)
    allowed = json.dumps(ALLOWED_PARAMETER_DESCRIPTIONS, ensure_ascii=False)
    return f"""
You are the planning layer of B2G-Agent, a simulation-grounded mediator between a
{role_label(user_role)} and a {role_label(counterpart_role)}.

Your responsibilities are to understand the user's free-form engineering message,
translate it for the counterpart, and decide whether a validated simulation is needed.
Do not invent simulation results. Do not claim a model was modified or run.

Return JSON only and exactly match this JSON Schema:
{schema}

Rules:
- requested_changes may contain only these keys and value domains: {allowed}
- Use simulation_scope="coupled" for changes that can affect both buildings and the grid.
- Use simulation_scope="grid" only for a purely grid-capacity or connection change.
- Use simulation_scope="none" for discussion, explanations, or clarification.
- Ask one focused clarification question when a material parameter is ambiguous.
- needs_confirmation=true for topology changes, very large capacity changes, or low-confidence interpretations.
- Preserve the user's professional intent; do not optimize away their stated priorities.
- confidence must reflect interpretation confidence, not confidence in unrun physics.
""".strip()


def _reply_prompt(user_role: EngineerRole, counterpart_role: EngineerRole) -> str:
    schema = json.dumps(MediatedReply.model_json_schema(), ensure_ascii=False)
    return f"""
You are B2G-Agent after the planning and optional simulation stages.
The human is the {role_label(user_role)}. The simulated counterpart is the
{role_label(counterpart_role)}.

Return JSON only and exactly match this JSON Schema:
{schema}

Requirements:
- mediator_message explains the interpretation and evidence in plain language.
- counterpart_message speaks in first person as the counterpart engineer and responds
  to the user's proposal using only supplied case state and simulation evidence.
- next_question advances the joint design toward a feasible, mutually acceptable plan.
- decision_note records a concrete proposal or result; otherwise use null.
- Clearly distinguish user input, assumptions, and computed results.
- Never fabricate a metric. If simulation is null, say that no new simulation was run.
- Avoid pretending the deterministic vertical backend is a calibrated EnergyPlus or OpenDSS result.
""".strip()


def _local_plan(
    text: str,
    user_role: EngineerRole,
    counterpart_role: EngineerRole,
) -> MediatorPlan:
    normalized = " ".join(text.lower().split())
    changes: dict[str, Any] = {}

    temperature = re.search(r"(\d+(?:\.\d+)?)\s*(?:°?\s*c|摄氏度|度)", normalized)
    if temperature:
        changes["cooling_setpoint_c"] = float(temperature.group(1))
    building_count = re.search(r"(\d+)\s*(?:栋|buildings?|homes?)", normalized)
    if building_count:
        changes["building_count"] = int(building_count.group(1))
    bus = re.search(r"bus[_\s-]?([3-8])|(?:节点|母线)\s*([3-8])", normalized)
    if bus:
        changes["target_bus"] = f"bus_{bus.group(1) or bus.group(2)}"
    transformer = re.search(r"(\d+(?:\.\d+)?)\s*(?:kva|千伏安)", normalized)
    if transformer:
        changes["transformer_capacity_kva"] = float(transformer.group(1))
    line_capacity = re.search(r"(?:line|线路).*?(\d+(?:\.\d+)?)\s*kw", normalized)
    if line_capacity:
        changes["line_capacity_kw"] = float(line_capacity.group(1))
    demand_response = re.search(r"(?:demand response|需求响应|削峰).*?(\d+(?:\.\d+)?)\s*%", normalized)
    if demand_response:
        changes["demand_response_pct"] = float(demand_response.group(1))
    pv = re.search(r"(?:pv|光伏).*?(\d+(?:\.\d+)?)\s*kw", normalized)
    if pv:
        changes["pv_kw_per_building"] = float(pv.group(1))
    if any(word in normalized for word in ["deep retrofit", "深度改造"]):
        changes["retrofit_level"] = "deep"
    elif any(word in normalized for word in ["standard retrofit", "标准改造"]):
        changes["retrofit_level"] = "standard"

    finalize = any(word in normalized for word in ["finalize", "final plan", "定稿", "最终方案"])
    should_simulate = bool(changes) or any(
        word in normalized for word in ["simulate", "simulation", "run", "仿真", "模拟", "分析"]
    )
    if finalize:
        intent = "finalize"
        scope = SimulationScope.NONE
    elif should_simulate:
        intent = "simulate"
        grid_only = changes and set(changes) <= {
            "target_bus",
            "transformer_capacity_kva",
            "line_capacity_kw",
        }
        scope = SimulationScope.GRID if grid_only else SimulationScope.COUPLED
    else:
        intent = "discuss"
        scope = SimulationScope.NONE

    return MediatorPlan(
        intent=intent,
        interpreted_intent=(
            f"The {role_label(user_role)} is proposing a scenario change."
            if changes
            else f"The {role_label(user_role)} is sharing a professional view or question."
        ),
        translation_for_counterpart=(
            f"Translate the message into implications relevant to the {role_label(counterpart_role)}."
        ),
        requested_changes=changes,
        simulation_scope=scope,
        needs_confirmation=False,
        assumptions=[],
        confidence=0.55,
    )


def _local_reply(
    user_role: EngineerRole,
    counterpart_role: EngineerRole,
    parameters: ScenarioParameters,
    plan: MediatorPlan,
    run: SimulationRun | None,
) -> MediatedReply:
    if plan.clarification_question:
        return MediatedReply(
            mediator_message=plan.clarification_question,
            counterpart_message="I will hold my engineering response until that assumption is clear.",
            next_question=plan.clarification_question,
            decision_note=None,
        )

    if run is None:
        return MediatedReply(
            mediator_message=(
                f"I interpreted this as: {plan.interpreted_intent} No new simulation was run. "
                f"Current shared case: {compact_case_context(parameters)}."
            ),
            counterpart_message=(
                f"As the {role_label(counterpart_role)}, I understand the proposal. "
                "Please identify the parameter or acceptance criterion you want us to test next."
            ),
            next_question="Which concrete scenario change should we test against the joint constraints?",
            decision_note=None,
        )

    metrics = run.metrics
    mediator_message = (
        f"I translated the proposal into validated scenario parameters and ran the {run.backend} backend. "
        f"The feeder peak is {metrics.feeder_peak_kw:.1f} kW, minimum voltage is "
        f"{metrics.minimum_voltage_pu:.3f} p.u., maximum line loading is "
        f"{metrics.maximum_line_loading_pct:.1f}%, and maximum transformer loading is "
        f"{metrics.maximum_transformer_loading_pct:.1f}%."
    )
    if metrics.feasible:
        counterpart_message = (
            f"As the {role_label(counterpart_role)}, I can accept this as a technically feasible candidate. "
            "I would still like to compare its cost and professional trade-offs with the baseline."
        )
        next_question = "Do you want to accept this candidate or compare one lower-cost alternative?"
    else:
        counterpart_message = (
            f"As the {role_label(counterpart_role)}, I cannot accept this candidate yet because one or more "
            "hard grid constraints are violated. We should adjust demand, connection, or capacity."
        )
        next_question = "Which lever should we test next: building flexibility, retrofit, connection bus, or capacity?"
    return MediatedReply(
        mediator_message=mediator_message,
        counterpart_message=counterpart_message,
        next_question=next_question,
        decision_note=(
            f"Run {run.run_id}: {'feasible' if metrics.feasible else 'needs revision'}; "
            f"building score {metrics.building_satisfaction_score:.1f}, grid score {metrics.grid_reliability_score:.1f}."
        ),
    )


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[3] / ".env"
    try:
        from dotenv import load_dotenv
    except ImportError:
        if not env_path.exists():
            return
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    else:
        load_dotenv(env_path)
