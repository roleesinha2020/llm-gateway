import structlog
from openai import AsyncOpenAI

from src.core.config import get_settings
from src.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

logger = structlog.get_logger()
settings = get_settings()


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            response = await self.client.chat.completions.create(
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                finish_reason=response.choices[0].finish_reason,
                provider="openai",
            )
        except Exception as e:
            logger.error("OpenAI API error", error=str(e))
            raise

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens + completion_tokens) / 1000 * settings.OPENAI_COST_PER_1K_TOKENS

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
