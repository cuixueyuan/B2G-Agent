from __future__ import annotations

from pathlib import Path
from typing import Iterable

from x2g_agent.cases.building_to_grid.workflow import run_building_to_grid
from x2g_agent.chat.config_builder import ConfigBuilder
from x2g_agent.chat.intent_parser import Intent
from x2g_agent.chat.intent_parser import IntentParser
from x2g_agent.chat.llm_intent_parser import LLMIntentValidationError, LLMIntentParser
from x2g_agent.chat.result_summarizer import ResultSummarizer


class ChatAgent:
    """Rule-based terminal chat agent for Building-to-Grid runs."""

    def __init__(
        self,
        base_config_path: str | Path = "samples/single-building-to-grid/configs/building_to_grid.yaml",
        session_root: str | Path = "samples/single-building-to-grid/outputs/chat_sessions",
        backend: str = "rule",
        intent_parser: object | None = None,
        debug: bool = False,
    ) -> None:
        self.intent_parser = intent_parser or _build_intent_parser(backend, debug)
        self.backend = backend
        self.debug = debug
        self.config_builder = ConfigBuilder(base_config_path, session_root)
        self.summarizer = ResultSummarizer()
        self.last_state: dict | None = None
        self.config_path = self.config_builder.write()

    def handle(self, text: str) -> tuple[str, bool]:
        try:
            parsed = self.intent_parser.parse(text)
        except LLMIntentValidationError:
            return "I could not turn that into a valid X2G-Agent action. Please rephrase.", False
        intents = _normalize_intents(parsed)

        responses = []
        should_exit = False
        for intent in intents:
            response, should_exit = self._handle_intent(intent)
            if response:
                responses.append(response)
            if should_exit:
                break
        return "\n".join(responses), should_exit

    def _handle_intent(self, intent: Intent) -> tuple[str, bool]:
        if intent.name == "exit":
            return "Goodbye.", True
        if intent.name == "help":
            return _help_text(), False
        if intent.name == "set_mode":
            self.config_path = self.config_builder.apply_intent(intent.name, intent.slots)
            return f"Set Building-to-Grid mode to {intent.slots['mode']}.", False
        if intent.name == "set_bus":
            self.config_path = self.config_builder.apply_intent(intent.name, intent.slots)
            return f"Connected the building to {intent.slots['bus_id']}.", False
        if intent.name == "set_load_scale":
            self.config_path = self.config_builder.apply_intent(intent.name, intent.slots)
            return f"Set load scale to {intent.slots['load_scale']}.", False
        if intent.name == "run_case":
            mode = intent.slots.get("mode")
            if mode:
                self.config_path = self.config_builder.apply_intent("set_mode", {"mode": mode})
            self.last_state = run_building_to_grid(self.config_path)
            return self.summarizer.summarize_run(self.last_state), False
        if intent.name == "summarize_voltage_violations":
            return self.summarizer.summarize_voltage(self.last_state), False
        if intent.name == "summarize_results":
            if self.last_state is None:
                return "No run has completed yet. Try: run mock Building-to-Grid", False
            return self.summarizer.summarize_run(self.last_state), False
        if intent.name == "show_output_paths":
            return self.summarizer.output_paths(self.last_state), False

        return _help_text(), False


def _build_intent_parser(backend: str, debug: bool) -> object:
    if backend == "rule":
        return IntentParser()
    if backend == "openai":
        return LLMIntentParser(debug=debug)
    raise ValueError(f"Unsupported chat backend: {backend}")


def _normalize_intents(parsed: Intent | Iterable[Intent]) -> list[Intent]:
    if isinstance(parsed, Intent):
        return [parsed]
    return list(parsed)


def _help_text() -> str:
    return (
        "I can run mock or real Building-to-Grid, set the bus, set load scale, "
        "summarize voltage violations, show output paths, or exit."
    )
