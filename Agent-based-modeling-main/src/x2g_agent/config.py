from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import re

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in minimal runtimes
    yaml = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only in minimal runtimes
    load_dotenv = None


def load_config(config_path: Path) -> dict[str, Any]:
    """Load YAML config and resolve sample paths relative to the config file."""
    config_path = config_path.expanduser().resolve()
    _load_env(config_path.parent / ".env")
    repo_root = _find_repo_root(config_path.parent)
    _load_env(repo_root / ".env")
    _load_env(Path(".env"))

    config = _load_yaml(config_path)

    config_base = config_path.parent
    config["_config_path"] = str(config_path)
    config["_repo_root"] = str(repo_root)
    config["_config_base"] = str(config_base)
    config = _expand_env_values(config)
    config = normalize_building_to_grid_config(config, config_base)

    opendss = config.get("opendss", {})
    if opendss.get("master_file"):
        opendss["master_file"] = str(resolve_path(opendss["master_file"], config_base))
    return config


def normalize_building_to_grid_config(config: dict[str, Any], config_base: Path) -> dict[str, Any]:
    if "paths" not in config:
        config["output_root"] = str(resolve_path(config.get("output_root", "outputs"), config_base))
        return config

    case = config.get("case", {})
    paths = config.get("paths", {})
    building = config.get("building", {})
    thresholds = config.get("thresholds", {})
    energyplus = config.get("energyplus", {})
    opendss = config.get("opendss", {})

    output_root = paths.get("output_root", "outputs")
    mode = case.get("mode", "mock")
    feeder_template = opendss.get("feeder_template")

    config["output_root"] = str(resolve_path(output_root, config_base))
    config["energyplus"] = {
        **energyplus,
        "mode": mode,
        "idf": energyplus.get("idf_path"),
        "epw": energyplus.get("epw_path"),
        "mock": {
            "power_factor": building.get("power_factor", 0.95),
        },
    }
    config["load_mapping"] = {
        "target_bus": building.get("bus_id") or opendss.get("target_bus", "loadbus"),
        "target_load_name": "building_load",
        "phases": 3,
        "kv": opendss.get("base_kv", 12.47),
    }
    config["opendss"] = {
        **opendss,
        "mode": "mock" if mode == "mock" else "direct",
        "master_file": feeder_template,
        "load_name": "building_load",
        "target_bus": opendss.get("target_bus") or building.get("bus_id", "loadbus"),
    }
    config["metrics"] = {
        "voltage_min_pu": thresholds.get("voltage_min_pu", 0.95),
        "voltage_max_pu": thresholds.get("voltage_max_pu", 1.05),
        "line_overload_pct": thresholds.get("line_loading_limit_pct", 100.0),
    }
    config["report"] = {
        "title": case.get("name", "Building-to-Grid"),
    }
    return config


def resolve_path(value: str | Path, base: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _find_repo_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "pyproject.toml").exists() or (path / ".git").exists():
            return path
    return start


def _load_env(path: Path) -> None:
    if load_dotenv is not None:
        load_dotenv(path)
        return
    if not path.exists():
        return
    import os

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return _parse_simple_yaml(text)


def _expand_env_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env_values(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_expand_env_values(child) for child in value]
    if isinstance(value, str):
        return re.sub(r"\$\{([^}]+)\}", lambda match: os.getenv(match.group(1), match.group(0)), value)
    return value


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small mapping-only YAML subset used by the sample configs."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, sep, value = raw_line.strip().partition(":")
        if not sep:
            raise ValueError(f"Unsupported YAML line: {raw_line}")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if value.strip() == "":
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
        else:
            current[key] = _parse_scalar(value.strip())
    return root


def _parse_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    lower = value.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"null", "none"}:
        return None
    try:
        if any(char in value for char in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value
