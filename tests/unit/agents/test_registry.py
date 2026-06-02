from __future__ import annotations

from typing import Any

import pytest

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.agents.result import AgentResult
from app.core.errors import AgentError
from app.agents.registry import AgentRegistry


class RegisteredAgent(BaseAgent):
    name = "registered_agent"
    version = "1.0.0"

    async def _run(self, context: AgentContext) -> dict[str, Any]:
        return {"output_ids": {}, "summary": "ok", "stats": {}}


class AnotherAgent(BaseAgent):
    name = "another_agent"
    version = "2.0.0"

    async def _run(self, context: AgentContext) -> dict[str, Any]:
        return {"output_ids": {}, "summary": "ok", "stats": {}}


class NamelessAgent(BaseAgent):
    name = ""
    version = "1.0.0"

    async def _run(self, context: AgentContext) -> dict[str, Any]:
        return {"output_ids": {}, "summary": "ok", "stats": {}}


class VersionlessAgent(BaseAgent):
    name = "versionless"
    version = ""

    async def _run(self, context: AgentContext) -> dict[str, Any]:
        return {"output_ids": {}, "summary": "ok", "stats": {}}


def test_agent_registry_registers_and_resolves_agent() -> None:
    registry = AgentRegistry()
    registry.register(RegisteredAgent)

    assert registry.get("registered_agent") is RegisteredAgent
    assert registry.names() == ("registered_agent",)


def test_agent_registry_registers_multiple_agents() -> None:
    registry = AgentRegistry()
    registry.register(RegisteredAgent)
    registry.register(AnotherAgent)

    assert registry.names() == ("another_agent", "registered_agent")


def test_agent_registry_rejects_duplicate_names() -> None:
    registry = AgentRegistry()
    registry.register(RegisteredAgent)

    with pytest.raises(AgentError) as exc_info:
        registry.register(RegisteredAgent)

    assert exc_info.value.code == "irtiqa.agent_error"
    assert exc_info.value.details == {"agent_name": "registered_agent"}


def test_agent_registry_rejects_nameless_agents() -> None:
    registry = AgentRegistry()

    with pytest.raises(AgentError) as exc_info:
        registry.register(NamelessAgent)

    assert "stable name" in exc_info.value.message


def test_agent_registry_rejects_versionless_agents() -> None:
    registry = AgentRegistry()

    with pytest.raises(AgentError) as exc_info:
        registry.register(VersionlessAgent)

    assert "version" in exc_info.value.message


def test_agent_registry_rejects_unknown_agent_lookup() -> None:
    registry = AgentRegistry()

    with pytest.raises(AgentError) as exc_info:
        registry.get("missing")

    assert exc_info.value.details == {"agent_name": "missing"}


def test_agent_registry_names_returns_empty_tuple_when_empty() -> None:
    registry = AgentRegistry()
    assert registry.names() == ()
