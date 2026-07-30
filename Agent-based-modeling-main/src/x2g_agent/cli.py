from __future__ import annotations

import argparse
from pathlib import Path

from x2g_agent.cases.building_to_grid.workflow import run_building_to_grid as run_case


def run_building_to_grid(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the X2G Building-to-Grid workflow.")
    parser.add_argument(
        "--config",
        default="samples/single-building-to-grid/configs/building_to_grid.yaml",
        help="Path to YAML config.",
    )
    args = parser.parse_args(argv)

    state = run_case(Path(args.config))
    print(f"Output root: {state['output_root']}")
    print("Output paths:")
    for name, path in sorted(state["artifacts"].items()):
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_building_to_grid())
