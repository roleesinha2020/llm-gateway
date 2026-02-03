from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False


class LLMResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    provider: str


class BaseLLMProvider(ABC):
    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        pass

    @abstractmethod
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass
