import logging
from typing import Optional

from backend.app.core.config import settings
from backend.app.rag.llm.base import LLMProvider
from backend.app.rag.llm.mock import MockLLMProvider
from backend.app.rag.llm.mistral_provider import MistralProvider
from backend.app.rag.llm.openai_provider import OpenAIProvider
from backend.app.rag.llm.groq_provider import GroqProvider
from backend.app.rag.llm.local_slm_provider import LocalSLMProvider

logger = logging.getLogger(__name__)


def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Factory resolving LLM provider instance from settings or explicit selection:
    - 'mistral': Mistral AI API (e.g. ministral-8b-latest, mistral-small-latest)
    - 'mock': Offline deterministic simulator
    - 'local' / 'ollama': Local SLM inference server
    - 'openai': OpenAI API
    - 'groq': Groq high-speed API
    """
    target = (provider_name or settings.LLM_PROVIDER or "mock").lower()

    if target == "mistral":
        if settings.MISTRAL_API_KEY:
            return MistralProvider()
        logger.warning("MISTRAL_API_KEY missing. Falling back to mock provider.")
        return MockLLMProvider()

    elif target == "openai":
        if settings.OPENAI_API_KEY:
            return OpenAIProvider()
        logger.warning("OPENAI_API_KEY missing. Falling back to mock provider.")
        return MockLLMProvider()

    elif target == "groq":
        if settings.GROQ_API_KEY:
            return GroqProvider()
        logger.warning("GROQ_API_KEY missing. Falling back to mock provider.")
        return MockLLMProvider()

    elif target in ["local", "ollama", "slm"]:
        return LocalSLMProvider()

    elif target == "mock":
        return MockLLMProvider()

    else:
        logger.warning(f"Unrecognized LLM provider '{target}'. Using MockLLMProvider.")
        return MockLLMProvider()

