from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Intent:
    name: str
    slots: dict[str, Any] = field(default_factory=dict)


class IntentParser:
    """Small rule-based parser for the first Building-to-Grid chat interface."""

    def parse(self, text: str) -> Intent:
        normalized = " ".join(text.strip().lower().split())
        if normalized in {"exit", "quit", "bye"}:
            return Intent("exit")
        if not normalized:
            return Intent("unknown")

        if "show" in normalized and "output" in normalized and "path" in normalized:
            return Intent("show_output_paths")
        if "summarize" in normalized and "voltage" in normalized:
            return Intent("summarize_voltage_violations")

        scale_match = re.search(r"(?:set\s+)?load\s+scale\s+(?:to\s+)?([0-9]*\.?[0-9]+)", normalized)
        if scale_match:
            return Intent("set_load_scale", {"load_scale": float(scale_match.group(1))})

        bus_match = re.search(r"(?:connect|map|attach).*?(?:to\s+)?(bus[_-]?[a-z0-9]+)", normalized)
        if bus_match and "building" in normalized:
            return Intent("set_bus", {"bus_id": bus_match.group(1).replace("-", "_")})

        if "run" in normalized and "building-to-grid" in normalized:
            if "real" in normalized:
                return Intent("run_case", {"mode": "real"})
            if "mock" in normalized:
                return Intent("run_case", {"mode": "mock"})
            return Intent("run_case")

        return Intent("unknown", {"text": text})
