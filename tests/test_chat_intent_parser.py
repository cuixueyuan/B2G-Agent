from __future__ import annotations

from x2g_agent.chat.intent_parser import IntentParser


def test_parse_run_modes() -> None:
    parser = IntentParser()
    assert parser.parse("run mock Building-to-Grid").slots["mode"] == "mock"
    assert parser.parse("run real Building-to-Grid").slots["mode"] == "real"


def test_parse_bus_and_scale() -> None:
    parser = IntentParser()
    bus = parser.parse("connect the building to bus_4")
    scale = parser.parse("set load scale to 2.0")
    assert bus.name == "set_bus"
    assert bus.slots["bus_id"] == "bus_4"
    assert scale.name == "set_load_scale"
    assert scale.slots["load_scale"] == 2.0


def test_parse_summary_paths_and_exit() -> None:
    parser = IntentParser()
    assert parser.parse("summarize voltage violations").name == "summarize_voltage_violations"
    assert parser.parse("show output paths").name == "show_output_paths"
    assert parser.parse("exit").name == "exit"
