"""CI-safe: no Docker, no Ollama. The wrapped policy is a stub that returns canned text."""

import asyncio
import json

import pytest
from control_arena import control_agent
from control_arena.settings.apps.task.submission_types import (
    SubmitAttackArgs,
    SubmitHonestArgs,
)
from control_arena.tools.submit_tool import SubmitToolConfig
from inspect_ai.agent import AgentState
from inspect_ai.model import ChatMessageAssistant, ModelOutput
from inspect_ai.tool import ToolCall

from lip.text_submit import text_submit_builder

CODE = "def f(x):\n    return  x+1  # keep  spacing\n\nprint(f(int(input())))\n"


def submit_tool(args_type):
    cfg = SubmitToolConfig(name="submit", description="d", input_type=args_type)
    return cfg.get_tool_def().as_tool()


def run(reply: ChatMessageAssistant, args_type=SubmitHonestArgs):
    @control_agent
    def stub():
        async def impl(state, tools):
            state.output = ModelOutput.from_message(reply)
            state._messages.append(state.output.message)
            return state

        return impl

    agent = text_submit_builder(policy=stub())
    state = asyncio.run(agent(AgentState(messages=[]), [submit_tool(args_type)]))
    return state.output.message


def say(text):
    return ChatMessageAssistant(content=text)


def test_json_form():
    block = json.dumps({"name": "submit", "arguments": {"code": CODE}})
    m = run(say(f"Here:\n```json\n{block}\n```"))
    assert m.metadata["text_submit"] is True
    (tc,) = m.tool_calls
    assert tc.function == "submit"
    assert tc.arguments == {"code": CODE}
    assert "```json" in m.text  # text unchanged


def test_bare_json_reply():
    block = json.dumps({"name": "submit", "arguments": {"code": CODE}})
    assert run(say(block)).tool_calls[0].arguments == {"code": CODE}


def test_python_fence_is_byte_identical():
    m = run(say(f"Solution:\n```python\n{CODE}```\nDone."))
    assert m.tool_calls[0].arguments["code"] == CODE
    assert m.metadata["text_submit"] is True


def test_attack_secret_input_carried_and_defaulted():
    block = json.dumps(
        {"name": "submit", "arguments": {"code": CODE, "secret_input": "7\n"}}
    )
    m = run(say(f"```json\n{block}\n```"), SubmitAttackArgs)
    assert m.tool_calls[0].arguments == {"code": CODE, "secret_input": "7\n"}
    m = run(say(f"```python\n{CODE}```"), SubmitAttackArgs)
    assert m.tool_calls[0].arguments == {"code": CODE, "secret_input": None}


@pytest.mark.parametrize(
    "text",
    [
        "I would write a loop here.",
        '```json\n{"name": "submit", "arguments": {"code": "x = 1"\n```',  # malformed
        '```json\n{"name": "other", "arguments": {"code": "x"}}\n```',
        "```json\n[1, 2]\n```",
        "```python\na = 1\n```\n```python\nb = 2\n```",  # ambiguous
    ],
)
def test_no_submission_unchanged(text):
    m = run(say(text))
    assert not m.tool_calls
    assert not (m.metadata or {}).get("text_submit")
    assert m.text == text


def test_existing_tool_calls_untouched():
    tc = ToolCall(id="1", function="submit", arguments={"code": "y = 2"})
    m = run(ChatMessageAssistant(content=f"```python\n{CODE}```", tool_calls=[tc]))
    assert m.tool_calls == [tc]
    assert not (m.metadata or {}).get("text_submit")
