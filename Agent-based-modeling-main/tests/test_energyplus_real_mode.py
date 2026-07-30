from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from x2g_agent.tools.energyplus_tool import parse_eplusout_mtr, run_energyplus_or_mock


def test_real_mode_expands_env_and_parses_hourly_electricity(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "energyplus.exe"
    idf = tmp_path / "building.idf"
    epw = tmp_path / "weather.epw"
    for path in [executable, idf, epw]:
        path.write_text("", encoding="utf-8")
    monkeypatch.setenv("ENERGYPLUS_EXE", str(executable))
    monkeypatch.setenv("ENERGYPLUS_IDF", str(idf))
    monkeypatch.setenv("ENERGYPLUS_EPW", str(epw))

    def fake_run(command, check):
        assert check is True
        output_dir = Path(command[command.index("-d") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "eplusout.csv").write_text(
            "Date/Time,Electricity:Facility [J](Hourly)\n"
            " 01/01  01:00:00,3600000\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    rows = run_energyplus_or_mock(
        {
            "mode": "real",
            "executable": "${ENERGYPLUS_EXE}",
            "idf_path": "${ENERGYPLUS_IDF}",
            "epw_path": "${ENERGYPLUS_EPW}",
            "timestep_per_hour": 1,
        },
        tmp_path / "energyplus",
    )

    assert rows == [{"timestamp": "01/01 01:00:00", "electricity_kw": 1.0}]


def test_real_mode_reruns_with_temporary_idf_when_hourly_meter_missing(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "energyplus.exe"
    idf = tmp_path / "building.idf"
    epw = tmp_path / "weather.epw"
    executable.write_text("", encoding="utf-8")
    idf.write_text("Version,24.2;\n", encoding="utf-8")
    epw.write_text("", encoding="utf-8")
    calls = []

    def fake_run(command, check):
        calls.append(command)
        output_dir = Path(command[command.index("-d") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        if len(calls) == 1:
            (output_dir / "eplusout.csv").write_text("Date/Time,Other Meter [J](Hourly)\n1,2\n", encoding="utf-8")
        else:
            assert command[-1].endswith("_x2g_hourly_meter.idf")
            assert "Output:Meter,Electricity:Facility,hourly;" in Path(command[-1]).read_text(encoding="utf-8")
            (output_dir / "eplusout.csv").write_text(
                "Date/Time,Electricity:Facility [J](Hourly)\n"
                " 01/01  01:00:00,7200000\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    rows = run_energyplus_or_mock(
        {
            "mode": "real",
            "executable": str(executable),
            "idf_path": str(idf),
            "epw_path": str(epw),
        },
        tmp_path / "energyplus",
    )

    assert len(calls) == 2
    assert rows == [{"timestamp": "01/01 01:00:00", "electricity_kw": 2.0}]


def test_parse_eplusout_mtr_hourly_electricity_facility(tmp_path: Path) -> None:
    mtr = tmp_path / "eplusout.mtr"
    mtr.write_text(
        "\n".join(
            [
                "Program Version,EnergyPlus, Version 24.2",
                "2,8,Day of Simulation[],Month[],Day of Month[],DST Indicator[1=yes 0=no],Hour[],StartMinute[],EndMinute[],DayType",
                "101,1,Electricity:Facility [J](Hourly)",
                "102,1,Gas:Facility [J](Hourly)",
                "End of Data Dictionary",
                "2,1,1,1,0,1,0,60,Monday",
                "101,3600000",
                "2,1,1,1,0,2,0,60,Monday",
                "101,7200000",
            ]
        ),
        encoding="utf-8",
    )

    rows = parse_eplusout_mtr(mtr)

    assert rows == [
        {"timestamp": "01/01 01:00:00", "electricity_kw": 1.0},
        {"timestamp": "01/01 02:00:00", "electricity_kw": 2.0},
    ]


def test_parse_eplusout_mtr_reports_available_meter_names(tmp_path: Path) -> None:
    mtr = tmp_path / "eplusout.mtr"
    mtr.write_text(
        "\n".join(
            [
                "2,8,Day of Simulation[],Month[],Day of Month[],DST Indicator[1=yes 0=no],Hour[],StartMinute[],EndMinute[],DayType",
                "201,1,Electricity:Building [J](Hourly)",
                "202,1,Gas:Facility [J](Hourly)",
                "End of Data Dictionary",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Electricity:Building"):
        parse_eplusout_mtr(mtr)
