import asyncio
import logging
from typing import List, Optional

import httpx

from app.services.llm.interface import LLMClient, Message, LLMResponse
from app.config import get_settings

logger = logging.getLogger(__name__)

TOGETHER_API_BASE = "https://api.together.xyz/v1/chat/completions"
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds


class TogetherClient(LLMClient):
    """Together AI LLM client adapter (OpenAI-compatible API)."""

    def __init__(self):
        settings = get_settings()
        if not settings.together_api_key:
            raise ValueError("TOGETHER_API_KEY not configured")
        self.api_key = settings.together_api_key

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
        # Default model if something unknown is passed (can be customized)
        model_mapping = {
            "claude-3-haiku-20240307": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "claude-3-5-sonnet-20240620": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        }
        together_model = model_mapping.get(model, model if "/" in model else "meta-llama/Llama-3.3-70B-Instruct-Turbo")

        # Build messages list
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": together_model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stops:
            payload["stop"] = stops
        # Together AI supports json mode via response_format
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(TOGETHER_API_BASE, json=payload, headers=headers)
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
            except httpx.HTTPStatusError as e:
                last_error = e
                # Rate limit handling
                if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(f"Together AI rate-limited (429), retrying in {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Together AI error: {e.response.text}")
                    raise
            except Exception as e:
                logger.error(f"Together AI unexpected error: {e}")
                last_error = e
                if attempt == MAX_RETRIES - 1:
                    raise

        raise last_error
