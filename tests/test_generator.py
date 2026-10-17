import httpx
import pytest
from ollama import ResponseError

import app.generator as generator_module
from app.config import GENERATOR_TIMEOUT
from app.generator import Generator
from app.models import ChatMessage, ChatToolCall


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeResponse:
    def __init__(self, content):
        self.message = FakeMessage(content)


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


def create_generator(client, timeout=None):
    generator = Generator(
        host="http://fake",
        model="fake-model",
        max_retries=2,
        retry_base_delay=0,
        timeout=timeout,
    )

    generator.client = client

    return generator


def test_generate_returns_response_content():
    client = FakeClient(
        responses=[
            {
                "message": {
                    "content": "Hello!",
                }
            }
        ]
    )

    generator = create_generator(client)

    result = generator.generate(
        prompt="Say hello",
    )

    assert result == "Hello!"


def test_generate_accepts_response_object():
    client = FakeClient(
        responses=[
            FakeResponse("Hello!"),
        ]
    )

    generator = create_generator(client)

    result = generator.generate(
        prompt="Say hello",
    )

    assert result == "Hello!"


def test_is_available_returns_true_when_configured_model_is_available():
    client = FakeClient()
    generator = create_generator(client)

    assert generator.is_available() is True


@pytest.mark.parametrize(
    "error",
    [
        ConnectionError("connection failed"),
        ResponseError(
            "model not found",
            status_code=404,
        ),
    ],
)
def test_is_available_returns_false_when_configured_model_is_unavailable(
    error,
):
    client = FakeClient(show_error=error)
    generator = create_generator(client)

    assert generator.is_available() is False


def test_generate_sends_system_prompt():
    client = FakeClient(
        responses=[
            {
                "message": {
                    "content": "answer",
                }
            }
        ]
    )

    generator = create_generator(client)

    generator.generate(
        prompt="What is 2 + 2?",
        system_prompt="You are a calculator.",
    )

    call = client.calls[0]

    assert call["messages"][0] == {
        "role": "system",
        "content": "You are a calculator.",
    }

    assert call["messages"][1] == {
        "role": "user",
        "content": "What is 2 + 2?",
    }


def test_generate_uses_json_mode():
    client = FakeClient(
        responses=[
            {
                "message": {
                    "content": '{"tool": null, "arguments": {}}',
                }
            }
        ]
    )

    generator = create_generator(client)

    generator.generate(
        prompt="Hello",
        json_mode=True,
    )

    call = client.calls[0]

    assert call["format"] == "json"


def test_generate_uses_normal_mode():
    client = FakeClient(
        responses=[
            {
                "message": {
                    "content": "normal answer",
                }
            }
        ]
    )

    generator = create_generator(client)

    generator.generate(
        prompt="Hello",
        json_mode=False,
    )

    call = client.calls[0]

    assert call["format"] is None


def test_generate_retries_connection_error():
    client = FakeClient(
        errors=[
            ConnectionError("connection failed"),
        ],
        responses=[
            {
                "message": {
                    "content": "success after retry",
                }
            }
        ],
    )

    generator = create_generator(client)

    result = generator.generate(
        prompt="Hello",
    )

    assert result == "success after retry"
    assert len(client.calls) == 2


def test_generate_retries_server_error():
    error = ResponseError(
        "server error",
        status_code=500,
    )

    client = FakeClient(
        errors=[error],
        responses=[
            {
                "message": {
                    "content": "success after retry",
                }
            }
        ],
    )

    generator = create_generator(client)

    result = generator.generate(
        prompt="Hello",
    )

    assert result == "success after retry"
    assert len(client.calls) == 2


def test_generate_retries_timeout():
    client = FakeClient(
        errors=[
            httpx.ReadTimeout("request timed out"),
        ],
        responses=[
            {
                "message": {
                    "content": "success after timeout",
                }
            }
        ],
    )

    generator = create_generator(client, timeout=5.0)

    result = generator.generate(
        prompt="Hello",
    )

    assert result == "success after timeout"
    assert len(client.calls) == 2


def test_generate_does_not_retry_client_error():
    error = ResponseError(
        "model not found",
        status_code=404,
    )

    client = FakeClient(
        errors=[error],
    )

    generator = create_generator(client)

    with pytest.raises(ResponseError):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 1


def test_generate_raises_after_server_error_retries():
    errors = [
        ResponseError(
            "server error",
            status_code=500,
        ),
        ResponseError(
            "server error",
            status_code=500,
        ),
        ResponseError(
            "server error",
            status_code=500,
        ),
    ]

    client = FakeClient(
        errors=errors,
    )

    generator = create_generator(client)

    with pytest.raises(ResponseError):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 3


def test_generate_raises_after_max_retries():
    client = FakeClient(
        errors=[
            ConnectionError("connection failed"),
            ConnectionError("connection failed"),
            ConnectionError("connection failed"),
        ],
    )

    generator = create_generator(client)

    with pytest.raises(ConnectionError):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 3


def test_generate_raises_after_timeout_retries():
    client = FakeClient(
        errors=[
            httpx.ReadTimeout("request timed out"),
            httpx.ReadTimeout("request timed out"),
            httpx.ReadTimeout("request timed out"),
        ],
    )

    generator = create_generator(client, timeout=5.0)

    with pytest.raises(httpx.ReadTimeout):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 3


def test_generate_rejects_response_without_message():
    client = FakeClient(
        responses=[
            None,
        ]
    )

    generator = create_generator(client)

    with pytest.raises(
        ValueError,
        match="Generator response is missing message",
    ):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 1


def test_generate_rejects_missing_message():
    client = FakeClient(
        responses=[
            {},
        ]
    )

    generator = create_generator(client)

    with pytest.raises(
        ValueError,
        match="Generator response is missing message",
    ):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 1


def test_generate_rejects_non_dict_message():
    client = FakeClient(
        responses=[
            {
                "message": None,
            }
        ]
    )

    generator = create_generator(client)

    with pytest.raises(
        ValueError,
        match="Generator response is missing message",
    ):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 1


def test_generate_rejects_missing_content():
    client = FakeClient(
        responses=[
            {
                "message": {},
            }
        ]
    )

    generator = create_generator(client)

    with pytest.raises(
        ValueError,
        match="Generator response is missing content",
    ):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 1


def test_generate_rejects_non_string_content():
    client = FakeClient(
        responses=[
            {
                "message": {
                    "content": None,
                }
            }
        ]
    )

    generator = create_generator(client)

    with pytest.raises(
        ValueError,
        match="Generator response is missing content",
    ):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        "\n",
        "\t",
        " \n\t ",
    ],
)
def test_generate_rejects_empty_response(content):
    client = FakeClient(
        responses=[
            {
                "message": {
                    "content": content,
                }
            }
        ]
    )

    generator = create_generator(client)

    with pytest.raises(
        ValueError,
        match="Generator returned an empty response",
    ):
        generator.generate(
            prompt="Hello",
        )

    assert len(client.calls) == 1


def test_generate_logs_success_with_attempt_count_and_duration(
    caplog,
):
    client = FakeClient(
        responses=[
            {
                "message": {
                    "content": "answer",
                }
            }
        ]
    )

    generator = create_generator(client)

    with caplog.at_level("INFO"):
        result = generator.generate(
            prompt="Hello",
        )

    assert result == "answer"

    assert (
        "Generation completed successfully"
        in caplog.text
    )

    assert "after 1 attempt(s)" in caplog.text
    assert "s" in caplog.text


def test_generate_logs_retry_attempt(caplog):
    client = FakeClient(
        errors=[
            ConnectionError("connection failed"),
        ],
        responses=[
            {
                "message": {
                    "content": "success",
                }
            }
        ],
    )

    generator = create_generator(client)

    with caplog.at_level("WARNING"):
        result = generator.generate(
            prompt="Hello",
        )

    assert result == "success"

    assert (
        "Generator connection failed on attempt 1/3"
        in caplog.text
    )

    assert (
        "Retrying generator"
        in caplog.text
    )

    assert "next attempt 2/3" in caplog.text


def test_generate_logs_failure_after_retries(caplog):
    client = FakeClient(
        errors=[
            ConnectionError("connection failed"),
            ConnectionError("connection failed"),
            ConnectionError("connection failed"),
        ],
    )

    generator = create_generator(client)

    with caplog.at_level("ERROR"):
        with pytest.raises(ConnectionError):
            generator.generate(
                prompt="Hello",
            )

    assert (
        "Generator connection failed after 3 attempts"
        in caplog.text
    )

    assert "in " in caplog.text

def test_generator_uses_configured_timeout_by_default(monkeypatch):
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(generator_module, "Client", fake_client)

    generator = Generator(host="http://fake", model="fake-model")

    assert generator.timeout == GENERATOR_TIMEOUT
    assert captured == {"host": "http://fake", "timeout": GENERATOR_TIMEOUT}


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
        ({}, "missing message"),
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
    generator = create_generator(FakeClient(responses=[response]))

    with pytest.raises(ValueError, match=error):
        generator.chat([])


def test_chat_retries_connection_errors():
    client = FakeClient(
        responses=[chat_response(content="ok")],
        errors=[ConnectionError("down")],
    )

    message = create_generator(client).chat([])

    assert message.content == "ok"
    assert len(client.calls) == 2
