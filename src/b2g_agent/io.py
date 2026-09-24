from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable


def write_rows_csv(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    materialized = list(rows)
    if not materialized:
        path.write_text("", encoding="utf-8")
        return path

    fieldnames = list(materialized[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)
    return path


def read_rows_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
