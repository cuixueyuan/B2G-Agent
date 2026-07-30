from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def run_resstock_backend(config: dict[str, Any]) -> None:
    """Validate future ResStock prerequisites and stop before any real simulation.

    This backend is intentionally a scaffold. It should never report success until
    the project has real BuildStockBatch project creation, execution, and result
    collection implemented.
    """
    buildstockbatch_available = importlib.util.find_spec("buildstockbatch") is not None
    resstock_path = _resstock_repository_path(config)
    resstock_configured = bool(resstock_path and resstock_path.exists())

    if not buildstockbatch_available or not resstock_configured:
        reasons = []
        if not buildstockbatch_available:
            reasons.append("BuildStockBatch Python package `buildstockbatch` is not installed.")
        if not resstock_path:
            reasons.append("No ResStock repository path is configured in `resstock.project_dir`.")
        elif not resstock_path.exists():
            reasons.append(f"Configured ResStock repository path does not exist: {resstock_path}")
        raise RuntimeError(_setup_message(reasons))

    raise RuntimeError(
        "The resstock backend is scaffold-only. BuildStockBatch and a ResStock path were found, "
        "but real ResStock simulation is not implemented yet. Use `--backend synthetic` for the current runnable sample."
    )


def create_buildstockbatch_project(config: dict[str, Any]) -> Path:
    """Placeholder for creating a BuildStockBatch project directory.

    Future implementation notes:
    - BuildStockBatch can be configured to consume a precomputed sample file.
    - This sample's fixed 50 buildings should be translated into that precomputed
      sample so the real ResStock run matches `config/buildings_50.csv`.
    """
    raise NotImplementedError("BuildStockBatch project creation is not implemented yet.")


def write_precomputed_sample(config: dict[str, Any]) -> Path:
    """Placeholder for writing the fixed 50-building precomputed sample file.

    BuildStockBatch supports precomputed samples, which is the right mechanism
    for preserving this sample's deterministic set of 50 buildings when moving
    from the synthetic backend to real ResStock simulation.
    """
    raise NotImplementedError("Writing a BuildStockBatch precomputed sample is not implemented yet.")


def run_buildstockbatch(config: dict[str, Any], project_dir: Path) -> Path:
    """Placeholder for launching BuildStockBatch/OpenStudio/EnergyPlus runs."""
    raise NotImplementedError("BuildStockBatch execution is not implemented yet.")


def collect_timeseries_results(config: dict[str, Any], results_dir: Path) -> Path:
    """Placeholder for collecting ResStock timeseries into building load CSVs."""
    raise NotImplementedError("ResStock timeseries result collection is not implemented yet.")


def _resstock_repository_path(config: dict[str, Any]) -> Path | None:
    value = config.get("resstock", {}).get("resstock_repo_path")
    if not value:
        return None
    return Path(str(value)).expanduser()


def _setup_message(reasons: list[str]) -> str:
    detail = " ".join(reasons)
    return (
        f"{detail} ResStock/BuildStockBatch is not installed or configured for this sample. "
        "The current runnable backend is `synthetic`. To use real ResStock, install BuildStockBatch "
        "and clone/configure a ResStock repository with OpenStudio/EnergyPlus before running `--backend resstock`."
    )
