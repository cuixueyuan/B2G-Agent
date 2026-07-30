from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


WorkflowState = dict[str, Any]


class Agent(ABC):
    """Base class for stateful workflow agents."""

    name: str

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__

    @abstractmethod
    def run(self, state: WorkflowState) -> WorkflowState:
        """Run the agent and return the updated workflow state."""
