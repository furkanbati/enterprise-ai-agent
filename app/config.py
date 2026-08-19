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

TOOL_TIMEOUT = float(
    os.getenv("TOOL_TIMEOUT", "5.0")
)

if MAX_RETRIES < 0:
    raise ValueError("MAX_RETRIES must be zero or greater.")

if RETRY_BASE_DELAY < 0:
    raise ValueError("RETRY_BASE_DELAY must be zero or greater.")

if TOOL_MAX_RETRIES < 0:
    raise ValueError("TOOL_MAX_RETRIES must be zero or greater.")
