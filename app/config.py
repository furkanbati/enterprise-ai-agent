import os

LLM_PROVIDERS = ("ollama", "openai", "anthropic")

# Used when CHAT_MODEL is not set. OpenAI has no default: its model names
# change often, so the model must be chosen explicitly.
DEFAULT_MODELS = {
    "ollama": "qwen2.5:7b",
    "anthropic": "claude-opus-5-5",
}

# A blank value, e.g. "LLM_PROVIDER=" in .env, means the default.
LLM_PROVIDER = (
    os.getenv("LLM_PROVIDER", "").strip().lower() or "ollama"
)

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434",
)

CHAT_MODEL = os.getenv(
    "CHAT_MODEL",
    DEFAULT_MODELS.get(LLM_PROVIDER, ""),
)
GENERATOR_MAX_RETRIES = int(
    os.getenv("GENERATOR_MAX_RETRIES", "3")
)

EXECUTOR_MAX_RETRIES = int(
    os.getenv("EXECUTOR_MAX_RETRIES", "2")
)

AGENT_MAX_STEPS = int(
    os.getenv("AGENT_MAX_STEPS", "5")
)


RETRY_BASE_DELAY = float(
    os.getenv("RETRY_BASE_DELAY", "1.0")
)


TOOL_TIMEOUT = float(
    os.getenv("TOOL_TIMEOUT", "5.0")
)


# SQLite database for the support scenario, created with demo data on
# first use.
BUSINESS_DB_PATH = os.getenv(
    "BUSINESS_DB_PATH",
    "var/business.db",
)

GENERATOR_TIMEOUT = float(
    os.getenv("GENERATOR_TIMEOUT", "120.0")
)

if EXECUTOR_MAX_RETRIES < 0:
    raise ValueError("EXECUTOR_MAX_RETRIES must be zero or greater.")
if AGENT_MAX_STEPS < 1:
    raise ValueError("AGENT_MAX_STEPS must be at least 1.")
if GENERATOR_MAX_RETRIES < 0:
    raise ValueError("GENERATOR_MAX_RETRIES must be zero or greater.")
if TOOL_TIMEOUT < 0:
    raise ValueError("TOOL_TIMEOUT must be zero or greater.")

if GENERATOR_TIMEOUT <= 0:
    raise ValueError("GENERATOR_TIMEOUT must be greater than zero.")

if RETRY_BASE_DELAY < 0:
    raise ValueError("RETRY_BASE_DELAY must be zero or greater.")
if not OLLAMA_HOST.strip():
    raise ValueError(
        "OLLAMA_HOST cannot be empty."
    )

if LLM_PROVIDER not in LLM_PROVIDERS:
    raise ValueError(
        "LLM_PROVIDER must be one of: " + ", ".join(LLM_PROVIDERS) + "."
    )

if "CHAT_MODEL" not in os.environ and LLM_PROVIDER not in DEFAULT_MODELS:
    raise ValueError(
        f"CHAT_MODEL must be set when LLM_PROVIDER is {LLM_PROVIDER}."
    )

if not CHAT_MODEL.strip():
    raise ValueError(
        "CHAT_MODEL cannot be empty."
    )

