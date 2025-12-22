from __future__ import annotations

from integrations.takprodam.models import GiftCandidate

from .models import GiftDTO


def candidate_to_dto(candidate: GiftCandidate) -> GiftDTO:
    return GiftDTO(
        id=candidate.gift_id,
        title=candidate.title,
        description=candidate.description,
        price=candidate.price,
        currency=candidate.currency,
        image_url=candidate.image_url,
        product_url=candidate.product_url,
        merchant=candidate.merchant,
        category=candidate.category,
    )
