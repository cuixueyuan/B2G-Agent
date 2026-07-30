from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


SAMPLE_ROOT = Path(__file__).resolve().parents[1]


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or SAMPLE_ROOT).resolve()
    for path in [current, *current.parents]:
        if (path / "pyproject.toml").exists():
            return path
    return SAMPLE_ROOT


def sample_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (SAMPLE_ROOT / path).resolve()


def load_case_config(path: str | Path = "config/case_config.yaml") -> dict[str, Any]:
    config_path = sample_path(path)
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        config = parse_simple_yaml(text)
    else:
        config = yaml.safe_load(text) or {}
    config["_config_path"] = str(config_path)
    config["_sample_root"] = str(SAMPLE_ROOT)
    return config


def output_root(config: dict[str, Any]) -> Path:
    return sample_path("outputs")


def ensure_output_dirs(config: dict[str, Any]) -> dict[str, Path]:
    root = output_root(config)
    output_config = config.get("outputs", {})
    building_loads = sample_path(output_config.get("building_loads", root / "building_loads" / "building_loads.csv"))
    bus_loads = sample_path(output_config.get("bus_loads", root / "bus_loads" / "bus_loads.csv"))
    grid_results = sample_path(output_config.get("grid_results", root / "grid_results" / "grid_results.csv"))
    paths = {
        "root": root,
        "building_loads": building_loads.parent,
        "building_loads_csv": building_loads,
        "bus_loads": bus_loads.parent,
        "bus_loads_csv": bus_loads,
        "grid_results": grid_results.parent,
        "grid_results_csv": grid_results,
        "summary_json": grid_results.parent / "summary.json",
        "logs": root / "logs",
    }
    for key, path in paths.items():
        if key.endswith("_csv") or key.endswith("_json"):
            continue
        path.mkdir(parents=True, exist_ok=True)
    return paths


def buildings_csv_path() -> Path:
    return sample_path("config/buildings_50.csv")


def building_to_bus_csv_path() -> Path:
    return sample_path("config/building_to_bus.csv")


def simulation_hours(config: dict[str, Any]) -> int:
    return int(config.get("simulation_hours", 24))


def time_step_minutes(config: dict[str, Any]) -> int:
    return int(config.get("time_step_minutes", 60))


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with sample_path(path).open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    target = sample_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return target
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return target


def parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, sep, value = raw_line.strip().partition(":")
        if not sep:
            continue
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if value.strip() == "":
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
        else:
            current[key] = parse_scalar(value.strip())
    return root


def parse_scalar(value: str) -> Any:
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


def log_message(config: dict[str, Any], message: str) -> None:
    paths = ensure_output_dirs(config)
    log_path = paths["logs"] / "run_case.log"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(message.rstrip() + "\n")
