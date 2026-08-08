import os

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434",
)

CHAT_MODEL = os.getenv(
    "CHAT_MODEL",
    "llama3",
)