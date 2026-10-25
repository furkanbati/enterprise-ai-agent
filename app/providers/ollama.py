import logging
from typing import Any

import httpx
from ollama import Client, ResponseError

from app.models import ChatMessage
from app.providers.base import (
    ChatProvider,
    build_message,
    build_tool_call,
    get_field,
)


logger = logging.getLogger(__name__)


class OllamaProvider(ChatProvider):
    """Local models served by Ollama."""

    name = "ollama"

    def __init__(
        self,
        model: str,
        host: str,
        timeout: float | None,
    ):
        super().__init__(model)
        self.client = Client(host=host, timeout=timeout)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        response = self.client.chat(
            model=self.model,
            messages=[_to_ollama(message) for message in messages],
            tools=tools or None,
        )

        message = get_field(response, "message")

        if message is None:
            raise ValueError(
                "Generator response is missing message."
            )

        tool_calls = []

        for tool_call in get_field(message, "tool_calls") or []:
            function = get_field(tool_call, "function")

            tool_calls.append(
                build_tool_call(
                    name=get_field(function, "name") if function else None,
                    arguments=(
                        get_field(function, "arguments") if function else None
                    ),
                )
            )

        return build_message(get_field(message, "content"), tool_calls)

    def is_available(self) -> bool:
        try:
            self.client.show(self.model)

        except (ConnectionError, ResponseError) as exc:
            logger.warning(
                "Ollama model '%s' is unavailable: %s",
                self.model,
                exc,
            )
            return False

        return True

    def retry_reason(self, error: Exception) -> str | None:
        if isinstance(error, ConnectionError):
            return "connection failure"

        if isinstance(error, httpx.TimeoutException):
            return "timeout"

        if isinstance(error, ResponseError) and error.status_code >= 500:
            return "server error"

        return None


def _to_ollama(message: dict[str, Any]) -> dict[str, Any]:
    """Drop the fields only ID-based providers use."""

    if message["role"] == "tool":
        return {
            key: value
            for key, value in message.items()
            if key != "tool_call_id"
        }

    if message["role"] == "assistant" and "tool_calls" in message:
        return {
            "role": "assistant",
            "content": message.get("content", ""),
            "tool_calls": [
                {"function": tool_call["function"]}
                for tool_call in message["tool_calls"]
            ],
        }

    return message
