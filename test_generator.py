from unittest.mock import Mock

from ollama import ResponseError

from app.generator import Generator


def test_generator_retries_connection_error():
    generator = Generator(
        max_retries=2,
        retry_base_delay=0,
    )

    generator.client.chat = Mock(
        side_effect=[
            ConnectionError("temporary failure"),
            ConnectionError("temporary failure"),
            {
                "message": {
                    "content": "success",
                },
            },
        ]
    )

    result = generator.generate("Hello")

    print(f"Result: {result}")
    print(f"Call count: {generator.client.chat.call_count}")

    assert result == "success"
    assert generator.client.chat.call_count == 3


def test_generator_does_not_retry_client_error():
    generator = Generator(
        max_retries=3,
        retry_base_delay=0,
    )

    error = ResponseError(
        "model not found",
        status_code=404,
    )

    generator.client.chat = Mock(
        side_effect=error,
    )

    try:
        generator.generate("Hello")
    except ResponseError:
        pass

    print(f"Call count: {generator.client.chat.call_count}")

    assert generator.client.chat.call_count == 1

def test_generator_retries_server_error():
    generator = Generator(
        max_retries=2,
        retry_base_delay=0,
    )

    error = ResponseError(
        "server error",
        status_code=500,
    )

    generator.client.chat = Mock(
        side_effect=[
            error,
            error,
            {
                "message": {
                    "content": "success",
                },
            },
        ],
    )

    result = generator.generate("Hello")

    print(f"Result: {result}")
    print(f"Call count: {generator.client.chat.call_count}")

    assert result == "success"
    assert generator.client.chat.call_count == 3