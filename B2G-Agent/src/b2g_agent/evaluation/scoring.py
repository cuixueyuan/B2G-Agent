from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from b2g_agent.contracts import Episode, EpisodeGroundTruth, PipelineResult, TaskFamily
from b2g_agent.evaluation.goal_attainment import QUALITY_PROTOCOL, validated_goal
from b2g_agent.contracts.outcomes import validated_non_execution_report, rejection_causes, constraint_failure_codes


class InteractionScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.0"
    scoring_protocol_id: str = QUALITY_PROTOCOL
    scored_candidate: bool = True
    goal_applicable: bool = True
    episode_id: str
    semantic_fidelity: float = Field(ge=0.0, le=1.0)
    actionability: float = Field(ge=0.0, le=1.0)
    physical_feasibility: float = Field(ge=0.0, le=1.0)
    goal_achievement: float | None = Field(default=None, ge=0.0, le=1.0)
    interaction_quality: float = Field(ge=0.0, le=100.0)
    task_success: bool
    first_transfer: dict[str, Any]
    second_transfer: dict[str, Any]
    actionability_checks: dict[str, bool]
    goal_scores: dict[str, float]
    agent_metrics: dict[str, float | bool]


class InteractionScorer:
    """Implement the paper's F, A, V, G, Q and episode-success definitions."""

    def __init__(self, config_path: Path) -> None:
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        self.abs_tol = float(self.config["numeric_absolute_tolerance"])
        self.rel_tol = float(self.config["numeric_relative_tolerance"])

    def score(
        self,
        *,
        episode: Episode,
        groundtruth: EpisodeGroundTruth,
        candidate: PipelineResult,
        numeric_oracle: dict[str, Any] | None,
    ) -> InteractionScore:
        if episode.episode_id != groundtruth.episode_id:
            raise ValueError("Episode and ground truth IDs differ")
        if candidate.task_specification.episode_id != groundtruth.episode_id:
            raise ValueError("Candidate is not a frozen run for this episode")

        first = self._first_transfer(groundtruth, candidate)
        second = self._second_transfer(groundtruth, candidate, numeric_oracle)
        fidelity = 0.5 * (float(first["f1"]) + float(second["f1"]))
        actionability, action_checks = self._actionability(
            groundtruth, candidate, numeric_oracle
        )
        physical = self._physical_feasibility(
            episode, groundtruth, candidate, numeric_oracle
        )
        goal, goal_scores = self._goal_achievement(
            groundtruth, candidate, numeric_oracle
        )
        components = [fidelity, actionability, physical] + ([] if goal is None else [goal])
        quality = 100.0 * sum(components) / len(components)
        success = bool(
            fidelity >= float(self.config["semantic_success_threshold"])
            and math.isclose(actionability, 1.0, abs_tol=1e-12)
            and math.isclose(physical, 1.0, abs_tol=1e-12)
            and (goal is None or goal >= float(self.config["goal_success_threshold"]))
        )
        evidence_consistency = self._evidence_consistency(
            groundtruth, candidate, numeric_oracle
        )
        expected_route = (
            "clarify_sender"
            if groundtruth.perfect_execution.route == "clarify_sender"
            else "release"
        )
        has_annotated_error = (
            float(first["f1"]) < 1.0
            or float(second["f1"]) < 1.0
            or physical < 1.0
        )
        agent_metrics: dict[str, float | bool] = {
            "translator_required_field_f1": float(first["f1"]),
            "translator_mapping_accuracy": self._mapping_accuracy(
                groundtruth, candidate
            ),
            "translator_clarification_decision_correct": (
                candidate.task_specification.clarification_required
                == (groundtruth.perfect_execution.route == "clarify_sender")
            ),
            "actor_plan_legal": bool(
                candidate.execution_plan is None
                if groundtruth.perfect_execution.route == "clarify_sender"
                else candidate.execution_plan is not None
                and candidate.execution_plan.valid
            ),
            "actor_tool_chain_success": bool(
                groundtruth.perfect_execution.route == "clarify_sender"
                or candidate.physics_evidence is not None
            ),
            "actor_evidence_consistency": evidence_consistency,
            "reviewer_verdict_correct": (
                candidate.reviewer_decision.verdict
                == groundtruth.expected_reviewer_verdict
            ),
            "reviewer_routing_correct": (
                candidate.reviewer_decision.routing_decision == expected_route
            ),
            "reviewer_erroneous_release": bool(
                candidate.reviewer_decision.routing_decision == "release"
                and has_annotated_error
            ),
        }
        return InteractionScore(
            episode_id=episode.episode_id,
            semantic_fidelity=_clip(fidelity),
            actionability=_clip(actionability),
            physical_feasibility=_clip(physical),
            goal_achievement=None if goal is None else _clip(goal),
            goal_applicable=goal is not None,
            interaction_quality=max(0.0, min(100.0, quality)),
            task_success=success,
            first_transfer=first,
            second_transfer=second,
            actionability_checks=action_checks,
            goal_scores=goal_scores,
            agent_metrics=agent_metrics,
        )

    def _first_transfer(
        self,
        truth: EpisodeGroundTruth,
        candidate: PipelineResult,
    ) -> dict[str, Any]:
        reference = truth.task_specification
        predicted = candidate.task_specification
        fields = truth.perfect_execution.required_semantic_fields
        checks: dict[str, bool] = {}
        present: dict[str, bool] = {}
        for name in fields:
            expected = _semantic_field(reference, name)
            observed = _semantic_field(predicted, name)
            present[name] = _present(observed)
            checks[name] = self._equivalent(expected, observed, field=name)
        return _weighted_f1(
            fields,
            checks,
            present,
            self.config["semantic_field_weights"],
        )

    def _second_transfer(
        self,
        truth: EpisodeGroundTruth,
        candidate: PipelineResult,
        numeric: dict[str, Any] | None,
    ) -> dict[str, Any]:
        exchange = candidate.information_exchange
        if truth.perfect_execution.route == "clarify_sender":
            fields = ["decision", "completion_percentage", "clarification"]
            checks = {
                "decision": exchange.decision == "needs_clarification",
                "completion_percentage": self._equivalent(
                    0.0, exchange.completion_percentage
                ),
                "clarification": bool(
                    exchange.receiver_sent and exchange.sender_received
                ),
            }
            present = {
                "decision": bool(exchange.decision),
                "completion_percentage": exchange.completion_percentage is not None,
                "clarification": bool(exchange.receiver_sent),
            }
            weights = {
                "decision": self.config["reverse_field_weights"]["decision"],
                "completion_percentage": self.config["reverse_field_weights"][
                    "completion_percentage"
                ],
                "clarification": self.config["reverse_field_weights"]["clarification"],
            }
            return _weighted_f1(fields, checks, present, weights)
        if numeric is None:
            return _weighted_f1(
                ["decision"],
                {"decision": False},
                {"decision": exchange.decision != "pending_physics"},
                {"decision": 1.0},
            )
        expected_final = numeric["final_decision"]
        fields = ["decision", "committed_power_kw", "completion_percentage"]
        checks = {
            "decision": exchange.decision == expected_final["receiver_decision"],
            "committed_power_kw": self._equivalent(
                expected_final["committed_power_kw"], exchange.committed_power_kw
            ),
            "completion_percentage": self._equivalent(
                expected_final["completion_percentage"],
                exchange.completion_percentage,
            ),
        }
        present = {
            "decision": exchange.decision != "pending_physics",
            "committed_power_kw": exchange.committed_power_kw is not None,
            "completion_percentage": exchange.completion_percentage is not None,
        }
        weights = {
            name: float(self.config["reverse_field_weights"][name])
            for name in fields
        }
        candidate_metrics = (
            candidate.physics_evidence.business_metrics
            if candidate.physics_evidence is not None
            else {}
        )
        expected_values = numeric["business_metrics"].get(
            "requested_output_values", {}
        )
        for name, expected in expected_values.items():
            key = f"numeric_output:{name}"
            fields.append(key)
            observed = candidate_metrics.get("requested_output_values", {}).get(name)
            present[key] = observed is not None
            checks[key] = self._equivalent(expected, observed)
            weights[key] = float(
                self.config["reverse_field_weights"]["numeric_output"]
            )
        return _weighted_f1(fields, checks, present, weights)

    def _actionability(
        self,
        truth: EpisodeGroundTruth,
        candidate: PipelineResult,
        numeric: dict[str, Any] | None,
    ) -> tuple[float, dict[str, bool]]:
        exchange = candidate.information_exchange
        if truth.perfect_execution.route == "clarify_sender":
            correct = bool(
                candidate.task_specification.clarification_required
                and candidate.workflow_status != "blocked"
                and exchange.decision == "needs_clarification"
                and exchange.receiver_sent
                and exchange.sender_received
                and exchange.completion_percentage == 0.0
            )
            checks = {
                name: correct
                for name in self.config["actionability_field_weights"]
            }
            return float(correct), checks
        reference = truth.task_specification
        predicted = candidate.task_specification
        expected_final = numeric["final_decision"] if numeric else {}
        candidate_metrics = (
            candidate.physics_evidence.business_metrics
            if candidate.physics_evidence is not None
            else {}
        )
        expected_gap = (
            numeric["business_metrics"].get("maximum_remaining_service_gap_kw")
            if numeric
            else None
        )
        observed_gap = candidate_metrics.get("maximum_remaining_service_gap_kw")
        decision_match = bool(
            expected_final
            and exchange.decision == expected_final.get("receiver_decision")
        )
        modification_terms = decision_match
        if expected_final.get("receiver_decision") == "modified":
            modification_terms = bool(
                self._equivalent(
                    expected_final.get("committed_power_kw"),
                    exchange.committed_power_kw,
                )
                and self._equivalent(
                    expected_final.get("completion_percentage"),
                    exchange.completion_percentage,
                )
            )
        checks = {
            "target_objects": self._equivalent(
                (reference.target_bems, reference.target_buses),
                (predicted.target_bems, predicted.target_buses),
            ),
            "action_direction": self._equivalent(
                reference.task_families, predicted.task_families
            ),
            "quantity": self._equivalent(
                _field_value_unit(reference.fields.get("target_power")),
                _field_value_unit(predicted.fields.get("target_power")),
            ),
            "time_windows": self._equivalent(reference.windows, predicted.windows),
            "operating_constraints": self._equivalent(
                reference.constraints, predicted.constraints, field="constraints"
            ),
            "decision_status": decision_match,
            "modification_terms": modification_terms,
            # An internally correct draft is not a delivered interaction when
            # Reviewer exhausted corrections and withheld external release.
            "final_delivery": candidate.workflow_status != "blocked" and self._equivalent(
                expected_final.get("committed_power_kw"),
                exchange.committed_power_kw,
            ),
            "residual_gap": self._equivalent(expected_gap, observed_gap),
        }
        weights = self.config["actionability_field_weights"]
        denominator = sum(float(weights[name]) for name in checks)
        score = sum(float(weights[name]) for name, value in checks.items() if value)
        return score / denominator, checks

    def _physical_feasibility(
        self,
        episode: Episode,
        truth: EpisodeGroundTruth,
        candidate: PipelineResult,
        numeric: dict[str, Any] | None,
    ) -> float:
        if truth.perfect_execution.route == "clarify_sender":
            return float(
                candidate.information_exchange.decision == "needs_clarification"
                and candidate.physics_evidence is None
            )
        evidence = candidate.physics_evidence
        if (
            numeric is not None
            and numeric["final_decision"]["receiver_decision"] == "rejected"
            and candidate.information_exchange.decision == "rejected"
            and validated_non_execution_report(evidence)
        ):
            if "validated_metrics_by_direction" in numeric:
                expected_causes = {name: constraint_failure_codes(value)
                    for name, value in numeric["validated_metrics_by_direction"].items()
                    if constraint_failure_codes(value)}
            else:
                expected_causes = {"event": constraint_failure_codes({
                    "grid_violations": numeric.get("grid_violations", {}),
                    "comfort_violation_intervals": numeric.get("validated_metrics", {}).get("comfort_violation_intervals", 0)})}
            actual_causes = rejection_causes(evidence)
            return float(bool(actual_causes) and actual_causes == expected_causes
                         and evidence.execution_log.get("rejection_causes") == actual_causes)
        if evidence is None or not evidence.converged or not evidence.hard_constraints_passed:
            return 0.0
        # A generation-time difficulty tag is not a physical feasibility result.
        # Verified numerical validation takes precedence over that stale tag.
        if (numeric is not None and numeric.get("physics_truth_status") == "verified"
                and numeric["final_decision"]["receiver_decision"] == "accepted"):
            return 1.0
        if episode.difficulty.feasibility == "infeasible":
            if numeric is None:
                return 0.0
            return float(
                candidate.information_exchange.decision
                == numeric["final_decision"]["receiver_decision"]
                and candidate.information_exchange.decision != "accepted"
            )
        return 1.0

    def _goal_achievement(self, truth, candidate, numeric):
        # Numeric reference outcomes are not the denominator of original-goal attainment.
        if truth.perfect_execution.route == "clarify_sender":
            return None, {}
        return validated_goal(truth.task_specification, candidate.physics_evidence)

    def _evidence_consistency(
        self,
        truth: EpisodeGroundTruth,
        candidate: PipelineResult,
        numeric: dict[str, Any] | None,
    ) -> float:
        if truth.perfect_execution.route == "clarify_sender":
            return float(candidate.physics_evidence is None)
        if numeric is None or candidate.physics_evidence is None:
            return 0.0
        expected = numeric["business_metrics"].get("requested_output_values", {})
        observed = candidate.physics_evidence.business_metrics.get(
            "requested_output_values", {}
        )
        if not expected:
            return 0.0
        return sum(
            self._equivalent(value, observed.get(name))
            for name, value in expected.items()
        ) / len(expected)

    def _mapping_accuracy(
        self,
        truth: EpisodeGroundTruth,
        candidate: PipelineResult,
    ) -> float:
        expected = truth.task_specification
        observed = candidate.task_specification
        checks = (
            self._equivalent(expected.target_bems, observed.target_bems),
            self._equivalent(expected.target_buses, observed.target_buses),
            self._equivalent(expected.windows, observed.windows),
            self._equivalent(expected.task_families, observed.task_families),
            self._equivalent(
                _field_value_unit(expected.fields.get("target_power")),
                _field_value_unit(observed.fields.get("target_power")),
            ),
            self._equivalent(
                _field_value_unit(expected.fields.get("time_resolution")),
                _field_value_unit(observed.fields.get("time_resolution")),
            ),
        )
        return sum(checks) / len(checks)

    def _equivalent(
        self,
        expected: Any,
        observed: Any,
        *,
        field: str | None = None,
    ) -> bool:
        expected = _plain(expected)
        observed = _plain(observed)
        if expected is None or observed is None:
            return expected is observed
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            if not isinstance(observed, (int, float)) or isinstance(observed, bool):
                return False
            return math.isclose(
                float(expected),
                float(observed),
                abs_tol=self.abs_tol,
                rel_tol=self.rel_tol,
            )
        if field == "objectives":
            return _normalized_objectives(expected) == _normalized_objectives(observed)
        if field == "constraints":
            return _normalized_constraints(expected) == _normalized_constraints(observed)
        if isinstance(expected, list) and isinstance(observed, list):
            if field in {"task_families", "target_bems", "target_buses"}:
                return sorted(expected) == sorted(observed)
            return len(expected) == len(observed) and all(
                self._equivalent(left, right) for left, right in zip(expected, observed)
            )
        if isinstance(expected, dict) and isinstance(observed, dict):
            keys = set(expected) | set(observed)
            return all(
                key in expected
                and key in observed
                and self._equivalent(expected[key], observed[key])
                for key in keys
            )
        return expected == observed


def _semantic_field(specification: Any, name: str) -> Any:
    if name in {"target_power", "offer_price"}:
        field = specification.fields.get(name)
        if field is None:
            return None
        payload = _plain(field)
        return {
            "value": payload.get("value"),
            "unit": payload.get("unit"),
            "status": payload.get("status"),
        }
    return getattr(specification, name)


def _field_value_unit(field: Any) -> dict[str, Any] | None:
    if field is None:
        return None
    payload = _plain(field)
    return {"value": payload.get("value"), "unit": payload.get("unit")}


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return value.value
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    return value


def _present(value: Any) -> bool:
    value = _plain(value)
    return value is not None and value != [] and value != {}


def _weighted_f1(
    fields: list[str],
    checks: dict[str, bool],
    present: dict[str, bool],
    weights: dict[str, float],
) -> dict[str, Any]:
    reference_weight = sum(float(weights.get(name, 1.0)) for name in fields)
    predicted_weight = sum(
        float(weights.get(name, 1.0)) for name in fields if present.get(name, False)
    )
    matched_weight = sum(
        float(weights.get(name, 1.0)) for name in fields if checks.get(name, False)
    )
    precision = matched_weight / predicted_weight if predicted_weight else 0.0
    recall = matched_weight / reference_weight if reference_weight else 1.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "precision": _clip(precision),
        "recall": _clip(recall),
        "f1": _clip(f1),
        "field_checks": checks,
    }


def _normalized_objectives(values: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return sorted(
        (
            item.get("name"),
            item.get("metric"),
            item.get("operator"),
            item.get("value"),
            item.get("unit"),
            item.get("priority"),
        )
        for item in values
    )


def _normalized_constraints(values: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return sorted(
        (
            item.get("metric"),
            item.get("operator"),
            json.dumps(item.get("value"), sort_keys=True),
            item.get("unit"),
            item.get("hard", True),
        )
        for item in values
    )


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
