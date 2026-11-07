"""Validated-plan original-goal attainment from immutable physics artifacts."""
from __future__ import annotations

import math
import json
import hashlib
from functools import lru_cache
from pathlib import Path

from b2g_agent.artifact_paths import resolve_recorded_path
from b2g_agent.publication import recorded_hash_matches

QUALITY_PROTOCOL = "validated-plan-goal-attainment-20261106"
EVIDENCE_INPUT_HASHES = {}

FAMILIES = {
    "peak_shaving", "congestion_management", "voltage_management",
    "reserve_service", "renewable_absorption", "baseline_flexibility",
    "market_trading",
}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Required numeric evidence is absent or invalid: {value!r}")
    if not math.isfinite(value):
        raise ValueError("Non-finite evidence")
    return float(value)


def clip(value):
    return min(1.0, max(0.0, number(value)))


def window_indices(window):
    def index(value):
        hour, minute = map(int, value.split(":"))
        if minute % 15 or not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("Unsupported interval")
        return hour * 4 + minute // 15
    first, last = index(window["start"]), index(window["end"])
    if (window["start"], window["end"]) == ("00:00", "23:45"):
        return list(range(96))  # frozen benchmark's full-day convention
    if last <= first:
        raise ValueError("Empty or overnight window")
    return list(range(first, last))


def family_windows(spec):
    families, windows = spec["task_families"], spec["windows"]
    if len(families) == len(windows) and len(families) > 1:
        bindings = list(zip(families, windows))
    else:
        bindings = [(f, w) for f in families for w in windows]
    result = {}
    for family, window in bindings:
        if family not in FAMILIES:
            raise ValueError("Unknown family")
        result.setdefault(family, set()).update(window_indices(window))
    return {key: sorted(value) for key, value in result.items()}


def scope_matches(source, physical):
    def pairs(spec):
        if len(spec["target_bems"]) != len(spec["target_buses"]):
            return None
        return set(zip(spec["target_bems"], spec["target_buses"]))
    return (
        source["operating_day"] == physical["operating_day"]
        and pairs(source) is not None
        and pairs(source) == pairs(physical)
        and set(source["task_families"]) == set(physical["task_families"])
        and family_windows(source) == family_windows(physical)
    )


def interval_coverage(series, indices, target, sign=1):
    if len(series) != 96 or not indices or target <= 0:
        raise ValueError("Incomplete 15-minute evidence or nonpositive source target")
    return sum(clip(sign * number(series[i]) / target) for i in indices) / len(indices)


def family_scores(source, metrics, service_by_direction):
    target_field = source["fields"]["target_power"]
    target = number(target_field["value"])
    if target_field["unit"] != "kW" or target <= 0:
        raise ValueError("Original target must be positive kW")
    indices = family_windows(source)
    result, details = {}, {}
    for family in source["task_families"]:
        if family == "baseline_flexibility":
            down = number(metrics["validated_downward_flexibility_kw"])
            up = number(metrics["validated_upward_flexibility_kw"])
            result[family] = clip(min(down, up) / target)
            details[family] = {
                "original_target_kw": target, "downward_kw": down,
                "upward_kw": up, "basis": "symmetric_capacity",
            }
            continue
        direction = "absorption" if family == "renewable_absorption" else "reduction"
        sign = -1 if direction == "absorption" else 1
        series = service_by_direction.get(direction, service_by_direction.get("native"))
        if series is None:
            raise ValueError(f"Missing directional evidence for {family}")
        coverage = interval_coverage(series, indices[family], target, sign)
        detail = {
            "original_target_kw": target, "interval_count": len(indices[family]),
            "interval_coverage": coverage,
        }
        score = coverage
        if family == "peak_shaving":
            peak = number(metrics["feeder_peak_reduction_kw"])
            score = min(score, clip(peak / target))
            detail["feeder_peak_reduction_kw"] = peak
        elif family == "market_trading":
            price_field = source["fields"]["offer_price"]
            if price_field["unit"] != "USD/MWh":
                raise ValueError("Unsupported original offer price unit")
            price = number(price_field["value"])
            expected = target * len(indices[family]) * 0.25 * price / 1000
            if expected <= 0:
                raise ValueError("Nonpositive original full-offer settlement")
            settlement = number(metrics["settlement_usd"])
            score = min(score, clip(settlement / expected))
            detail.update(original_full_offer_settlement_usd=expected,
                          recorded_settlement_usd=settlement)
        elif family in {"voltage_management", "congestion_management"}:
            key = ("baseline_voltage_violation_area_pu_h" if family == "voltage_management"
                   else "baseline_congestion_violation_area_pct_h")
            detail["baseline_violation_area"] = number(metrics[key])
            detail["interpretation"] = "requested_response_fulfillment_not_violation_removal"
        result[family], details[family] = score, detail
    priorities = {obj["name"]: obj["priority"] for obj in source["objectives"]}
    raw = {name: 1.0 / max(1, priorities.get(name, 1)) for name in result}
    total = sum(raw.values())
    weights = {name: value / total for name, value in raw.items()}
    aggregate = sum(result[name] * weights[name] for name in result)
    return aggregate, result, weights, details



@lru_cache(maxsize=8192)
def _read_verified_json(path_text, expected_sha=None):
    path = resolve_recorded_path(path_text).resolve()
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None and not recorded_hash_matches(path, expected_sha, actual_sha256=actual):
        raise ValueError(f"Physics artifact hash mismatch: {path}")
    EVIDENCE_INPUT_HASHES[str(path)] = actual
    return json.loads(raw)


def _linked(parent, reference):
    return _read_verified_json(str((parent / reference["path"]).resolve()), reference.get("sha256"))


def _final_validation(package_path, package):
    return _linked(package_path.parent, package["iterations"][-1]["coupled_validation"])


def validated_goal(source, evidence):
    """G is N/A for source clarification; no final-release gate is applied.

    Missing evidence receives zero. Corrupt existing artifacts fail loudly.
    A retains the delivery requirement; this score describes a validated plan.
    """
    if evidence is None or not evidence.converged or not evidence.hard_constraints_passed:
        return 0.0, {}
    path = resolve_recorded_path(evidence.evidence_path)
    if not path.is_file():
        return 0.0, {}
    package = _read_verified_json(str(path.resolve()), evidence.evidence_sha256)
    physical = _linked(path.parent, package["task_specification"])
    original = source.model_dump(mode="json") if hasattr(source, "model_dump") else source
    if not scope_matches(original, physical):
        return 0.0, {}
    if "directions" in package:
        series = {}
        for direction, ref in package["directions"].items():
            nested_path = resolve_recorded_path(path.parent / ref["evidence_package"])
            nested = _read_verified_json(str(nested_path.resolve()), ref["sha256"])
            series[direction] = _final_validation(nested_path, nested)["actual_aggregate_service_kw"]
        metrics = package["business_metrics"]
    else:
        validation = _final_validation(path, package)
        series = {"native": validation["actual_aggregate_service_kw"]}
        metrics = validation["business_metrics"]
    aggregate, goals, _, _ = family_scores(original, metrics, series)
    return aggregate, goals
