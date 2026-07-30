from __future__ import annotations

import json
import os
from typing import Any, Literal

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional fallback
    load_dotenv = None

from pydantic import BaseModel, Field, ValidationError

try:
    from pydantic import ConfigDict, model_validator

    _PYDANTIC_V2 = True
except ImportError:  # pragma: no cover - pydantic v1 compatibility
    from pydantic import root_validator

    _PYDANTIC_V2 = False

from x2g_agent.chat.intent_parser import Intent


AllowedAction = Literal[
    "set_mode",
    "set_target_bus",
    "set_load_scale",
    "run_workflow",
    "summarize_results",
    "show_outputs",
    "help",
    "exit",
]


class ChatAction(BaseModel):
    """Validated action returned by the OpenAI-backed intent parser."""

    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid")

    action: AllowedAction
    mode: Literal["mock", "real"] | None = None
    bus_id: str | None = None
    load_scale: float | None = Field(default=None, gt=0)

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def validate_required_slots(self) -> "ChatAction":
            _validate_action_slots(self.action, self.mode, self.bus_id, self.load_scale)
            return self

    else:

        class Config:
            extra = "forbid"

        @root_validator
        def validate_required_slots(cls, values):  # type: ignore[no-untyped-def]
            _validate_action_slots(
                values.get("action"),
                values.get("mode"),
                values.get("bus_id"),
                values.get("load_scale"),
            )
            return values


class ChatActionRequest(BaseModel):
    """Validated JSON envelope returned by the OpenAI-backed intent parser."""

    if _PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid")
    else:

        class Config:
            extra = "forbid"

    actions: list[ChatAction] = Field(min_length=1)


class LLMIntentValidationError(ValueError):
    """Raised when LLM output cannot be validated as an allowed chat action."""


class LLMIntentParser:
    """OpenAI-backed parser that converts natural language into validated actions."""

    def __init__(self, model: str | None = None, client: Any | None = None, debug: bool = False) -> None:
        _load_env()
        self.model = model or os.getenv("X2G_CHAT_MODEL", "gpt-4.1-mini")
        self.client = client or _build_openai_client()
        self.debug = debug

    def parse(self, text: str) -> list[Intent]:
        raw = self._request_json(text)
        if self.debug:
            print(f"[x2g-chat-debug] Raw LLM response: {raw}")
        try:
            request = validate_chat_action_request(raw)
        except LLMIntentValidationError as exc:
            if self.debug:
                print(f"[x2g-chat-debug] LLM validation error: {exc}")
            raise
        return [chat_action_to_intent(action) for action in request.actions]

    def _request_json(self, text: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": _system_prompt(),
                },
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMIntentValidationError("OpenAI returned an empty response.")
        return content


def validate_chat_action_request(raw: str | dict[str, Any]) -> ChatActionRequest:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise LLMIntentValidationError(f"LLM did not return valid JSON: {exc}") from exc
    try:
        return ChatActionRequest(**data)
    except ValidationError as exc:
        raise LLMIntentValidationError(f"LLM returned an invalid chat action request: {exc}") from exc


def validate_chat_action(raw: str | dict[str, Any]) -> ChatAction:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise LLMIntentValidationError(f"LLM did not return valid JSON: {exc}") from exc
    try:
        return ChatAction(**data)
    except ValidationError as exc:
        raise LLMIntentValidationError(f"LLM returned an invalid chat action: {exc}") from exc


def chat_action_to_intent(action: ChatAction) -> Intent:
    if action.action == "set_mode":
        return Intent("set_mode", {"mode": action.mode})
    if action.action == "set_target_bus":
        return Intent("set_bus", {"bus_id": action.bus_id})
    if action.action == "set_load_scale":
        return Intent("set_load_scale", {"load_scale": action.load_scale})
    if action.action == "run_workflow":
        return Intent("run_case")
    if action.action == "summarize_results":
        return Intent("summarize_results")
    if action.action == "show_outputs":
        return Intent("show_output_paths")
    if action.action == "help":
        return Intent("help")
    if action.action == "exit":
        return Intent("exit")
    raise LLMIntentValidationError(f"Unsupported action: {action.action}")


def _system_prompt() -> str:
    return """
You are the X2G-Agent Building-to-Grid intent parser.

Return JSON only.
No markdown.
No explanations.
No code fences.
No prose outside the JSON object.

The JSON object must exactly match this shape:
{
  "actions": [
    {"action": "set_mode", "mode": "mock"},
    {"action": "run_workflow"}
  ]
}

Allowed action objects:
{"action": "set_mode", "mode": "mock"} or {"action": "set_mode", "mode": "real"}
{"action": "set_target_bus", "bus_id": "bus_4"}
{"action": "set_load_scale", "load_scale": 2.0}
{"action": "run_workflow"}
{"action": "summarize_results"}
{"action": "show_outputs"}
{"action": "help"}
{"action": "exit"}

Required mappings:
Input: run mock Building-to-Grid
Output: {"actions":[{"action":"set_mode","mode":"mock"},{"action":"run_workflow"}]}

Input: run real Building-to-Grid
Output: {"actions":[{"action":"set_mode","mode":"real"},{"action":"run_workflow"}]}

Input: connect the building to bus_4
Output: {"actions":[{"action":"set_target_bus","bus_id":"bus_4"}]}

Input: set load scale to 2.0
Output: {"actions":[{"action":"set_load_scale","load_scale":2.0}]}

Input: summarize voltage violations
Output: {"actions":[{"action":"summarize_results"}]}
""".strip()


def _validate_action_slots(action: str | None, mode: str | None, bus_id: str | None, load_scale: float | None) -> None:
    if action == "set_mode" and mode is None:
        raise ValueError("set_mode requires mode.")
    if action != "set_mode" and mode is not None:
        raise ValueError("mode is only allowed with set_mode.")
    if action == "set_target_bus" and not bus_id:
        raise ValueError("set_target_bus requires bus_id.")
    if action != "set_target_bus" and bus_id is not None:
        raise ValueError("bus_id is only allowed with set_target_bus.")
    if action == "set_load_scale" and load_scale is None:
        raise ValueError("set_load_scale requires load_scale.")
    if action != "set_load_scale" and load_scale is not None:
        raise ValueError("load_scale is only allowed with set_load_scale.")


def _build_openai_client() -> Any:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --backend openai.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The OpenAI Python SDK is required for --backend openai. Install with `pip install openai`.") from exc
    return OpenAI(api_key=api_key)


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv()
