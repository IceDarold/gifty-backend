from typing import Dict, Type
import logging

from app.config import get_settings
from app.core.logic_config import logic_config
from app.services.llm.interface import LLMClient
from app.services.llm.anthropic_client import AnthropicClient
from app.services.llm.gemini_client import GeminiClient
from app.services.llm.groq_client import GroqClient
from app.services.llm.openrouter_client import OpenRouterClient
from app.services.llm.together_client import TogetherClient

logger = logging.getLogger(__name__)


class LLMFactory:
    """
    Factory for creating LLM clients based on configuration.
    Supported providers: anthropic, gemini, groq, openrouter, together
    """
    _clients: Dict[str, Type[LLMClient]] = {
        "anthropic": AnthropicClient,
        "gemini": GeminiClient,
        "groq": GroqClient,
        "openrouter": OpenRouterClient,
        "together": TogetherClient,
    }

    @staticmethod
    def get_client(provider: str = None) -> LLMClient:
        """
        Returns an instance of the configured LLM client.
        """
        settings = get_settings()
        # Prioritize Settings (ENV) over logic_config (YAML) for the default provider
        # but allow manual override via the 'provider' parameter.
        provider = provider or settings.llm_provider or logic_config.llm.default_provider
        
        client_class = LLMFactory._clients.get(provider.lower())
        
        if not client_class:
            logger.warning(f"Unknown LLM provider '{provider}', falling back to Anthropic.")
            client_class = AnthropicClient
            
        return client_class()
