import logging
import time
from typing import Any

from prometheus_client import Counter

from app.config import (
    GENERATOR_MAX_RETRIES,
    RETRY_BASE_DELAY,
)
from app.models import ChatMessage
from app.providers import ChatProvider, create_provider


logger = logging.getLogger(__name__)


GENERATION_TOTAL = Counter(
    "agent_generation_total",
    "Total number of generation calls.",
    ["provider"],
)


class GeneratorError(Exception):
    """The LLM call failed. Raised from the provider's own exception."""


class GeneratorUnavailableError(GeneratorError):
    """A retryable failure (connection, timeout, rate limit, 5xx) persisted."""


class GeneratorResponseError(GeneratorError):
    """The provider rejected the request or returned an invalid response."""


class Generator:
    """Calls the configured LLM provider with retries and backoff.

    Which errors are retried is decided by the provider; the retry loop,
    logging and metrics are the same for every provider. Failures are
    raised as GeneratorError subclasses, so callers do not depend on any
    provider's SDK exceptions.
    """

    def __init__(
        self,
        provider: ChatProvider | None = None,
        max_retries: int = GENERATOR_MAX_RETRIES,
        retry_base_delay: float = RETRY_BASE_DELAY,
    ):
        self.provider = provider or create_provider()
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    @property
    def model(self) -> str:
        return self.provider.model

    def is_available(self) -> bool:
        return self.provider.is_available()

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Send a conversation, optionally with tool schemas.

        Returns the assistant message, which holds either text content or
        the tool calls the model wants to make.
        """

        GENERATION_TOTAL.labels(provider=self.provider.name).inc()

        start_time = time.perf_counter()
        total_attempts = self.max_retries + 1

        logger.info(
            "Generating response with %s model '%s'",
            self.provider.name,
            self.model,
        )

        for attempt in range(total_attempts):
            attempt_number = attempt + 1

            try:
                message = self.provider.chat(messages, tools=tools or None)

            except Exception as exc:
                reason = self.provider.retry_reason(exc)
                duration = time.perf_counter() - start_time

                if reason is None:
                    logger.error(
                        "Generator request failed with a non-retryable "
                        "%s after %.3fs",
                        type(exc).__name__,
                        duration,
                    )
                    raise GeneratorResponseError(str(exc)) from exc

                logger.warning(
                    "Generator %s on attempt %s/%s: %s",
                    reason,
                    attempt_number,
                    total_attempts,
                    exc,
                )

                if attempt >= self.max_retries:
                    logger.error(
                        "Generator %s persisted after %s attempts in %.3fs",
                        reason,
                        attempt_number,
                        duration,
                    )
                    raise GeneratorUnavailableError(str(exc)) from exc

                self._retry(
                    attempt=attempt,
                    attempt_number=attempt_number,
                    total_attempts=total_attempts,
                    reason=reason,
                )
                continue

            logger.info(
                "Generation completed successfully in %.3fs "
                "after %s attempt(s)",
                time.perf_counter() - start_time,
                attempt_number,
            )

            return message

        raise RuntimeError("Generator failed unexpectedly.")

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
