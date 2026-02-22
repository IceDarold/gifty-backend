import asyncio
import logging
from typing import List, Optional

import httpx

from app.services.llm.interface import LLMClient, Message, LLMResponse
from app.services.llm.proxy import build_async_client
from app.config import get_settings

logger = logging.getLogger(__name__)

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1/chat/completions"
MAX_RETRIES = 3
INITIAL_BACKOFF = 5  # seconds


class OpenRouterClient(LLMClient):
    """OpenRouter LLM client adapter (OpenAI-compatible API, multi-model gateway)."""

    def __init__(self):
        settings = get_settings()
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")
        self.api_key = settings.openrouter_api_key
        self.proxy_url = settings.llm_proxy_url

    async def generate_text(
        self,
        messages: List[Message],
        model: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stops: Optional[List[str]] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        # Map Anthropic model names → OpenRouter model ids
        model_mapping = {
            "claude-3-haiku-20240307": "google/gemini-2.5-flash",
            "claude-haiku-4-5": "google/gemini-2.5-flash",
            "claude-3-5-sonnet-20240620": "google/gemini-2.5-pro",
            "claude-opus-4-6": "google/gemini-2.5-pro",
        }
        or_model = model_mapping.get(model, "google/gemini-2.5-flash")

        # Build messages list
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": or_model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stops:
            payload["stop"] = stops
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://giftyai.ru",
            "X-Title": "GiftyAI",
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with build_async_client(self.proxy_url) as client:
                    resp = await client.post(OPENROUTER_API_BASE, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()

                choice = data["choices"][0]
                content = choice["message"]["content"]
                usage_data = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    raw_response=data,
                    usage={
                        "input_tokens": usage_data.get("prompt_tokens", 0),
                        "output_tokens": usage_data.get("completion_tokens", 0),
                    },
                )
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_error = e
                # Retry on 429 or 529 (overloaded)
                status_code = getattr(e.response, "status_code", 0) if hasattr(e, "response") else 0
                if (status_code in (429, 529) or isinstance(e, httpx.RequestError)) and attempt < MAX_RETRIES - 1:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(f"OpenRouter error ({status_code or 'network'}), retrying in {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)
                else:
                    raise

        raise last_error
