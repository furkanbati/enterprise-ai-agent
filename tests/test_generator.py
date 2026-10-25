import httpx
import pytest
from ollama import ResponseError

import app.providers.ollama as ollama_module
from app.config import GENERATOR_TIMEOUT
from app.generator import (
    Generator,
    GeneratorResponseError,
    GeneratorUnavailableError,
)
from app.models import ChatMessage, ChatToolCall
from app.providers.ollama import OllamaProvider


class FakeClient:
    def __init__(self, responses=None, errors=None, show_error=None):
        self.responses = responses or []
        self.errors = errors or []
        self.show_error = show_error
        self.calls = []
        self.call_count = 0

    def chat(self, **kwargs):
        self.calls.append(kwargs)

        if self.call_count < len(self.errors):
            error = self.errors[self.call_count]
            self.call_count += 1
            raise error

        response = self.responses[
            self.call_count - len(self.errors)
        ]

        self.call_count += 1
        return response

    def show(self, model):
        if self.show_error:
            raise self.show_error

        return {"model": model}


def create_generator(client):
    provider = OllamaProvider(
        model="fake-model",
        host="http://fake",
        timeout=None,
    )
    provider.client = client

    return Generator(
        provider=provider,
        max_retries=2,
        retry_base_delay=0,
    )


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluates a mathematical expression.",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]


def chat_response(content="", tool_calls=None):
    return {
        "message": {
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
        }
    }


def test_chat_sends_messages_and_tools():
    client = FakeClient(responses=[chat_response(content="Hello!")])
    generator = create_generator(client)
    messages = [{"role": "user", "content": "Hi"}]

    message = generator.chat(messages, tools=TOOLS)

    assert message == ChatMessage(content="Hello!", tool_calls=[])
    assert client.calls[0] == {
        "model": "fake-model",
        "messages": messages,
        "tools": TOOLS,
    }


def test_chat_sends_no_tools_when_tools_are_withdrawn():
    client = FakeClient(responses=[chat_response(content="Done.")])

    create_generator(client).chat([], tools=None)

    assert client.calls[0]["tools"] is None


def test_chat_drops_tool_call_ids_for_ollama():
    client = FakeClient(responses=[chat_response(content="42")])
    messages = [
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
            "provider_content": ["opaque"],
        },
        {
            "role": "tool",
            "tool_name": "calculator",
            "tool_call_id": "call_1",
            "content": "42",
        },
    ]

    create_generator(client).chat(messages)

    assert client.calls[0]["messages"] == [
        {
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
        },
        {"role": "tool", "tool_name": "calculator", "content": "42"},
    ]


def test_chat_parses_tool_calls():
    client = FakeClient(
        responses=[
            chat_response(
                tool_calls=[
                    {
                        "function": {
                            "name": "calculator",
                            "arguments": {"expression": "2 + 2"},
                        }
                    },
                    {
                        "function": {
                            "name": "datetime",
                            "arguments": '{"zone": "UTC"}',
                        }
                    },
                ]
            )
        ]
    )

    message = create_generator(client).chat([], tools=TOOLS)

    assert message.content == ""
    assert message.tool_calls == [
        ChatToolCall(name="calculator", arguments={"expression": "2 + 2"}),
        ChatToolCall(name="datetime", arguments={"zone": "UTC"}),
    ]


def test_chat_parses_ollama_message_objects():
    from ollama import ChatResponse, Message

    response = ChatResponse(
        message=Message(
            role="assistant",
            content="",
            tool_calls=[
                Message.ToolCall(
                    function=Message.ToolCall.Function(
                        name="calculator",
                        arguments={"expression": "6 * 7"},
                    )
                )
            ],
        )
    )

    message = create_generator(FakeClient(responses=[response])).chat([])

    assert message.tool_calls == [
        ChatToolCall(name="calculator", arguments={"expression": "6 * 7"}),
    ]


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (chat_response(content="  "), "empty response"),
        (chat_response(content=None), "empty response"),
        (chat_response(content=["text"]), "must be a string"),
        ({}, "missing message"),
        (None, "missing message"),
        (
            chat_response(tool_calls=[{"function": {"arguments": {}}}]),
            "without a name",
        ),
        (
            chat_response(
                tool_calls=[
                    {"function": {"name": "calculator", "arguments": "{"}}
                ]
            ),
            "invalid JSON arguments",
        ),
        (
            chat_response(
                tool_calls=[
                    {"function": {"name": "calculator", "arguments": [1]}}
                ]
            ),
            "must be an object",
        ),
    ],
)
def test_chat_rejects_invalid_responses(response, error):
    client = FakeClient(responses=[response])
    generator = create_generator(client)

    with pytest.raises(GeneratorResponseError, match=error) as raised:
        generator.chat([])

    assert isinstance(raised.value.__cause__, ValueError)

    assert len(client.calls) == 1


def test_is_available_returns_true_when_configured_model_is_available():
    assert create_generator(FakeClient()).is_available() is True


@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("connection failed"),
        ResponseError("model not found", status_code=404),
    ],
)
def test_is_available_returns_false_when_configured_model_is_unavailable(
    error,
):
    generator = create_generator(FakeClient(show_error=error))

    assert generator.is_available() is False


@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("connection failed"),
        ResponseError("server error", status_code=500),
        httpx.ReadTimeout("request timed out"),
    ],
)
def test_chat_retries_retryable_errors(error):
    client = FakeClient(
        errors=[error],
        responses=[chat_response(content="success after retry")],
    )

    message = create_generator(client).chat([])

    assert message.content == "success after retry"
    assert len(client.calls) == 2


def test_chat_does_not_retry_client_error():
    client = FakeClient(
        errors=[ResponseError("model not found", status_code=404)],
    )

    with pytest.raises(GeneratorResponseError) as raised:
        create_generator(client).chat([])

    assert isinstance(raised.value.__cause__, ResponseError)
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("connection failed"),
        ResponseError("server error", status_code=500),
        httpx.ReadTimeout("request timed out"),
    ],
)
def test_chat_raises_after_max_retries(error):
    client = FakeClient(errors=[error, error, error])

    with pytest.raises(GeneratorUnavailableError) as raised:
        create_generator(client).chat([])

    assert raised.value.__cause__ is error
    assert len(client.calls) == 3


def test_chat_logs_success_with_attempt_count(caplog):
    client = FakeClient(responses=[chat_response(content="answer")])

    with caplog.at_level("INFO"):
        create_generator(client).chat([])

    assert "with ollama model 'fake-model'" in caplog.text
    assert "Generation completed successfully" in caplog.text
    assert "after 1 attempt(s)" in caplog.text


def test_chat_logs_retry_attempt(caplog):
    client = FakeClient(
        errors=[ConnectionError("connection failed")],
        responses=[chat_response(content="success")],
    )

    with caplog.at_level("WARNING"):
        create_generator(client).chat([])

    assert (
        "Generator connection failure on attempt 1/3: connection failed"
        in caplog.text
    )
    assert "Retrying generator" in caplog.text
    assert "next attempt 2/3" in caplog.text


def test_chat_logs_failure_after_retries(caplog):
    error = ConnectionError("connection failed")
    client = FakeClient(errors=[error, error, error])

    with caplog.at_level("ERROR"):
        with pytest.raises(GeneratorUnavailableError):
            create_generator(client).chat([])

    assert (
        "Generator connection failure persisted after 3 attempts"
        in caplog.text
    )


def test_ollama_provider_uses_configured_timeout(monkeypatch):
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(ollama_module, "Client", fake_client)

    OllamaProvider(
        model="fake-model",
        host="http://fake",
        timeout=GENERATOR_TIMEOUT,
    )

    assert captured == {"host": "http://fake", "timeout": GENERATOR_TIMEOUT}


def test_generator_exposes_provider_model():
    generator = create_generator(FakeClient())

    assert generator.model == "fake-model"
