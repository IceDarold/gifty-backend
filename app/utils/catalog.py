from __future__ import annotations
import hashlib

def build_content_text(item: dict) -> str:
    """
    Build stable content text for embedding: title + category + description + merchant.
    This supports both raw Takprodam dicts and normalized models.
    """
    parts = [
        item.get("title") or "",
        item.get("product_category") or item.get("category_name") or item.get("category") or "",
        item.get("description") or "",
        item.get("store_title") or item.get("merchant_name") or item.get("merchant") or "",
    ]
    # Clean and join
    clean_parts = [str(p).strip() for p in parts if p and str(p).strip()]
    return " ".join(clean_parts)[:4000]

def build_content_hash(text: str, image_url: Optional[str] = None) -> str:
    """sha256(content_text + (image_url or ""))"""
    combined = f"{text}|{image_url or ''}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
