from __future__ import annotations

import pytest

from x2g_agent.chat.intent_parser import Intent
from x2g_agent.chat.llm_intent_parser import (
    LLMIntentParser,
    LLMIntentValidationError,
    chat_action_to_intent,
    validate_chat_action,
    validate_chat_action_request,
)


def test_validate_llm_action_and_map_to_intent() -> None:
    action = validate_chat_action('{"action": "set_load_scale", "load_scale": 2.5}')
    intent = chat_action_to_intent(action)

    assert intent.name == "set_load_scale"
    assert intent.slots["load_scale"] == 2.5


def test_validate_llm_action_request_for_run_mock() -> None:
    request = validate_chat_action_request(
        '{"actions": [{"action": "set_mode", "mode": "mock"}, {"action": "run_workflow"}]}'
    )
    intents = [chat_action_to_intent(action) for action in request.actions]

    assert intents[0].name == "set_mode"
    assert intents[0].slots["mode"] == "mock"
    assert intents[1].name == "run_case"


def test_validate_llm_action_request_for_required_examples() -> None:
    examples = [
        ('{"actions":[{"action":"set_mode","mode":"real"},{"action":"run_workflow"}]}', ["set_mode", "run_case"]),
        ('{"actions":[{"action":"set_target_bus","bus_id":"bus_4"}]}', ["set_bus"]),
        ('{"actions":[{"action":"set_load_scale","load_scale":2.0}]}', ["set_load_scale"]),
        ('{"actions":[{"action":"summarize_results"}]}', ["summarize_results"]),
    ]
    for raw, names in examples:
        request = validate_chat_action_request(raw)
        assert [chat_action_to_intent(action).name for action in request.actions] == names


def test_reject_invalid_llm_action_extra_slot() -> None:
    with pytest.raises(LLMIntentValidationError):
        validate_chat_action('{"action": "run_workflow", "mode": "mock"}')


def test_reject_invalid_llm_json() -> None:
    with pytest.raises(LLMIntentValidationError):
        validate_chat_action("run the workflow")


def test_reject_invalid_llm_action_request_extra_slot() -> None:
    with pytest.raises(LLMIntentValidationError):
        validate_chat_action_request('{"actions": [{"action": "run_workflow", "mode": "mock"}]}')


def test_mocked_openai_client_response_returns_action_sequence(capsys) -> None:
    class Message:
        content = '{"actions":[{"action":"set_mode","mode":"mock"},{"action":"run_workflow"}]}'

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    class Completions:
        @staticmethod
        def create(**_kwargs):
            return Response()

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    parser = LLMIntentParser(client=Client(), model="test-model", debug=True)
    intents = parser.parse("run mock Building-to-Grid")

    assert [intent.name for intent in intents] == ["set_mode", "run_case"]
    assert intents[0].slots["mode"] == "mock"
    assert "Raw LLM response" in capsys.readouterr().out


def test_mocked_openai_client_validation_error_in_debug(capsys) -> None:
    class Message:
        content = '{"actions":[{"action":"run_workflow","mode":"mock"}]}'

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    class Completions:
        @staticmethod
        def create(**_kwargs):
            return Response()

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    parser = LLMIntentParser(client=Client(), model="test-model", debug=True)
    with pytest.raises(LLMIntentValidationError):
        parser.parse("run mock Building-to-Grid")

    output = capsys.readouterr().out
    assert "Raw LLM response" in output
    assert "LLM validation error" in output


def test_mocked_llm_parser_with_chat_agent(tmp_path, monkeypatch) -> None:
    from x2g_agent.chat.chat_agent import ChatAgent

    class FakeParser:
        def parse(self, _text):
            return [Intent("set_mode", {"mode": "mock"})]

    agent = ChatAgent(
        base_config_path="configs/building_to_grid.yaml",
        session_root=tmp_path / "chat_sessions",
        backend="openai",
        intent_parser=FakeParser(),
    )

    response, should_exit = agent.handle("please use the cheap dry-run mode")

    assert should_exit is False
    assert response == "Set Building-to-Grid mode to mock."


def test_chat_agent_executes_llm_action_sequence(tmp_path, monkeypatch) -> None:
    from x2g_agent.chat import chat_agent as chat_agent_module
    from x2g_agent.chat.chat_agent import ChatAgent

    class FakeParser:
        def parse(self, _text):
            return [Intent("set_mode", {"mode": "mock"}), Intent("run_case")]

    def fake_run(_config_path):
        return {
            "artifacts": {
                "building_load_csv": "building_load.csv",
                "power_flow_result_csv": "power_flow_results.csv",
                "risk_summary_csv": "risk_summary.csv",
                "markdown_report": "report.md",
            },
            "risk_summary": {
                "voltage_violations": 0,
                "minimum_voltage_pu": 0.98,
                "feeder_peak_kw": 123.0,
            },
        }

    monkeypatch.setattr(chat_agent_module, "run_building_to_grid", fake_run)
    agent = ChatAgent(
        base_config_path="configs/building_to_grid.yaml",
        session_root=tmp_path / "chat_sessions",
        backend="openai",
        intent_parser=FakeParser(),
    )

    response, should_exit = agent.handle("run mock Building-to-Grid")

    assert should_exit is False
    assert "Set Building-to-Grid mode to mock." in response
    assert "Building-to-Grid run completed." in response


def test_llm_validation_failure_does_not_execute(tmp_path) -> None:
    from x2g_agent.chat.chat_agent import ChatAgent

    class BadParser:
        def parse(self, _text):
            raise LLMIntentValidationError("bad json")

    agent = ChatAgent(
        base_config_path="configs/building_to_grid.yaml",
        session_root=tmp_path / "chat_sessions",
        backend="openai",
        intent_parser=BadParser(),
    )

    response, should_exit = agent.handle("do an impossible thing")

    assert should_exit is False
    assert "Please rephrase" in response
    assert agent.last_state is None
