from __future__ import annotations

from pathlib import Path
from typing import Any

from resstock_backend import run_resstock_backend
from synthetic_backend import run_synthetic_backend
from utils import load_case_config


def run_building_simulations(config: dict[str, Any], backend: str) -> list[Path]:
    if backend == "synthetic":
        return run_synthetic_backend(config)
    if backend == "resstock":
        run_resstock_backend(config)
        return []
    raise ValueError(f"Unsupported backend: {backend}")


def main() -> int:
    config = load_case_config()
    paths = run_building_simulations(config, "synthetic")
    print(f"Wrote {len(paths)} synthetic building load profiles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
