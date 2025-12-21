from __future__ import annotations

from typing import Optional

from .client import TakprodamClient
from .models import GiftCandidate
from .normalizer import normalize_product


def search_gift_candidates(
    query: str,
    limit: int = 50,
    source_id: Optional[int] = None,
) -> list[GiftCandidate]:
    client = TakprodamClient()
    products = client.search_products(query=query, limit=limit, source_id=source_id)

    candidates: list[GiftCandidate] = []
    for product in products:
        normalized = normalize_product(product)
        if normalized is not None:
            candidates.append(normalized)

    return candidates
