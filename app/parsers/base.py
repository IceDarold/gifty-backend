from __future__ import annotations
import abc
import httpx
from typing import Optional
from app.parsers.schemas import ParsedProduct

class BaseParser(abc.ABC):
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text

    @abc.abstractmethod
    async def parse(self, url: str) -> ParsedProduct:
        """Main entry point to fetch and parse a product URL."""
        pass
