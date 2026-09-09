"""
LLM Client factory and provider resolution.
"""
from __future__ import annotations

import os
from typing import Optional

from app.core.config import settings
from app.llm.provider import LLMProvider, MockLLMProvider, OpenAICompatibleProvider

_global_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """
    Return the active LLMProvider based on configuration.
    Defaults to MockLLMProvider if no API key is present.
    """
    global _global_provider
    if _global_provider is not None:
        return _global_provider

    provider_name = os.getenv("LLM_PROVIDER", "mock").lower()
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    timeout = float(os.getenv("LLM_TIMEOUT", "60.0"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))

    if provider_name == "openai" and api_key:
        return OpenAICompatibleProvider(
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_retries=max_retries,
        )

    # Default to deterministic mock provider
    return MockLLMProvider()


def set_llm_provider(provider: Optional[LLMProvider]) -> None:
    """Explicitly set provider (primarily for unit/integration tests)."""
    global _global_provider
    _global_provider = provider
