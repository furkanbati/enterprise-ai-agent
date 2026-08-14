import pytest

from app.generator import Generator


class FakeClient:
    def __init__(self, responses=None, errors=None):
        self.responses = responses or []
        self.errors = errors or []
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


def create_generator(client):
    generator = Generator(
        host="http://fake",
        model="fake-model",
        max_retries=2,
        retry_base_delay=0,
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
    from ollama import ResponseError

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


def test_generate_does_not_retry_client_error():
    from ollama import ResponseError

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