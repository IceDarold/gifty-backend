from __future__ import annotations
from urllib.parse import urlparse
from typing import Type
from app.parsers.base import BaseParser
from app.parsers.generic import GenericParser

from app.parsers.sites.mrgeek import MrGeekParser

# Dictionary map: domain -> ParserClass
PARSER_REGISTRY: dict[str, Type[BaseParser]] = {
    "mrgeek.ru": MrGeekParser,
}

class ParserFactory:
    @staticmethod
    def get_parser(url: str) -> BaseParser:
        domain = urlparse(url).netloc.replace("www.", "")
        
        parser_class = PARSER_REGISTRY.get(domain)
        if parser_class:
            return parser_class()
        
        # Fallback to generic
        return GenericParser()
