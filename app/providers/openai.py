import json
import logging
from typing import Any

import openai

from app.models import ChatMessage
from app.providers.base import ChatProvider, build_message, build_tool_call


logger = logging.getLogger(__name__)


class OpenAIProvider(ChatProvider):
    """OpenAI Chat Completions, or any compatible API through OPENAI_BASE_URL.

    The SDK reads OPENAI_API_KEY and OPENAI_BASE_URL from the environment.
    """

    name = "openai"

    def __init__(
        self,
        model: str,
        timeout: float | None,
        client: Any = None,
    ):
        super().__init__(model)
        # The Generator owns retries, so the SDK's own retries are off.
        self.client = client or openai.OpenAI(
            timeout=timeout,
            max_retries=0,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [_to_openai(message) for message in messages],
        }

        if tools:
            request["tools"] = tools

        response = self.client.chat.completions.create(**request)

        if not response.choices:
            raise ValueError(
                "Generator response is missing message."
            )

        message = response.choices[0].message

        tool_calls = [
            build_tool_call(
                name=tool_call.function.name,
                arguments=tool_call.function.arguments,
                call_id=tool_call.id,
            )
            for tool_call in message.tool_calls or []
        ]

        return build_message(message.content, tool_calls)

    def is_available(self) -> bool:
        try:
            self.client.models.retrieve(self.model)

        except openai.APIError as exc:
            logger.warning(
                "OpenAI model '%s' is unavailable: %s",
                self.model,
                exc,
            )
            return False

        return True

    def retry_reason(self, error: Exception) -> str | None:
        # APITimeoutError is a subclass of APIConnectionError.
        if isinstance(error, openai.APITimeoutError):
            return "timeout"

        if isinstance(error, openai.APIConnectionError):
            return "connection failure"

        if isinstance(error, openai.RateLimitError):
            return "rate limit"

        if isinstance(error, openai.APIStatusError) and error.status_code >= 500:
            return "server error"

        return None


def _to_openai(message: dict[str, Any]) -> dict[str, Any]:
    if message["role"] == "tool":
        return {
            "role": "tool",
            "tool_call_id": message["tool_call_id"],
            "content": message["content"],
        }

    if message["role"] == "assistant" and message.get("tool_calls"):
        return {
            "role": "assistant",
            "content": message.get("content") or None,
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "type": "function",
                    "function": {
                        "name": tool_call["function"]["name"],
                        "arguments": json.dumps(
                            tool_call["function"]["arguments"]
                        ),
                    },
                }
                for tool_call in message["tool_calls"]
            ],
        }

    return {"role": message["role"], "content": message["content"]}
