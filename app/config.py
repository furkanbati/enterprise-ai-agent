import os

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434",
)

CHAT_MODEL = os.getenv(
    "CHAT_MODEL",
    "llama3",
)

MAX_RETRIES = int(
    os.getenv("MAX_RETRIES", "3")
)

RETRY_BASE_DELAY = float(
    os.getenv("RETRY_BASE_DELAY", "1.0")
)

TOOL_MAX_RETRIES = int(
    os.getenv("TOOL_MAX_RETRIES", "1")
)
