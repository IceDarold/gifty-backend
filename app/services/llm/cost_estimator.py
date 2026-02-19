import httpx
import logging
import time
import asyncio
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# Fallback prices per 1M tokens (used if API fails or model not found)
FALLBACK_PRICES = {
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gemini-1.5-pro": {"input": 1.25, "output": 3.75},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
    "llama-3-70b": {"input": 0.6, "output": 0.6},
    "llama-3-8b": {"input": 0.05, "output": 0.05}
}

class PriceRegistry:
    """
    Registry for LLM prices with real-time updates from OpenRouter API.
    """
    _instance = None
    _prices: Dict[str, Dict[str, float]] = {}
    _last_updated = 0
    _update_interval = 3600 * 24  # Update once a day
    _fetching_lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PriceRegistry, cls).__new__(cls)
        return cls._instance

    async def _fetch_remote_prices(self):
        """Fetches prices from OpenRouter API."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://openrouter.ai/api/v1/models")
                if response.status_code == 200:
                    data = response.json()
                    new_prices = {}
                    for model in data.get("data", []):
                        model_id = model.get("id", "")
                        pricing = model.get("pricing", {})
                        if model_id and pricing:
                            # OpenRouter returns pricing per token, convert to per 1M tokens
                            new_prices[model_id] = {
                                "input": float(pricing.get("prompt", 0)) * 1_000_000,
                                "output": float(pricing.get("completion", 0)) * 1_000_000
                            }
                    if new_prices:
                        self._prices = new_prices
                        self._last_updated = time.time()
                        logger.info(f"LLM Price Registry updated with {len(new_prices)} models.")
        except Exception as e:
            logger.error(f"Failed to fetch LLM prices from OpenRouter: {e}")

    async def get_prices_for_model(self, model: str) -> Dict[str, float]:
        """Returns input/output prices for a given model."""
        # 1. Check if we need to update
        if time.time() - self._last_updated > self._update_interval:
            async with self._fetching_lock:
                # Double-check inside lock
                if time.time() - self._last_updated > self._update_interval:
                    await self._fetch_remote_prices()

        # 2. Try exact match from remote
        if model in self._prices:
            return self._prices[model]

        # 3. Try fuzzy match from remote or fallbacks
        model_lower = model.lower()
        
        # Search in remote first
        for m_id, p in self._prices.items():
            if m_id.lower() in model_lower or model_lower in m_id.lower():
                return p

        # Search in fallbacks
        for m_id, p in FALLBACK_PRICES.items():
            if m_id.lower() in model_lower:
                return p

        # 4. Final fallback
        return {"input": 0.5, "output": 1.5}

_registry = PriceRegistry()

async def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Returns estimated cost in USD for a given model and token usage.
    Asynchronously fetches real-time prices if needed.
    """
    prices = await _registry.get_prices_for_model(model)
    
    input_cost = (prompt_tokens / 1_000_000) * prices["input"]
    output_cost = (completion_tokens / 1_000_000) * prices["output"]
    
    return round(input_cost + output_cost, 6)
