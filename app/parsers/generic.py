from __future__ import annotations
import json
import logging
from bs4 import BeautifulSoup
from typing import Optional, Any
from app.parsers.base import BaseParser
from app.parsers.schemas import ParsedProduct

logger = logging.getLogger(__name__)

class GenericParser(BaseParser):
    async def parse(self, url: str) -> ParsedProduct:
        html = await self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        
        data = {
            "title": self._extract_title(soup),
            "description": self._extract_description(soup),
            "price": self._extract_price(soup),
            "currency": self._extract_currency(soup),
            "image_url": self._extract_image(soup),
            "product_url": url,
            "merchant": self._extract_merchant(soup, url),
            "category": self._extract_category(soup),
            "raw_data": {"source": "generic_metadata"}
        }
        
        # Try JSON-LD as a primary source of truth if available
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            data.update(self._map_json_ld(json_ld))
            data["raw_data"]["json_ld"] = json_ld

        return ParsedProduct(**data)

    def _extract_title(self, soup: BeautifulSoup) -> str:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            return og_title["content"]
        
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
            
        return soup.title.string if soup.title else "Untitled"

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            return og_desc["content"]
        
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            return meta_desc["content"]
            
        return None

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        og_image = soup.find("meta", property="og:image")
        if og_image:
            return og_image["content"]
        return None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        # Try OpenGraph price
        price_meta = soup.find("meta", property="product:price:amount")
        if price_meta:
            try:
                return float(price_meta["content"])
            except (ValueError, TypeError):
                pass
        return None

    def _extract_currency(self, soup: BeautifulSoup) -> str:
        curr_meta = soup.find("meta", property="product:price:currency")
        if curr_meta:
            return curr_meta["content"]
        return "RUB"

    def _extract_merchant(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        site_name = soup.find("meta", property="og:site_name")
        if site_name:
            return site_name["content"]
        
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        return domain.replace("www.", "")

    def _extract_category(self, soup: BeautifulSoup) -> Optional[str]:
        # Very naive category extraction
        return None

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[dict[str, Any]]:
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                # We are looking for Product type
                if isinstance(data, dict) and data.get("@type") == "Product":
                    return data
                elif isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            return item
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _map_json_ld(self, data: dict[str, Any]) -> dict[str, Any]:
        """Maps Schema.org Product to our internal format."""
        mapped = {}
        if data.get("name"):
            mapped["title"] = data["name"]
        if data.get("description"):
            mapped["description"] = data["description"]
        if data.get("image"):
            img = data["image"]
            mapped["image_url"] = img[0] if isinstance(img, list) else img
            
        offers = data.get("offers")
        if offers:
            if isinstance(offers, list):
                offers = offers[0]
            if offers.get("price"):
                try:
                    mapped["price"] = float(offers["price"])
                except (ValueError, TypeError):
                    pass
            if offers.get("priceCurrency"):
                mapped["currency"] = offers["priceCurrency"]
                
        return mapped
