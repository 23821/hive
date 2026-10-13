"""The ``hive`` package: Hive's primitives for projects built on it.

Every exported name resolves, importing stays light, and an agent loop hands its report to
``on_report`` without being a colony worker.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import AsyncIterator
from typing import Any

import pytest

import hive


@pytest.mark.parametrize("name", [n for n in hive.__all__ if n != "__version__"])
def test_every_primitive_resolves(name: str) -> None:
    assert getattr(hive, name) is not None


def test_all_lists_exactly_the_exports() -> None:
    assert set(hive.__all__) - {"__version__"} == set(hive._EXPORTS)


def test_the_version_is_the_installed_one() -> None:
    from importlib.metadata import version

    assert hive.__version__ == version("aden-hive")


def _loaded_after(statement: str) -> set[str]:
    code = f"import sys; {statement}; print(','.join(sorted(sys.modules)))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    return set(out.strip().split(","))


def test_importing_hive_loads_nothing_until_used() -> None:
    loaded = _loaded_after("import hive")
    assert "framework.agent_loop.agent_loop" not in loaded
    assert "litellm" not in loaded


def test_one_module_of_the_framework_does_not_load_the_rest() -> None:
    loaded = _loaded_after("import framework.host.event_bus")
    assert "framework.host.colony_runtime" not in loaded
    assert "framework.agent_loop.agent_loop" not in loaded


class _ReportingLLM(hive.LLMProvider):
    """Calls report_to_parent on its first turn, then only talks."""

    model = "scripted"

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        self.offered: list[str] = []
        self.turns = 0

    async def stream(self, messages: list[dict[str, Any]], system: str = "", tools: list | None = None, **kwargs: Any) -> AsyncIterator:
        self.turns += 1
        if self.turns == 1:
            self.offered = [t.name for t in tools or []]
            yield hive.ToolCallEvent(tool_use_id="r1", tool_name="report_to_parent", tool_input=self.report)
            yield hive.FinishEvent(stop_reason="tool_calls", input_tokens=10, output_tokens=5, model="scripted")
        else:
            yield hive.TextDeltaEvent(content="Done.", snapshot="Done.")
            yield hive.FinishEvent(stop_reason="stop", input_tokens=10, output_tokens=5, model="scripted")

    def complete(self, messages: list[dict[str, Any]], system: str = "", **kwargs: Any) -> Any:
        return hive.LLMResponse(content="", model="scripted", stop_reason="stop")


@pytest.mark.asyncio
async def test_on_report_receives_the_report_without_a_worker_stream() -> None:
    llm = _ReportingLLM({"status": "success", "summary": "Counted the sheep.", "data": {"sheep": 12}})
    reports: list[hive.AgentReport] = []
    spec = hive.AgentSpec(id="counter", name="Counter", description="Counts", system_prompt="Count the sheep, then report.")
    ctx = hive.AgentContext(runtime=None, agent_id="counter", agent_spec=spec, llm=llm, stream_id="game")
    loop = hive.AgentLoop(config=hive.LoopConfig(max_iterations=3), on_report=reports.append)

    result = await loop.execute(ctx)

    assert "report_to_parent" in llm.offered and "escalate" not in llm.offered
    assert reports == [hive.AgentReport(status="success", summary="Counted the sheep.", data={"sheep": 12})]
    assert result.success is True


@pytest.mark.asyncio
async def test_without_on_report_only_a_worker_stream_may_report() -> None:
    llm = _ReportingLLM({"status": "success", "summary": "x", "data": {}})
    spec = hive.AgentSpec(id="a", name="A", description="A", system_prompt="Say hello.")
    ctx = hive.AgentContext(runtime=None, agent_id="a", agent_spec=spec, llm=llm, stream_id="judge")
    await hive.AgentLoop(config=hive.LoopConfig(max_iterations=1)).execute(ctx)
    assert "report_to_parent" not in llm.offered
