import time

from ollama import Client, ResponseError

from app.config import (
    CHAT_MODEL,
    MAX_RETRIES,
    OLLAMA_HOST,
    RETRY_BASE_DELAY,
)


class Generator:

    def __init__(
        self,
        host: str = OLLAMA_HOST,
        model: str = CHAT_MODEL,
        max_retries: int = MAX_RETRIES,
        retry_base_delay: float = RETRY_BASE_DELAY,
    ):
        self.client = Client(host=host)
        self.model = model
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    def is_available(self) -> bool:
        try:
            self.client.show(self.model)
        except (ConnectionError, ResponseError):
            return False

        return True

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> str:

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat(
                    model=self.model,
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

                return response["message"]["content"]

            except ConnectionError:
                if attempt >= self.max_retries:
                    raise

                self._wait(attempt)

            except ResponseError as exc:
                if not self._is_retryable_response(exc):
                    raise

                if attempt >= self.max_retries:
                    raise

                self._wait(attempt)

        raise RuntimeError("Generator failed unexpectedly.")

    def _is_retryable_response(self, error: ResponseError) -> bool:
        return error.status_code >= 500

    def _wait(self, attempt: int) -> None:
        delay = self.retry_base_delay * (2 ** attempt)
        time.sleep(delay)
