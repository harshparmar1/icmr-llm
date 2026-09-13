import time
import logging
from typing import Optional, Dict, Any

from backend.app.core.config import settings
from backend.app.rag.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """
    Groq API adapter for ultra-fast Llama-3 / open-weight models.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self._client = None

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("GROQ_API_KEY is not configured in environment variables.")
            from openai import OpenAI
            self._client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.api_key
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
            logger.error(f"Groq generation error: {e}")
            raise e
