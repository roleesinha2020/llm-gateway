from typing import Optional

from src.core.config import get_settings
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.base import BaseLLMProvider
from src.providers.openai_provider import OpenAIProvider

settings = get_settings()


class ProviderFactory:
    _providers: dict[str, BaseLLMProvider] = {}

    @classmethod
    def get_provider(cls, provider_name: str) -> Optional[BaseLLMProvider]:
        if provider_name in cls._providers:
            return cls._providers[provider_name]

        if provider_name == "openai" and settings.OPENAI_API_KEY:
            cls._providers["openai"] = OpenAIProvider(settings.OPENAI_API_KEY)
        elif provider_name == "anthropic" and settings.ANTHROPIC_API_KEY:
            cls._providers["anthropic"] = AnthropicProvider(settings.ANTHROPIC_API_KEY)

        return cls._providers.get(provider_name)

    @classmethod
    async def get_healthy_provider(
        cls, preferred_order: list[str]
    ) -> Optional[BaseLLMProvider]:
        for provider_name in preferred_order:
            provider = cls.get_provider(provider_name)
            if provider and await provider.health_check():
                return provider
        return None
