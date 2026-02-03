import structlog
from anthropic import AsyncAnthropic

from src.core.config import get_settings
from src.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

logger = structlog.get_logger()
settings = get_settings()


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            # Anthropic requires system messages separately; extract if present
            system_msg = None
            messages = []
            for msg in request.messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    messages.append(msg)

            kwargs = dict(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            if system_msg:
                kwargs["system"] = system_msg

            response = await self.client.messages.create(**kwargs)

            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                finish_reason=response.stop_reason,
                provider="anthropic",
            )
        except Exception as e:
            logger.error("Anthropic API error", error=str(e))
            raise

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens + completion_tokens) / 1000 * settings.ANTHROPIC_COST_PER_1K_TOKENS

    async def health_check(self) -> bool:
        try:
            await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception:
            return False
