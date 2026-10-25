import json
from abc import ABC, abstractmethod
from typing import Any

from app.models import ChatMessage, ChatToolCall


class ChatProvider(ABC):
    """Sends a conversation to one LLM API and returns the assistant message.

    The agent builds messages in one neutral format (system, user,
    assistant with tool_calls, tool). Each provider converts them to its
    own API and converts the response back to a ChatMessage. Retries,
    logging and metrics stay in the Generator, so every provider gets the
    same behaviour.
    """

    name: str

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send the conversation, with tool schemas when tools is not None."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the API is reachable and the configured model exists."""

    @abstractmethod
    def retry_reason(self, error: Exception) -> str | None:
        """Why the failed call may be retried, or None if it may not."""


def parse_arguments(name: str, arguments: Any) -> dict[str, Any]:
    """Normalise tool call arguments to a dict.

    Ollama and Anthropic return a dict; OpenAI and some Ollama models
    return a JSON-encoded string.
    """

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Tool call '{name}' has invalid JSON arguments."
            ) from exc

    if arguments is None:
        arguments = {}

    if not isinstance(arguments, dict):
        raise ValueError(
            f"Tool call '{name}' arguments must be an object."
        )

    return dict(arguments)


def build_tool_call(
    name: Any,
    arguments: Any,
    call_id: str | None = None,
) -> ChatToolCall:
    if not isinstance(name, str) or not name.strip():
        raise ValueError(
            "Generator returned a tool call without a name."
        )

    return ChatToolCall(
        name=name,
        arguments=parse_arguments(name, arguments),
        id=call_id,
    )


def build_message(
    content: Any,
    tool_calls: list[ChatToolCall],
    provider_content: Any = None,
) -> ChatMessage:
    content = content or ""

    if not isinstance(content, str):
        raise ValueError(
            "Generator response content must be a string."
        )

    if not content.strip() and not tool_calls:
        raise ValueError(
            "Generator returned an empty response."
        )

    return ChatMessage(
        content=content,
        tool_calls=tool_calls,
        provider_content=provider_content,
    )


def get_field(value: Any, key: str) -> Any:
    """Read a field from an SDK response object or a plain dict."""

    if isinstance(value, dict):
        return value.get(key)

    return getattr(value, key, None)
