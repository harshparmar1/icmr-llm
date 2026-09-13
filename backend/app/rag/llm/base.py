from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class LLMResponse:
    """
    Standardized container for LLM generation outputs.
    """
    content: str
    model: str
    provider: str
    latency_ms: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Optional[Any] = None


class LLMProvider(ABC):
    """
    Abstract interface for LLM/SLM providers.
    Enables hot-swapping between OpenAI, Groq, local SLMs (Ollama/vLLM),
    and offline mock providers without code changes.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = True,
        temperature: float = 0.1,
        max_tokens: int = 1500
    ) -> LLMResponse:
        """
        Submits prompt to LLM and returns standardized response.
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass
