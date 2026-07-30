from __future__ import annotations

import sys
import types
from pathlib import Path

from x2g_agent.tools.opendss_tool import run_opendssdirect_detailed


class _FakeDSS:
    def __init__(self) -> None:
        self.commands = []

        class Basic:
            def __init__(inner, outer):
                inner.outer = outer

            def ClearAll(inner):
                inner.outer.commands.append("ClearAll")

        class Text:
            def __init__(inner, outer):
                inner.outer = outer

            def Command(inner, command):
                inner.outer.commands.append(command)

        class Loads:
            @staticmethod
            def AllNames():
                return ["building_load"]

        class Solution:
            @staticmethod
            def Solve():
                return None

            @staticmethod
            def Converged():
                return True

        class Circuit:
            @staticmethod
            def AllBusNames():
                return ["bus_1", "bus_4"]

            @staticmethod
            def SetActiveBus(_bus):
                return None

            @staticmethod
            def TotalPower():
                return [-12.0, -3.0]

        class Bus:
            @staticmethod
            def puVmagAngle():
                return [1.0, 0.0, 0.99, -120.0, 0.99, 120.0]

        class Lines:
            @staticmethod
            def AllNames():
                return []

        self.Basic = Basic(self)
        self.Text = Text(self)
        self.Loads = Loads
        self.Solution = Solution
        self.Circuit = Circuit
        self.Bus = Bus
        self.Lines = Lines


def test_opendssdirect_clears_before_single_compile(monkeypatch, tmp_path: Path) -> None:
    fake = _FakeDSS()
    monkeypatch.setitem(sys.modules, "opendssdirect", fake)
    feeder = tmp_path / "feeder.dss"
    feeder.write_text("Clear\n", encoding="utf-8")

    run_opendssdirect_detailed(
        [
            {"timestamp": "h1", "building_kw": 10, "building_kvar": 2},
            {"timestamp": "h2", "building_kw": 11, "building_kvar": 2},
        ],
        {"master_file": str(feeder), "target_bus": "bus_4", "base_kv": 12.47},
    )

    compile_commands = [command for command in fake.commands if isinstance(command, str) and command.startswith("Compile")]
    assert fake.commands[0] == "ClearAll"
    assert len(compile_commands) == 1
    assert fake.commands.index("ClearAll") < fake.commands.index(compile_commands[0])
