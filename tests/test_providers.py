import pytest

from app.providers import create_provider
from app.providers.anthropic import AnthropicProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


def test_creates_the_configured_ollama_provider():
    provider = create_provider()

    assert isinstance(provider, OllamaProvider)
    assert provider.model == "qwen2.5:7b"


def test_creates_openai_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    provider = create_provider("openai", model="gpt-test")

    assert isinstance(provider, OpenAIProvider)
    assert provider.client.max_retries == 0


def test_creates_anthropic_provider_with_its_default_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    provider = create_provider("anthropic")

    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-opus-5-5"
    assert provider.client.max_retries == 0


def test_openai_needs_a_model():
    with pytest.raises(ValueError, match="model must be given"):
        create_provider("openai")


def test_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider 'gemini'"):
        create_provider("gemini", model="x")
