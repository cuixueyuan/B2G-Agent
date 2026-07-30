from __future__ import annotations

from pathlib import Path
import sys


def _find_repo_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "pyproject.toml").exists():
            return path
    return start


SAMPLE_ROOT = Path(__file__).resolve().parents[1]
ROOT = _find_repo_root(Path(__file__).resolve())
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from x2g_agent.cases.building_to_grid.workflow import run_building_to_grid


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the X2G-Agent Building-to-Grid workflow.")
    parser.add_argument("--config", default="configs/building_to_grid.yaml", help="Path to YAML config.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = config_path if config_path.exists() else SAMPLE_ROOT / config_path

    final_state = run_building_to_grid(config_path)
    print(f"Output root: {final_state['output_root']}")
    print("Output paths:")
    for name, path in sorted(final_state["artifacts"].items()):
        print(f"- {name}: {path}")
