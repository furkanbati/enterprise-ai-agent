import json
from types import SimpleNamespace

import anthropic
import httpx2
import openai
import pytest

from app.agent import Agent
from app.executor import Executor
from app.generator import Generator
from app.models import ChatToolCall
from app.providers.anthropic import (
    FALLBACK_BETA,
    REFUSAL_ANSWER,
    AnthropicProvider,
)
from app.providers.openai import OpenAIProvider
from app.tool_registry import ToolRegistry
from tools.calculator import CalculatorTool


TOOLS = ToolRegistry([CalculatorTool()]).tool_schemas()


class Recorder:
    """A fake SDK method that returns scripted responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(json.loads(json.dumps(kwargs, default=vars)))
        response = self.responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response


# --- OpenAI -----------------------------------------------------------------


def openai_response(content=None, tool_calls=()):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=[
                        SimpleNamespace(
                            id=call_id,
                            function=SimpleNamespace(
                                name=name,
                                arguments=json.dumps(arguments),
                            ),
                        )
                        for call_id, name, arguments in tool_calls
                    ]
                    or None,
                )
            )
        ]
    )


def openai_provider(responses):
    create = Recorder(responses)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )

    return OpenAIProvider(model="gpt-test", timeout=None, client=client), create


def test_openai_parses_tool_calls_with_ids():
    provider, _ = openai_provider(
        [openai_response(tool_calls=[("call_1", "calculator", {"expression": "6 * 7"})])]
    )

    message = provider.chat([{"role": "user", "content": "6 * 7?"}], tools=TOOLS)

    assert message.tool_calls == [
        ChatToolCall(
            name="calculator",
            arguments={"expression": "6 * 7"},
            id="call_1",
        )
    ]


def test_openai_converts_tool_turns_and_omits_withdrawn_tools():
    provider, create = openai_provider([openai_response(content="42")])
    messages = [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "6 * 7?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "calculator",
                        "arguments": {"expression": "6 * 7"},
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_name": "calculator",
            "tool_call_id": "call_1",
            "content": "42",
        },
    ]

    provider.chat(messages, tools=None)

    request = create.calls[0]
    assert "tools" not in request
    assert request["messages"][2] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "calculator",
                    "arguments": '{"expression": "6 * 7"}',
                },
            }
        ],
    }
    assert request["messages"][3] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "42",
    }


def test_openai_rejects_empty_responses():
    provider, _ = openai_provider([openai_response(content="")])

    with pytest.raises(ValueError, match="empty response"):
        provider.chat([])


def _http(status):
    request = httpx2.Request("POST", "https://api.test")
    return httpx2.Response(status, request=request)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (openai.APITimeoutError(request=_http(200).request), "timeout"),
        (
            openai.APIConnectionError(request=_http(200).request),
            "connection failure",
        ),
        (
            openai.RateLimitError("slow down", response=_http(429), body=None),
            "rate limit",
        ),
        (
            openai.InternalServerError("boom", response=_http(500), body=None),
            "server error",
        ),
        (
            openai.BadRequestError("bad", response=_http(400), body=None),
            None,
        ),
        (ValueError("bad response"), None),
    ],
)
def test_openai_retry_reasons(error, reason):
    provider, _ = openai_provider([])

    assert provider.retry_reason(error) == reason


def test_generator_retries_openai_rate_limits():
    provider, create = openai_provider(
        [
            openai.RateLimitError("slow down", response=_http(429), body=None),
            openai_response(content="ok"),
        ]
    )

    message = Generator(provider, max_retries=1, retry_base_delay=0).chat([])

    assert message.content == "ok"
    assert len(create.calls) == 2


# --- Anthropic --------------------------------------------------------------


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(call_id, name, arguments):
    return SimpleNamespace(type="tool_use", id=call_id, name=name, input=arguments)


def anthropic_response(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def anthropic_provider(responses, model="claude-haiku-5-5"):
    create = Recorder(responses)
    client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
    )

    return AnthropicProvider(model=model, timeout=None, client=client), create


def test_anthropic_sends_system_and_tool_schemas():
    provider, create = anthropic_provider([anthropic_response(text_block("Hi"))])

    message = provider.chat(
        [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "Hello"},
        ],
        tools=TOOLS,
    )

    request = create.calls[0]
    assert message.content == "Hi"
    assert request["system"] == "rules"
    assert request["messages"] == [{"role": "user", "content": "Hello"}]
    assert request["tools"][0]["name"] == "calculator"
    assert request["tools"][0]["input_schema"] == TOOLS[0]["function"]["parameters"]
    assert "tool_choice" not in request
    assert "fallbacks" not in request


def test_anthropic_enables_refusal_fallbacks_on_supported_models():
    provider, create = anthropic_provider(
        [anthropic_response(text_block("Hi"))],
        model="claude-opus-5-5",
    )

    provider.chat([{"role": "user", "content": "Hello"}])

    assert create.calls[0]["betas"] == [FALLBACK_BETA]
    assert create.calls[0]["fallbacks"] == "default"


def test_anthropic_keeps_response_content_for_the_next_turn():
    thinking = SimpleNamespace(type="thinking", thinking="", signature="sig")
    tool_use = tool_use_block("toolu_1", "calculator", {"expression": "6 * 7"})
    provider, _ = anthropic_provider(
        [anthropic_response(thinking, tool_use, stop_reason="tool_use")]
    )

    message = provider.chat([{"role": "user", "content": "6 * 7?"}], tools=TOOLS)

    assert message.tool_calls == [
        ChatToolCall(
            name="calculator",
            arguments={"expression": "6 * 7"},
            id="toolu_1",
        )
    ]
    assert message.provider_content == [thinking, tool_use]


def test_anthropic_returns_a_message_for_refusals():
    provider, _ = anthropic_provider(
        [anthropic_response(stop_reason="refusal")]
    )

    message = provider.chat([{"role": "user", "content": "..."}])

    assert message.content == REFUSAL_ANSWER


def test_agent_round_trip_with_anthropic_messages():
    """Tool results share one user turn and are matched to tool_use IDs."""

    provider, create = anthropic_provider(
        [
            anthropic_response(
                text_block("Let me calculate."),
                tool_use_block("toolu_1", "calculator", {"expression": "6 * 7"}),
                tool_use_block("toolu_2", "calculator", {"expression": "2 ** 10"}),
                stop_reason="tool_use",
            ),
            anthropic_response(text_block("42 and 1024.")),
        ]
    )
    registry = ToolRegistry([CalculatorTool()])
    agent = Agent(
        generator=Generator(provider, max_retries=0),
        executor=Executor(registry, timeout=1.0, max_retries=0),
        registry=registry,
    )

    result = agent.run("What are 6 * 7 and 2 ** 10?")

    assert result.answer == "42 and 1024."
    assert [step.result for step in result.steps] == [42, 1024]

    second = create.calls[1]["messages"]
    assert second[0] == {"role": "user", "content": "What are 6 * 7 and 2 ** 10?"}
    assert second[1]["role"] == "assistant"
    assert [block["type"] for block in second[1]["content"]] == [
        "text",
        "tool_use",
        "tool_use",
    ]
    assert second[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "42"},
            {"type": "tool_result", "tool_use_id": "toolu_2", "content": "1024"},
        ],
    }


def test_anthropic_declares_tools_without_calls_when_tools_are_withdrawn():
    provider, create = anthropic_provider([anthropic_response(text_block("Too big."))])
    messages = [
        {"role": "user", "content": "2 ** 5000000?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "toolu_1",
                    "function": {
                        "name": "calculator",
                        "arguments": {"expression": "2 ** 5000000"},
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_name": "calculator",
            "tool_call_id": "toolu_1",
            "content": "The tool rejected this request: too large",
        },
        {"role": "user", "content": "Answer now."},
    ]

    provider.chat(messages, tools=None)

    request = create.calls[0]
    assert request["tool_choice"] == {"type": "none"}
    assert [tool["name"] for tool in request["tools"]] == ["calculator"]
    assert request["messages"][1]["content"] == [
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "calculator",
            "input": {"expression": "2 ** 5000000"},
        }
    ]
    assert request["messages"][2]["content"][-1] == {
        "type": "text",
        "text": "Answer now.",
    }


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (
            anthropic.APITimeoutError(request=_http(200).request),
            "timeout",
        ),
        (
            anthropic.APIConnectionError(request=_http(200).request),
            "connection failure",
        ),
        (
            anthropic.RateLimitError(
                "slow down", response=_http(429), body=None
            ),
            "rate limit",
        ),
        (
            anthropic.InternalServerError(
                "overloaded", response=_http(529), body=None
            ),
            "server error",
        ),
        (
            anthropic.NotFoundError(
                "no model", response=_http(404), body=None
            ),
            None,
        ),
    ],
)
def test_anthropic_retry_reasons(error, reason):
    provider, _ = anthropic_provider([])

    assert provider.retry_reason(error) == reason
