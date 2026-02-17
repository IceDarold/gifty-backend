from typing import List, Optional, Any
from anthropic import AsyncAnthropic
import logging

from app.services.llm.interface import LLMClient, Message, LLMResponse

logger = logging.getLogger(__name__)

class AnthropicClient(LLMClient):
    """
    Adapter for Anthropic API.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.client = AsyncAnthropic(api_key=api_key)

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
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
            
            return LLMResponse(
                content=content,
                raw_response=response,
                usage=usage
            )

        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise
