from app.config import (
    CHAT_MODEL,
    DEFAULT_MODELS,
    GENERATOR_TIMEOUT,
    LLM_PROVIDER,
    LLM_PROVIDERS,
    OLLAMA_HOST,
)
from app.providers.base import ChatProvider


def create_provider(
    name: str = LLM_PROVIDER,
    model: str | None = None,
    timeout: float | None = GENERATOR_TIMEOUT,
) -> ChatProvider:
    """Create a provider, by default the one configured by LLM_PROVIDER.

    Without a model, CHAT_MODEL is used for the configured provider and
    the provider's default model for any other. The SDKs are imported
    here so that only the selected one is loaded.
    """

    if model is None:
        model = CHAT_MODEL if name == LLM_PROVIDER else DEFAULT_MODELS.get(name)

    if not model:
        raise ValueError(f"A model must be given for the {name} provider.")

    if name == "ollama":
        from app.providers.ollama import OllamaProvider

        return OllamaProvider(model=model, host=OLLAMA_HOST, timeout=timeout)

    if name == "openai":
        from app.providers.openai import OpenAIProvider

        return OpenAIProvider(model=model, timeout=timeout)

    if name == "anthropic":
        from app.providers.anthropic import AnthropicProvider

        return AnthropicProvider(model=model, timeout=timeout)

    raise ValueError(
        f"Unknown LLM provider '{name}'. "
        f"Use one of: {', '.join(LLM_PROVIDERS)}."
    )


__all__ = ["ChatProvider", "create_provider"]
