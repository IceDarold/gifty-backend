import asyncio
import logging
from typing import List, Optional

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from app.services.llm.interface import (
    LLMClient,
    Message,
    LLMResponse,
    extract_finish_reason,
    extract_provider_request_id,
    normalize_usage,
    serialize_raw_response,
)
from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 12  # seconds


class GeminiClient(LLMClient):
    """Google Gemini LLM client adapter using the google.genai package."""
    
    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        self.client = genai.Client(api_key=settings.gemini_api_key)
    
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
        # Map Anthropic model names → Gemini equivalents
        model_mapping = {
            "claude-3-haiku-20240307": "gemini-2.5-flash",
            "claude-haiku-4-5": "gemini-2.5-flash",
            "claude-3-5-sonnet-20240620": "gemini-2.5-pro",
            "claude-opus-4-6": "gemini-2.5-pro",
        }
        gemini_model = model_mapping.get(model, "gemini-2.5-flash")
        
        # Build generation config
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_prompt if system_prompt else None,
            stop_sequences=stops if stops else None,
        )
        
        if json_mode:
            config.response_mime_type = "application/json"
        
        # Convert messages to Gemini format
        gemini_contents = []
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            gemini_contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg.content)]
                )
            )
        
        # Retry with exponential backoff on rate-limit errors
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=gemini_model,
                    contents=gemini_contents,
                    config=config
                )
                
                content = response.text
                
                raw_response = serialize_raw_response(response)
                usage = {}
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    usage = normalize_usage({
                        "prompt_token_count": getattr(response.usage_metadata, 'prompt_token_count', 0),
                        "completion_token_count": getattr(response.usage_metadata, 'candidates_token_count', 0),
                        "total_token_count": getattr(response.usage_metadata, 'total_token_count', 0),
                    }, raw_response)
                
                return LLMResponse(
                    content=content,
                    raw_response=raw_response,
                    usage=usage,
                    provider_request_id=extract_provider_request_id(raw_response),
                    finish_reason=extract_finish_reason(raw_response),
                )
            except ClientError as e:
                last_error = e
                if e.code == 429 and attempt < MAX_RETRIES - 1:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(f"Gemini rate-limited (429), retrying in {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Gemini API error: {e}")
                    raise
        
        raise last_error  # should not reach here
