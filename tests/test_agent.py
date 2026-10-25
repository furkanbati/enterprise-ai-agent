import copy
from typing import Any

import pytest

from app.agent import (
    FALLBACK_ANSWER,
    MAX_PROMPT_VALUE_CHARS,
    STEP_LIMIT_PROMPT,
    Agent,
    format_for_prompt,
)
from app.executor import Executor
from app.models import AgentStep, ChatMessage, ChatToolCall
from app.tool_registry import ToolRegistry
from tools.base import Tool
from tools.calculator import CalculatorTool


class FixedDateTool(Tool):
    name = "datetime"
    description = "Returns the current date and time."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict[str, Any]) -> str:
        return "2026-12-21T12:00:00+00:00"


class TextTool(Tool):
    name = "text"
    description = "Returns a long text."
    parameters = {"type": "object", "properties": {}}

    def execute(self, arguments: dict[str, Any]) -> str:
        return "x" * 10_000


class ScriptedGenerator:
    """Returns pre-defined assistant messages and records every chat call."""

    def __init__(self, messages: list[ChatMessage]):
        self.messages = list(messages)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, tools=None):
        self.calls.append(
            {
                "messages": copy.deepcopy(messages),
                "tools": tools,
            }
        )

        return self.messages.pop(0)


def answer(text: str) -> ChatMessage:
    return ChatMessage(content=text)


def call(name: str, **arguments) -> ChatToolCall:
    return ChatToolCall(name=name, arguments=arguments)


def calls(*tool_calls: ChatToolCall) -> ChatMessage:
    return ChatMessage(content="", tool_calls=list(tool_calls))


def make_agent(messages, max_steps=5, tools=None):
    registry = ToolRegistry(
        tools or [CalculatorTool(), FixedDateTool()]
    )
    generator = ScriptedGenerator(messages)
    agent = Agent(
        generator=generator,
        executor=Executor(registry, timeout=1.0, max_retries=0),
        registry=registry,
        max_steps=max_steps,
    )

    return agent, generator


def tool_messages(chat_call: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        message
        for message in chat_call["messages"]
        if message["role"] == "tool"
    ]


def test_answers_directly_without_tools():
    agent, generator = make_agent([answer("Merhaba!")])

    result = agent.run("Say hello in Turkish.")

    assert result.answer == "Merhaba!"
    assert result.steps == []
    assert result.tool is None
    assert result.error is None

    first_call = generator.calls[0]
    assert first_call["messages"][1] == {
        "role": "user",
        "content": "Say hello in Turkish.",
    }
    assert [tool["function"]["name"] for tool in first_call["tools"]] == [
        "calculator",
        "datetime",
    ]


def test_runs_a_tool_and_returns_its_result_to_the_model():
    agent, generator = make_agent(
        [
            calls(call("calculator", expression="6 * 7")),
            answer("The answer is 42."),
        ]
    )

    result = agent.run("What is 6 * 7?")

    assert result.answer == "The answer is 42."
    assert result.steps == [
        AgentStep(
            tool="calculator",
            arguments={"expression": "6 * 7"},
            success=True,
            result=42,
        )
    ]
    assert result.tool == "calculator"
    assert result.arguments == {"expression": "6 * 7"}
    assert result.tool_result == 42

    second_call = generator.calls[1]
    assert second_call["messages"][2] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "function": {
                    "name": "calculator",
                    "arguments": {"expression": "6 * 7"},
                }
            }
        ],
    }
    assert tool_messages(second_call) == [
        {"role": "tool", "tool_name": "calculator", "content": "42"},
    ]


def test_chains_tool_calls_across_steps():
    agent, generator = make_agent(
        [
            calls(call("datetime")),
            calls(call("calculator", expression="(31 - 21) * 24")),
            answer("There are 240 hours left in December."),
        ]
    )

    result = agent.run("How many hours are left in December?")

    assert [step.tool for step in result.steps] == ["datetime", "calculator"]
    assert result.steps[1].result == 240
    assert result.tool == "calculator"

    # The second decision is made with the first tool result available.
    assert tool_messages(generator.calls[1])[0]["content"] == (
        "2026-12-21T12:00:00+00:00"
    )


def test_runs_multiple_tool_calls_from_one_message_in_order():
    agent, generator = make_agent(
        [
            calls(
                call("calculator", expression="2 + 2"),
                call("calculator", expression="3 * 3"),
            ),
            answer("4 and 9."),
        ]
    )

    result = agent.run("What are 2 + 2 and 3 * 3?")

    assert [step.result for step in result.steps] == [4, 9]
    assert [m["content"] for m in tool_messages(generator.calls[1])] == [
        "4",
        "9",
    ]


def test_feeds_tool_errors_back_so_the_model_can_correct_them():
    agent, generator = make_agent(
        [
            calls(call("calculator", expression="2 ^ 10")),
            calls(call("calculator", expression="2 ** 10")),
            answer("2 to the power of 10 is 1024."),
        ]
    )

    result = agent.run("What is 2^10?")

    assert [step.success for step in result.steps] == [False, True]
    assert result.tool_result == 1024
    assert result.error is None

    error_message = tool_messages(generator.calls[1])[0]["content"]
    assert error_message.startswith("Error: Unsupported expression")
    # Tools stay available so the model can retry.
    assert generator.calls[1]["tools"] is not None


def test_feeds_back_unknown_tool_errors():
    agent, generator = make_agent(
        [
            calls(call("weather", city="Istanbul")),
            answer("I cannot check the weather."),
        ]
    )

    result = agent.run("What is the weather in Istanbul?")

    assert result.steps[0].success is False
    assert result.error == "Unknown tool: weather"
    assert tool_messages(generator.calls[1])[0]["content"] == (
        "Error: Unknown tool: weather"
    )


def test_withdraws_tools_after_a_rejected_request():
    agent, generator = make_agent(
        [
            calls(call("calculator", expression="2 ** 5000000")),
            answer("That result is too large to calculate."),
        ]
    )

    result = agent.run("What is 2 to the power of 5000000?")

    assert result.answer == "That result is too large to calculate."
    assert result.error == "Result exceeds 1000 digits."
    assert result.tool_result is None
    assert result.steps[0].rejected is True

    final_call = generator.calls[1]
    assert final_call["tools"] is None
    assert tool_messages(final_call)[0]["content"] == (
        "The tool rejected this request: Result exceeds 1000 digits."
    )


def test_does_not_execute_tool_calls_after_tools_are_withdrawn():
    agent, generator = make_agent(
        [
            calls(call("calculator", expression="2 ** 5000000")),
            # The model ignores the withdrawal and tries a smaller value.
            calls(call("calculator", expression="2 ** 10")),
        ]
    )

    result = agent.run("What is 2 to the power of 5000000?")

    assert result.answer == FALLBACK_ANSWER
    assert len(result.steps) == 1
    assert len(generator.calls) == 2


def test_stops_calling_tools_at_the_step_limit():
    agent, generator = make_agent(
        [
            calls(call("calculator", expression="1 + 1")),
            calls(call("calculator", expression="2 + 2")),
            answer("Done."),
        ],
        max_steps=2,
    )

    result = agent.run("Keep calculating.")

    assert result.answer == "Done."
    assert len(result.steps) == 2

    final_call = generator.calls[2]
    assert final_call["tools"] is None
    assert final_call["messages"][-1] == {
        "role": "user",
        "content": STEP_LIMIT_PROMPT,
    }


def test_skips_tool_calls_beyond_the_step_limit_in_one_message():
    agent, generator = make_agent(
        [
            calls(
                call("calculator", expression="1 + 1"),
                call("calculator", expression="2 + 2"),
                call("calculator", expression="3 + 3"),
            ),
            answer("Partial results."),
        ],
        max_steps=2,
    )

    result = agent.run("Calculate three things.")

    assert [step.result for step in result.steps] == [2, 4]
    assert tool_messages(generator.calls[1])[-1]["content"] == (
        "Not executed: the tool call limit was reached."
    )


def test_truncates_large_tool_results_in_the_conversation():
    agent, generator = make_agent(
        [calls(call("text")), answer("Long text.")],
        tools=[TextTool()],
    )

    result = agent.run("Get the text.")

    assert result.tool_result == "x" * 10_000

    content = tool_messages(generator.calls[1])[0]["content"]
    assert content.endswith("[truncated: 10000 characters in total]")
    assert len(content) < 10_000


def test_propagates_generator_failures():
    class FailingGenerator:
        def chat(self, messages, tools=None):
            raise ConnectionError("Ollama is down")

    registry = ToolRegistry([CalculatorTool()])
    agent = Agent(
        generator=FailingGenerator(),
        executor=Executor(registry),
        registry=registry,
    )

    with pytest.raises(ConnectionError):
        agent.run("What is 2 + 2?")


def test_format_for_prompt_handles_values():
    assert format_for_prompt(42) == "42"
    assert format_for_prompt(10**5000) == "[value too large to display]"

    truncated = format_for_prompt("y" * (MAX_PROMPT_VALUE_CHARS + 1))
    assert truncated.startswith("y" * MAX_PROMPT_VALUE_CHARS)
    assert truncated.endswith(
        f"[truncated: {MAX_PROMPT_VALUE_CHARS + 1} characters in total]"
    )


def test_history_is_placed_between_the_system_prompt_and_the_question():
    agent, generator = make_agent([answer("CUS-1001 has two orders.")])
    history = [
        {"role": "user", "content": "Show me the orders of Elif."},
        {"role": "assistant", "content": "Which Elif do you mean?"},
    ]

    agent.run("Elif Yılmaz.", history=history)

    messages = generator.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1:] == [
        *history,
        {"role": "user", "content": "Elif Yılmaz."},
    ]
