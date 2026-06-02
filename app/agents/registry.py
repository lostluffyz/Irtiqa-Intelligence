from __future__ import annotations

from app.agents.base import BaseAgent
from app.core.errors import AgentError


class AgentRegistry:
    """Registry for agent class lookup by name.

    Follows the same structural pattern as ``WorkflowRegistry``.
    Each agent class must declare a ``name`` and ``version`` class
    attribute.  Registration rejects duplicates, empty names, and
    empty versions.
    """

    def __init__(self) -> None:
        self._agents: dict[str, type[BaseAgent]] = {}

    def register(self, agent: type[BaseAgent]) -> None:
        """Register an agent class.

        Validates that the class exposes a non-empty ``name`` and
        ``version`` string attribute, and that no other agent has
        already been registered under the same name.
        """
        name = getattr(agent, "name", None)
        if not name or not isinstance(name, str):
            raise AgentError(
                "Agent class must define a stable name.",
                details={"agent_class": agent.__name__},
            )

        version = getattr(agent, "version", None)
        if not version or not isinstance(version, str):
            raise AgentError(
                "Agent class must define a version.",
                details={"agent_class": agent.__name__, "agent_name": name},
            )

        if name in self._agents:
            raise AgentError(
                "Agent is already registered.",
                details={"agent_name": name},
            )

        self._agents[name] = agent

    def get(self, agent_name: str) -> type[BaseAgent]:
        """Resolve an agent class by name.

        Raises ``AgentError`` if no agent is registered under the
        given name.
        """
        agent = self._agents.get(agent_name)
        if agent is None:
            raise AgentError(
                "Agent is not registered.",
                details={"agent_name": agent_name},
            )
        return agent

    def names(self) -> tuple[str, ...]:
        """Return sorted tuple of registered agent names."""
        return tuple(sorted(self._agents))
