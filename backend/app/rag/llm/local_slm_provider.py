import time
import logging
from typing import Optional, Dict, Any

from backend.app.core.config import settings
from backend.app.rag.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class LocalSLMProvider(LLMProvider):
    """
    Local Small Language Model (SLM) adapter.
    Interfaces with Ollama, vLLM, LM Studio, or local inference servers
    exposing OpenAI-compatible endpoints (e.g. Qwen 2.5, Llama 3.2, Gemma 2).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.base_url = base_url or settings.LOCAL_SLM_BASE_URL
        self.model = model or settings.LOCAL_SLM_MODEL
        self._client = None

    @property
    def provider_name(self) -> str:
        return "local_slm"

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self.base_url,
                api_key="local-no-key-required"
            )
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = True,
        temperature: float = 0.1,
        max_tokens: int = 1500
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        start = time.time()
        try:
            resp = self.client.chat.completions.create(**kwargs)
            latency = (time.time() - start) * 1000

            choice = resp.choices[0]
            content = choice.message.content or ""
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                "total_tokens": resp.usage.total_tokens if resp.usage else 0
            }

            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                latency_ms=round(latency, 2),
                token_usage=usage,
                raw_response=resp
            )
        except Exception as e:
            logger.error(f"Local SLM ({self.base_url}) generation error: {e}")
            raise ConnectionError(
                f"Could not connect to Local SLM server at {self.base_url}: {e}"
            )
