import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
from ollama import Client, ResponseError
from prometheus_client import Counter

from app.config import (
    CHAT_MODEL,
    GENERATOR_MAX_RETRIES,
    GENERATOR_TIMEOUT,
    OLLAMA_HOST,
    RETRY_BASE_DELAY,
)
from app.models import ChatMessage, ChatToolCall


logger = logging.getLogger(__name__)


GENERATION_TOTAL = Counter(
    "agent_generation_total",
    "Total number of generation calls.",
)


class Generator:

    def __init__(
        self,
        host: str = OLLAMA_HOST,
        model: str = CHAT_MODEL,
        max_retries: int = GENERATOR_MAX_RETRIES,
        retry_base_delay: float = RETRY_BASE_DELAY,
        timeout: float | None = GENERATOR_TIMEOUT,
    ):
        self.client = Client(
            host=host,
            timeout=timeout,
        )
        self.model = model
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            self.client.show(self.model)

        except (ConnectionError, ResponseError) as exc:
            logger.warning(
                "Generator model '%s' is unavailable: %s",
                self.model,
                exc,
            )
            return False

        return True

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> str:
        return self._chat_with_retries(
            validate=self._validate_response,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt or "",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            format="json" if json_mode else None,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send a conversation, optionally with tool schemas.

        Returns the assistant message, which holds either text content or
        the tool calls the model wants to make.
        """
        return self._chat_with_retries(
            validate=self._validate_message,
            messages=messages,
            tools=tools or None,
        )

    def _chat_with_retries(
        self,
        validate: Callable[[Any], Any],
        **chat_kwargs: Any,
    ) -> Any:
        GENERATION_TOTAL.inc()

        start_time = time.perf_counter()
        total_attempts = self.max_retries + 1

        logger.info(
            "Generating response with model '%s'",
            self.model,
        )

        for attempt in range(total_attempts):
            attempt_number = attempt + 1

            try:
                response = self.client.chat(
                    model=self.model,
                    **chat_kwargs,
                )

                content = validate(response)

                duration = time.perf_counter() - start_time

                logger.info(
                    "Generation completed successfully in %.3fs "
                    "after %s attempt(s)",
                    duration,
                    attempt_number,
                )

                return content

            except ConnectionError as exc:
                logger.warning(
                    "Generator connection failed on attempt %s/%s: %s",
                    attempt_number,
                    total_attempts,
                    exc,
                )

                if attempt >= self.max_retries:
                    duration = time.perf_counter() - start_time

                    logger.error(
                        "Generator connection failed after %s attempts "
                        "in %.3fs",
                        attempt_number,
                        duration,
                    )

                    raise

                self._retry(
                    attempt=attempt,
                    attempt_number=attempt_number,
                    total_attempts=total_attempts,
                    reason="connection failure",
                )

            except httpx.TimeoutException:
                logger.warning(
                    "Generator timed out on attempt %s/%s",
                    attempt_number,
                    total_attempts,
                )

                if attempt >= self.max_retries:
                    duration = time.perf_counter() - start_time

                    logger.error(
                        "Generator timed out after %s attempts "
                        "in %.3fs",
                        attempt_number,
                        duration,
                    )

                    raise

                self._retry(
                    attempt=attempt,
                    attempt_number=attempt_number,
                    total_attempts=total_attempts,
                    reason="timeout",
                )

            except ResponseError as exc:
                if not self._is_retryable_response(exc):
                    duration = time.perf_counter() - start_time

                    logger.error(
                        "Generator request failed with non-retryable "
                        "ResponseError after %.3fs",
                        duration,
                    )

                    raise

                logger.warning(
                    "Generator received retryable server error "
                    "on attempt %s/%s",
                    attempt_number,
                    total_attempts,
                )

                if attempt >= self.max_retries:
                    duration = time.perf_counter() - start_time

                    logger.error(
                        "Generator server error persisted after %s "
                        "attempts in %.3fs",
                        attempt_number,
                        duration,
                    )

                    raise

                self._retry(
                    attempt=attempt,
                    attempt_number=attempt_number,
                    total_attempts=total_attempts,
                    reason="server error",
                )

        duration = time.perf_counter() - start_time

        logger.error(
            "Generator failed unexpectedly after %s attempts "
            "in %.3fs",
            total_attempts,
            duration,
        )

        raise RuntimeError("Generator failed unexpectedly.")

    def _validate_response(self, response) -> str:
        if isinstance(response, dict):
            message = response.get("message")
        else:
            message = getattr(response, "message", None)

        if message is None:
            raise ValueError(
                "Generator response is missing message."
            )

        if isinstance(message, dict):
            content = message.get("content")
        else:
            content = getattr(message, "content", None)

        if not isinstance(content, str):
            raise ValueError(
                "Generator response is missing content."
            )

        if not content.strip():
            raise ValueError(
                "Generator returned an empty response."
            )

        return content

    def _validate_message(self, response) -> ChatMessage:
        message = _get(response, "message")

        if message is None:
            raise ValueError(
                "Generator response is missing message."
            )

        content = _get(message, "content") or ""

        if not isinstance(content, str):
            raise ValueError(
                "Generator response content must be a string."
            )

        tool_calls = [
            self._parse_tool_call(tool_call)
            for tool_call in _get(message, "tool_calls") or []
        ]

        if not content.strip() and not tool_calls:
            raise ValueError(
                "Generator returned an empty response."
            )

        return ChatMessage(
            content=content,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _parse_tool_call(tool_call) -> ChatToolCall:
        function = _get(tool_call, "function")
        name = _get(function, "name") if function is not None else None
        arguments = (
            _get(function, "arguments") if function is not None else None
        )

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "Generator returned a tool call without a name."
            )

        # Ollama returns a dict; some models emit a JSON-encoded string.
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

        return ChatToolCall(
            name=name,
            arguments=dict(arguments),
        )

    def _is_retryable_response(
        self,
        error: ResponseError,
    ) -> bool:
        return error.status_code >= 500

    def _get_retry_delay(self, attempt: int) -> float:
        return self.retry_base_delay * (2**attempt)

    def _retry(
        self,
        attempt: int,
        attempt_number: int,
        total_attempts: int,
        reason: str,
    ) -> None:
        delay = self._get_retry_delay(attempt)

        logger.warning(
            "Retrying generator in %.2fs "
            "(next attempt %s/%s, reason: %s)",
            delay,
            attempt_number + 1,
            total_attempts,
            reason,
        )

        time.sleep(delay)


def _get(value, key: str):
    """Read a field from an Ollama response object or a plain dict."""

    if isinstance(value, dict):
        return value.get(key)

    return getattr(value, key, None)
