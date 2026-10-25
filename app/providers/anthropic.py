import logging
from typing import Any

import anthropic

from app.models import ChatMessage
from app.providers.base import ChatProvider, build_message, build_tool_call


logger = logging.getLogger(__name__)


MAX_TOKENS = 16_000

REFUSAL_ANSWER = "The model declined to answer this request."

# Models that accept server-side refusal fallbacks: when the model declines
# a request, the API reruns it on a fallback model in the same call.
FALLBACK_MODELS = {
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-sonnet-5-5",
}

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(ChatProvider):
    """Claude through the Anthropic Messages API.

    The SDK reads ANTHROPIC_API_KEY from the environment.
    """

    name = "anthropic"

    def __init__(
        self,
        model: str,
        timeout: float | None,
        client: Any = None,
    ):
        super().__init__(model)
        # The Generator owns retries, so the SDK's own retries are off.
        self.client = client or anthropic.Anthropic(
            timeout=timeout,
            max_retries=0,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        system, converted = _to_anthropic(messages)

        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": converted,
        }

        if system:
            request["system"] = system

        if tools:
            request["tools"] = [_to_anthropic_tool(tool) for tool in tools]

        elif _has_tool_blocks(converted):
            # Tools were withdrawn, but the history still holds tool_use
            # blocks, and the API requires those tools to be defined.
            # Declare them by name and forbid new calls.
            request["tools"] = [
                {
                    "name": name,
                    "input_schema": {"type": "object"},
                }
                for name in _tool_names(converted)
            ]
            request["tool_choice"] = {"type": "none"}

        if self.model in FALLBACK_MODELS:
            request["betas"] = [FALLBACK_BETA]
            request["fallbacks"] = "default"

        response = self.client.beta.messages.create(**request)

        if response.stop_reason == "refusal":
            logger.warning("Model '%s' declined the request", self.model)

        text = "".join(
            block.text for block in response.content if block.type == "text"
        )

        tool_calls = [
            build_tool_call(
                name=block.name,
                arguments=block.input,
                call_id=block.id,
            )
            for block in response.content
            if block.type == "tool_use"
        ]

        if response.stop_reason == "refusal" and not text.strip():
            text = REFUSAL_ANSWER

        # The content goes back unchanged on the next turn: thinking blocks
        # must stay with the tool_use blocks they came with.
        return build_message(
            text,
            tool_calls,
            provider_content=list(response.content),
        )

    def is_available(self) -> bool:
        try:
            self.client.models.retrieve(self.model)

        except anthropic.APIError as exc:
            logger.warning(
                "Anthropic model '%s' is unavailable: %s",
                self.model,
                exc,
            )
            return False

        return True

    def retry_reason(self, error: Exception) -> str | None:
        # APITimeoutError is a subclass of APIConnectionError.
        if isinstance(error, anthropic.APITimeoutError):
            return "timeout"

        if isinstance(error, anthropic.APIConnectionError):
            return "connection failure"

        if isinstance(error, anthropic.RateLimitError):
            return "rate limit"

        if (
            isinstance(error, anthropic.APIStatusError)
            and error.status_code >= 500
        ):
            return "server error"

        return None


def _to_anthropic_tool(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool["function"]

    return {
        "name": function["name"],
        "description": function.get("description", ""),
        "input_schema": function["parameters"],
    }


def _to_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Split out the system prompt and convert the rest to Messages API turns.

    Tool results become tool_result blocks in a user turn. Consecutive
    tool results, and a user message that follows them, share one turn.
    """

    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []

    for message in messages:
        role = message["role"]

        if role == "system":
            system_parts.append(message["content"])

        elif role == "assistant":
            converted.append(
                {
                    "role": "assistant",
                    "content": _assistant_content(message),
                }
            )

        elif role == "tool":
            _append_user_block(
                converted,
                {
                    "type": "tool_result",
                    "tool_use_id": message["tool_call_id"],
                    "content": message["content"],
                },
            )

        elif _last_turn_has_blocks(converted):
            _append_user_block(
                converted,
                {"type": "text", "text": message["content"]},
            )

        else:
            converted.append(
                {"role": "user", "content": message["content"]}
            )

    return "\n\n".join(system_parts), converted


def _assistant_content(message: dict[str, Any]) -> Any:
    if message.get("provider_content") is not None:
        return message["provider_content"]

    blocks: list[dict[str, Any]] = []

    if message.get("content"):
        blocks.append({"type": "text", "text": message["content"]})

    for tool_call in message.get("tool_calls") or []:
        blocks.append(
            {
                "type": "tool_use",
                "id": tool_call["id"],
                "name": tool_call["function"]["name"],
                "input": tool_call["function"]["arguments"],
            }
        )

    return blocks or message.get("content", "")


def _last_turn_has_blocks(converted: list[dict[str, Any]]) -> bool:
    return bool(
        converted
        and converted[-1]["role"] == "user"
        and isinstance(converted[-1]["content"], list)
    )


def _append_user_block(
    converted: list[dict[str, Any]],
    block: dict[str, Any],
) -> None:
    if _last_turn_has_blocks(converted):
        converted[-1]["content"].append(block)
    else:
        converted.append({"role": "user", "content": [block]})


def _block_field(block: Any, key: str) -> Any:
    if isinstance(block, dict):
        return block.get(key)

    return getattr(block, key, None)


def _tool_names(converted: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []

    for turn in converted:
        if turn["role"] != "assistant" or not isinstance(turn["content"], list):
            continue

        for block in turn["content"]:
            name = _block_field(block, "name")

            if _block_field(block, "type") == "tool_use" and name not in names:
                names.append(name)

    return names


def _has_tool_blocks(converted: list[dict[str, Any]]) -> bool:
    return bool(_tool_names(converted))
