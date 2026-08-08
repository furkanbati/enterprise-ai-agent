from ollama import Client

from app.config import CHAT_MODEL, OLLAMA_HOST


class Generator:

    def __init__(
        self,
        host: str = OLLAMA_HOST,
        model: str = CHAT_MODEL,
    ):
        self.client = Client(host=host)
        self.model = model

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> str:
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