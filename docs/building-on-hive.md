# Building on Hive

Hive's primitives (the agent loop, model providers, tools, events and configuration) can be
used by your own project. Depend on the `aden-hive` package and import them from `hive`.

## Install

Hive isn't on PyPI yet, so depend on a tagged commit. With uv:

```toml
# pyproject.toml
[project]
dependencies = ["aden-hive[server]>=1.0.1,<2"]

[tool.uv.sources]
aden-hive = { git = "https://github.com/aden-hive/hive", tag = "v1.0.1", subdirectory = "core" }
```

With pip, use the equivalent direct reference:

```text
aden-hive[server] @ git+https://github.com/aden-hive/hive@v1.0.1#subdirectory=core
```

The base install brings only what the primitives need. The extras are:

| Extra | Adds | Needed for |
|---|---|---|
| `server` | aiohttp | `SSEResponse`, and serving your own pages |
| `tools` | `aden-tools`: Hive's built-in tools, with a browser, PDF and OCR libraries, and database and SaaS clients | colonies and their workers, credential tooling |

## Use

```python
from hive import AgentContext, AgentLoop, AgentReport, AgentSpec, LiteLLMProvider, LoopConfig, ToolResult, ToolUse

reports: list[AgentReport] = []


async def run_tool(call: ToolUse) -> ToolResult:
    return ToolResult(tool_use_id=call.id, content="It is raining.")


spec = AgentSpec(id="scout", name="Scout", description="Looks around", system_prompt="Look outside, then report.")
llm = LiteLLMProvider(model="anthropic/claude-sonnet-5-5")
ctx = AgentContext(runtime=None, agent_id="scout", agent_spec=spec, llm=llm, available_tools=[...])
loop = AgentLoop(tool_executor=run_tool, config=LoopConfig(max_iterations=4), on_report=reports.append)
result = await loop.execute(ctx)
```

- **`on_report`** gives the agent a `report_to_parent` tool and receives its `AgentReport`
  (`status`, `summary` and `data` following the spec's `report_schema`). The loop ends once
  the agent reports.
- **The user's Hive setup** is available: `HIVE_HOME`, `get_preferred_model()`, `get_api_key()`,
  `get_api_base()` and `RuntimeConfig` read the model and keys configured with the quickstart.
- **`import hive` is cheap.** Each name is imported when first used.
- **Stability:** names exported from `hive` follow semantic versioning from 1.0.1. Anything
  imported from `framework.*` is Hive's internals and may change in any release.
