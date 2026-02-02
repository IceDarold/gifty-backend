import httpx
import logging
from typing import List, Dict, Any, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)

class IntelligenceService:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.intelligence_api_base.rstrip("/")
        self.token = settings.intelligence_api_token
        self.timeout = 30.0

    async def classify_categories(
        self, 
        external_names: List[str], 
        internal_categories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calls external API to map external category names to internal category IDs.
        """
        if not external_names:
            return []

        url = f"{self.base_url}/v1/classify/categories"
        payload = {
            "external_names": external_names,
            "internal_categories": internal_categories
        }
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data.get("mappings", [])
        except Exception as e:
            logger.error(f"Intelligence API Error (classify_categories): {e}")
            return []

    async def score_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls external API to get giftability score and reasoning.
        """
        url = f"{self.base_url}/v1/products/score"
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=product_data, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Intelligence API Error (score_product): {e}")
            return {}
