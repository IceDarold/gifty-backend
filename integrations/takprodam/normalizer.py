from __future__ import annotations

from typing import Any, Optional

from .models import GiftCandidate


def _first_str(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(" ", "").replace(",", ".")
        if "-" in cleaned:
            parts = [p for p in cleaned.split("-") if p]
            if parts:
                return _parse_price(parts[0])
        try:
            return float(cleaned)
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("min", "from", "price_from", "min_price"):
            if key in value:
                return _parse_price(value.get(key))
        for key in ("max", "to", "price_to", "max_price"):
            if key in value:
                return _parse_price(value.get(key))
        return None
    if isinstance(value, (list, tuple)) and value:
        return _parse_price(value[0])
    return None


def _extract_image(tp_product: dict[str, Any]) -> Optional[str]:
    direct = _first_str(tp_product.get("image_url"), tp_product.get("image"), tp_product.get("imageUrl"))
    if direct:
        return direct

    images = tp_product.get("images") or tp_product.get("photos")
    if isinstance(images, list):
        for item in images:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                candidate = _first_str(item.get("url"), item.get("image_url"), item.get("src"))
                if candidate:
                    return candidate
    return None


def _extract_category(tp_product: dict[str, Any]) -> Optional[str]:
    category = tp_product.get("product_category") or tp_product.get("category")
    if isinstance(category, dict):
        return _first_str(category.get("title"), category.get("name"))
    return _first_str(category)


def _extract_merchant(tp_product: dict[str, Any]) -> Optional[str]:
    return _first_str(
        tp_product.get("merchant"),
        tp_product.get("store_title"),
        tp_product.get("marketplace_title"),
        tp_product.get("store"),
    )


def _extract_link(tp_product: dict[str, Any]) -> Optional[str]:
    return _first_str(
        tp_product.get("tracking_link"),
        tp_product.get("deeplink"),
        tp_product.get("deeplink_url"),
        tp_product.get("trackingLink"),
        tp_product.get("external_link"),
        tp_product.get("url"),
    )


def normalize_product(tp_product: dict[str, Any]) -> GiftCandidate | None:
    if not isinstance(tp_product, dict):
        return None

    title = _first_str(tp_product.get("title"), tp_product.get("name"))
    product_url = _extract_link(tp_product)
    if not title or not product_url:
        return None

    product_id = _first_str(tp_product.get("id"), tp_product.get("product_id"), tp_product.get("product_sku"))
    if not product_id:
        return None

    description = _first_str(tp_product.get("description"), tp_product.get("details"))
    price = _parse_price(tp_product.get("price") or tp_product.get("price_range"))
    currency = _first_str(tp_product.get("currency"), tp_product.get("price_currency"))
    image_url = _extract_image(tp_product)
    category = _extract_category(tp_product)
    merchant = _extract_merchant(tp_product)

    return GiftCandidate(
        gift_id=f"takprodam:{product_id}",
        title=title,
        description=description,
        price=price,
        currency=currency,
        image_url=image_url,
        product_url=product_url,
        merchant=merchant,
        category=category,
        raw=tp_product,
    )
