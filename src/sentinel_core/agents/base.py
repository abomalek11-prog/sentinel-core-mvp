"""Abstract base class for all Sentinel agents."""
from __future__ import annotations

import abc

from sentinel_core.agents.state import AgentState
from sentinel_core.utils.logging import get_logger


class BaseAgent(abc.ABC):
    """Stateless abstract agent.

    Every concrete agent must inherit from BaseAgent and implement execute().
    """

    def __init__(self) -> None:
        self.log = get_logger(self.__class__.__qualname__)

    @abc.abstractmethod
    def execute(self, state: AgentState) -> AgentState:
        """Process the pipeline state and return an updated copy.

        Args:
            state: Current pipeline state.

        Returns:
            New state with this agent fields populated.
        """
        ...

    def safe_execute(self, state: AgentState) -> AgentState:
        """Wrap execute() with top-level error handling.

        Args:
            state: Current pipeline state.

        Returns:
            State with error field set on unhandled failure.
        """
        try:
            return self.execute(state)
        except Exception:
            self.log.error("agent_unhandled_error", exc_info=True)
            return {
                **state,
                "error": f"{self.__class__.__qualname__} failed unexpectedly",
            }
