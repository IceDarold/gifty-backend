import asyncio
import logging
from typing import List, Optional

import httpx

from app.services.llm.interface import LLMClient, Message, LLMResponse
from app.config import get_settings

logger = logging.getLogger(__name__)

GROQ_API_BASE = "https://api.groq.com/openai/v1/chat/completions"
MAX_RETRIES = 3
INITIAL_BACKOFF = 5  # seconds


class GroqClient(LLMClient):
    """Groq Cloud LLM client adapter (OpenAI-compatible API)."""

    def __init__(self):
        settings = get_settings()
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY not configured")
        self.api_key = settings.groq_api_key

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
        # Map Anthropic model names → Groq equivalents
        model_mapping = {
            "claude-3-haiku-20240307": "llama-3.3-70b-versatile",
            "claude-haiku-4-5": "llama-3.3-70b-versatile",
            "claude-3-5-sonnet-20240620": "llama-3.3-70b-versatile",
            "claude-opus-4-6": "llama-3.3-70b-versatile",
        }
        groq_model = model_mapping.get(model, "llama-3.3-70b-versatile")

        # Build messages list
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": groq_model,
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
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(GROQ_API_BASE, json=payload, headers=headers)
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
                if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                    wait = INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(f"Groq rate-limited (429), retrying in {wait}s (attempt {attempt+1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)
                else:
                    raise

        raise last_error
