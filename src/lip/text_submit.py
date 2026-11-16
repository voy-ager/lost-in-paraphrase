"""Turn a plain-text submission into a real `submit` tool call.

Small local models (qwen2.5-coder 1.5b/3b via Ollama) often write the submit call as text
instead of emitting a structured tool call. This wraps a policy: if the reply has no tool
calls, accept either a JSON block (fenced, or the whole reply) {"name": "submit", "arguments": {...}} or a single
fenced python block (taken as `code`). Values are used exactly as written; only the fence
markers are removed. Parsed calls get message metadata text_submit=True.
"""

import json
import re

from control_arena import control_agent
from control_arena._control_agent import ControlAgent
from control_arena.policy import untrusted_policy_builder
from inspect_ai.agent import Agent, AgentState
from inspect_ai.tool import Tool, ToolCall, ToolDef
from pydantic import Field

SUBMIT = "submit"
FENCE = re.compile(r"```[ \t]*([\w+-]*)[ \t]*\r?\n(.*?)```", re.DOTALL)


def extract_args(text: str, params: set[str]) -> dict | None:
    """Submit arguments found in `text`, or None. `params` = the submit tool's argument names."""
    fences = FENCE.findall(text)
    for body in [b for _, b in fences] + [
        text.strip()
    ]:  # fenced block or the bare reply
        try:
            obj = json.loads(body)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        args = obj.get("arguments")
        if (
            obj.get("name") == SUBMIT
            and isinstance(args, dict)
            and isinstance(args.get("code"), str)
        ):
            return {
                k: args.get(k) for k in params
            }  # missing optional args (secret_input) -> None
    py = [body for lang, body in fences if lang.lower() in ("python", "py")]
    if len(py) == 1:
        return {k: (py[0] if k == "code" else None) for k in params}
    return None


@control_agent
def text_submit_builder(
    policy: ControlAgent = Field(default_factory=untrusted_policy_builder),  # noqa: B008
) -> Agent:
    """Wrap `policy`; see module docstring."""

    async def impl(state: AgentState, tools: list[Tool]) -> AgentState:
        state = await policy(state, tools)
        msg = state.output.message
        if msg.tool_calls:
            return state
        submit = next((t for t in tools if ToolDef(t).name == SUBMIT), None)
        if submit is None:
            return state
        args = extract_args(msg.text, set(ToolDef(submit).parameters.properties))
        if args is not None:
            msg.tool_calls = [
                ToolCall(id="text_submit_0", function=SUBMIT, arguments=args)
            ]
            msg.metadata = {**(msg.metadata or {}), "text_submit": True}
        return state

    return impl
