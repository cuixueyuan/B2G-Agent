from __future__ import annotations

from pathlib import Path

from x2g_agent.chat.config_builder import ConfigBuilder
from x2g_agent.config import _load_yaml


def test_config_builder_writes_chat_config(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    base.write_text(
        """
case:
  name: Building-to-Grid
  mode: mock
paths:
  output_root: outputs/base
energyplus:
  executable: "${ENERGYPLUS_EXE}"
  idf_path: "${ENERGYPLUS_IDF}"
  epw_path: "${ENERGYPLUS_EPW}"
building:
  bus_id: bus_4
  load_scale: 1.0
opendss:
  target_bus: bus_4
  feeder_template: data_sample/opendss/simple_radial_feeder.dss
  base_kv: 12.47
thresholds:
  voltage_min_pu: 0.95
  voltage_max_pu: 1.05
  line_loading_limit_pct: 100
""",
        encoding="utf-8",
    )
    builder = ConfigBuilder(base, tmp_path / "chat_sessions", session_id="test_session")
    builder.set_mode("mock")
    builder.set_bus("bus_7")
    builder.set_load_scale(2.0)

    config_path = builder.write()
    config = _load_yaml(config_path)

    assert config_path == tmp_path / "chat_sessions" / "test_session" / "building_to_grid_chat.yaml"
    assert config["case"]["mode"] == "mock"
    assert config["building"]["bus_id"] == "bus_7"
    assert config["building"]["load_scale"] == 2.0
    assert config["opendss"]["target_bus"] == "bus_7"
    assert config["paths"]["output_root"].endswith("chat_sessions/test_session/run")
