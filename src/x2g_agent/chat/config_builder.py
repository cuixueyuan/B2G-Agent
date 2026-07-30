from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any

from x2g_agent.config import _load_yaml


class ConfigBuilder:
    """Builds temporary Building-to-Grid configs for chat sessions."""

    def __init__(
        self,
        base_config_path: str | Path = "samples/single-building-to-grid/configs/building_to_grid.yaml",
        session_root: str | Path = "samples/single-building-to-grid/outputs/chat_sessions",
        session_id: str | None = None,
    ) -> None:
        self.base_config_path = Path(base_config_path)
        self.session_root = Path(session_root)
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.session_root / self.session_id
        self.config = self._load_base_config()
        self._ensure_chat_paths()
        self._ensure_sample_asset_paths()

    def apply_intent(self, name: str, slots: dict[str, Any] | None = None) -> Path:
        slots = slots or {}
        if name == "set_mode":
            self.set_mode(str(slots["mode"]))
        elif name == "set_bus":
            self.set_bus(str(slots["bus_id"]))
        elif name == "set_load_scale":
            self.set_load_scale(float(slots["load_scale"]))
        return self.write()

    def set_mode(self, mode: str) -> None:
        if mode not in {"mock", "real"}:
            raise ValueError(f"Unsupported Building-to-Grid mode: {mode}")
        self.config.setdefault("case", {})["mode"] = mode

    def set_bus(self, bus_id: str) -> None:
        bus = bus_id.replace("-", "_")
        self.config.setdefault("building", {})["bus_id"] = bus
        self.config.setdefault("opendss", {})["target_bus"] = bus

    def set_load_scale(self, load_scale: float) -> None:
        if load_scale <= 0:
            raise ValueError("Load scale must be greater than zero.")
        self.config.setdefault("building", {})["load_scale"] = load_scale

    def write(self) -> Path:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        path = self.session_dir / "building_to_grid_chat.yaml"
        path.write_text(_dump_yaml(self.config), encoding="utf-8")
        return path

    def _load_base_config(self) -> dict[str, Any]:
        if self.base_config_path.exists():
            return copy.deepcopy(_load_yaml(self.base_config_path))
        return {
            "case": {"name": "Building-to-Grid", "mode": "mock"},
            "paths": {},
            "energyplus": {
                "executable": "${ENERGYPLUS_EXE}",
                "idf_path": "${ENERGYPLUS_IDF}",
                "epw_path": "${ENERGYPLUS_EPW}",
                "timestep_per_hour": 1,
            },
            "building": {"building_id": "single_building_001", "bus_id": "bus_4", "load_scale": 1.0, "power_factor": 0.95},
            "opendss": {
                "backend": "opendssdirect",
                "feeder_template": "../data_sample/opendss/simple_radial_feeder.dss",
                "target_bus": "bus_4",
                "base_kv": 12.47,
            },
            "thresholds": {"voltage_min_pu": 0.95, "voltage_max_pu": 1.05, "line_loading_limit_pct": 100},
        }

    def _ensure_chat_paths(self) -> None:
        self.config.setdefault("paths", {})
        self.config["paths"]["output_root"] = str((self.session_dir / "run").as_posix())
        self.config["paths"].setdefault("data_root", str(self.session_dir.as_posix()))

    def _ensure_sample_asset_paths(self) -> None:
        opendss = self.config.setdefault("opendss", {})
        feeder_template = opendss.get("feeder_template")
        if feeder_template:
            opendss["feeder_template"] = str(_resolve_path(feeder_template, self.base_config_path.parent).as_posix())


def _dump_yaml(value: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    for key, item in value.items():
        prefix = " " * indent + f"{key}:"
        if isinstance(item, dict):
            lines.append(prefix)
            lines.append(_dump_yaml(item, indent + 2).rstrip())
        else:
            lines.append(f"{prefix} {_format_scalar(item)}")
    return "\n".join(lines) + "\n"


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text.startswith("${") and text.endswith("}"):
        return f'"{text}"'
    if any(char in text for char in [":", "#", "{", "}", "[", "]"]) or " " in text:
        return f'"{text}"'
    return text


def _resolve_path(value: str | Path, base: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base / path).resolve()
