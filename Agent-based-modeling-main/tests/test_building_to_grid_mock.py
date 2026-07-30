from __future__ import annotations

import csv
from pathlib import Path

from x2g_agent.workflow import run_building_to_grid_workflow


def test_mock_building_to_grid_workflow(tmp_path: Path) -> None:
    config = tmp_path / "case.yaml"
    output_root = tmp_path / "outputs"
    master = tmp_path / "master.dss"
    master.write_text("Clear\n", encoding="utf-8")
    config.write_text(
        f"""
case_name: test
output_root: {output_root.as_posix()}
energyplus:
  mode: mock
  mock:
    start: "2024-01-01T00:00:00"
    hours: 6
    base_kw: 50
    daily_amplitude_kw: 10
    power_factor: 0.95
load_mapping:
  target_bus: loadbus
  target_load_name: building_load
  phases: 3
  kv: 12.47
opendss:
  mode: mock
  master_file: {master.as_posix()}
  mock:
    source_voltage_pu: 1.0
    voltage_drop_per_100kw: 0.01
    feeder_base_kw: 100
    line_rating_kw: 250
metrics:
  voltage_min_pu: 0.95
  voltage_max_pu: 1.05
  line_overload_pct: 100
report:
  title: Test Report
""",
        encoding="utf-8",
    )

    result = run_building_to_grid_workflow(config)

    assert result.report_path.exists()
    assert result.building_load_csv.exists()
    assert result.mapped_load_csv.exists()
    assert result.power_flow_csv.exists()
    assert result.metrics_csv.exists()
    assert (output_root / "figures" / "building_load.svg").exists()
    assert (output_root / "figures" / "minimum_voltage.svg").exists()

    with result.power_flow_csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 6
    assert rows[0]["bus"] == "loadbus"
    assert float(rows[0]["feeder_kw"]) > 0

    report = result.report_path.read_text(encoding="utf-8")
    assert "# Test Report" in report
    assert "Voltage violations" in report


def test_mock_metrics_detect_line_overload(tmp_path: Path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text(
        f"""
output_root: {(tmp_path / "outputs").as_posix()}
energyplus:
  mode: mock
  mock:
    hours: 2
    base_kw: 500
    daily_amplitude_kw: 0
load_mapping:
  target_bus: loadbus
opendss:
  mode: mock
  mock:
    feeder_base_kw: 0
    line_rating_kw: 100
metrics:
  line_overload_pct: 100
report:
  title: Overload Test
""",
        encoding="utf-8",
    )

    result = run_building_to_grid_workflow(config)

    with result.metrics_csv.open(newline="", encoding="utf-8") as fh:
        metrics = next(csv.DictReader(fh))
    assert int(metrics["line_overloads"]) == 2
    assert float(metrics["feeder_peak_kw"]) == 500.0
