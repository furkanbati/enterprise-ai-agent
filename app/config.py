import os

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434",
)

CHAT_MODEL = os.getenv(
    "CHAT_MODEL",
    "llama3",
)
GENERATOR_MAX_RETRIES = int(
    os.getenv("GENERATOR_MAX_RETRIES", "3")
)

EXECUTOR_MAX_RETRIES = int(
    os.getenv("EXECUTOR_MAX_RETRIES", "2")
)

PIPELINE_MAX_REPLANS = int(
    os.getenv("PIPELINE_MAX_REPLANS", "2")
)


RETRY_BASE_DELAY = float(
    os.getenv("RETRY_BASE_DELAY", "1.0")
)


TOOL_TIMEOUT = float(
    os.getenv("TOOL_TIMEOUT", "5.0")
)

if EXECUTOR_MAX_RETRIES < 0:
    raise ValueError("EXECUTOR_MAX_RETRIES must be zero or greater.")
if PIPELINE_MAX_REPLANS < 0:
    raise ValueError("PIPELINE_MAX_REPLANS must be zero or greater.")
if GENERATOR_MAX_RETRIES < 0:
    raise ValueError("GENERATOR_MAX_RETRIES must be zero or greater.")
if TOOL_TIMEOUT < 0:
    raise ValueError("TOOL_TIMEOUT must be zero or greater.")

if RETRY_BASE_DELAY < 0:
    raise ValueError("RETRY_BASE_DELAY must be zero or greater.")


