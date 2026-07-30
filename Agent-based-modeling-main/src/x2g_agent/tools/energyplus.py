from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnergyPlusRun:
    output_dir: Path
    meter_csv: Path | None


def run_energyplus(config: dict, output_dir: Path) -> EnergyPlusRun:
    executable = _config_or_env(config, "executable", "executable_env")
    idf = _config_or_env(config, "idf", "idf_env")
    epw = _config_or_env(config, "epw", "epw_env")
    if not executable or not idf or not epw:
        raise ValueError("EnergyPlus direct mode requires executable, idf, and epw from config or .env.")

    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        "-w",
        epw,
        "-d",
        str(output_dir),
        str(idf),
    ]
    subprocess.run(command, check=True)
    candidates = sorted(output_dir.glob("*Meter*.csv")) + sorted(output_dir.glob("*.csv"))
    return EnergyPlusRun(output_dir=output_dir, meter_csv=candidates[0] if candidates else None)


def _config_or_env(config: dict, value_key: str, env_key: str) -> str | None:
    value = config.get(value_key)
    if value:
        return str(value)
    env_name = config.get(env_key)
    if env_name:
        return os.getenv(str(env_name))
    return None
