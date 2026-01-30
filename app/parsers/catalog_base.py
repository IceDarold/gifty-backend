from __future__ import annotations
import abc
from app.parsers.base import BaseParser
from app.parsers.schemas import ParsedCatalog

class BaseCatalogParser(BaseParser, abc.ABC):
    @abc.abstractmethod
    async def parse_catalog(self, url: str) -> ParsedCatalog:
        """Parse a list of products from a catalog/listing page."""
        pass
