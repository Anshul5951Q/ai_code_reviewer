"""
LLM Client factory and provider resolution.
"""
from __future__ import annotations

import os
from typing import Optional

from app.core.config import settings
from app.llm.provider import LLMProvider, MockLLMProvider, OllamaProvider

_global_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """
    Return the active LLMProvider based on configuration.
    Defaults to OllamaProvider using system configuration settings,
    or MockLLMProvider for testing or when LLM_PROVIDER=mock.
    """
    global _global_provider
    if _global_provider is not None:
        return _global_provider

    provider_name = os.getenv("LLM_PROVIDER", settings.llm_provider).lower()

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.ollama_timeout_seconds,
            max_concurrent=settings.ollama_max_concurrent,
            context_size=settings.ollama_context_size,
            temperature=settings.ollama_temperature,
            keep_alive=settings.ollama_keep_alive,
            max_retries=settings.ollama_max_retries,
        )

    # Deterministic mock provider for tests or offline validation
    return MockLLMProvider()


def set_llm_provider(provider: Optional[LLMProvider]) -> None:
    """Explicitly set provider (primarily for unit/integration tests)."""
    global _global_provider
    _global_provider = provider
