from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkflowResult:
    output_root: Path
    building_load_csv: Path
    mapped_load_csv: Path
    power_flow_csv: Path
    metrics_csv: Path
    report_path: Path
