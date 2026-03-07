from typing import List, Optional, Any
from anthropic import AsyncAnthropic
import logging

from app.services.llm.interface import (
    LLMClient,
    Message,
    LLMResponse,
    extract_finish_reason,
    extract_provider_request_id,
    normalize_usage,
    serialize_raw_response,
)
from app.services.llm.proxy import build_async_client
from app.config import get_settings

logger = logging.getLogger(__name__)

class AnthropicClient(LLMClient):
    """
    Adapter for Anthropic API.
    """
    def __init__(self, api_key: Optional[str] = None):
        if not api_key:
            settings = get_settings()
            api_key = settings.anthropic_api_key

        proxy_url = get_settings().llm_proxy_url
        http_client = build_async_client(proxy_url) if proxy_url else None
        self.client = AsyncAnthropic(api_key=api_key, http_client=http_client)

    async def generate_text(
        self, 
        messages: List[Message], 
        model: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stops: Optional[List[str]] = None,
        json_mode: bool = False
    ) -> LLMResponse:
        """
        Generates text using Anthropic API.
        """
        try:
            # Prepare arguments
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
                
            if stops:
                kwargs["stop_sequences"] = stops

            # Only add extra headers if needed, Anthropic doesn't have a specific 'json_mode' param 
            # in the same way OpenAI does, but we can hint via prompt or prefill. 
            # Here we just execute the call.
            
            response = await self.client.messages.create(**kwargs)
            
            content = response.content[0].text
            raw_response = serialize_raw_response(response)
            usage = normalize_usage(response.usage, raw_response)
            
            return LLMResponse(
                content=content,
                raw_response=raw_response,
                usage=usage,
                provider_request_id=extract_provider_request_id(raw_response),
                finish_reason=extract_finish_reason(raw_response),
            )

        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise
