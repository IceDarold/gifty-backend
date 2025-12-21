import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from integrations.takprodam.normalizer import normalize_product
from integrations.takprodam.search import search_gift_candidates
from integrations.takprodam.client import TakprodamClient


def test_normalize_product_full():
    product = {
        "id": "123",
        "title": "Плед",
        "description": "Мягкий плед",
        "price": "1999.50",
        "currency": "RUB",
        "image_url": "https://example.com/img.jpg",
        "tracking_link": "https://tracking.example.com/123",
        "store_title": "Shop",
        "product_category": "Текстиль",
    }

    candidate = normalize_product(product)

    assert candidate is not None
    assert candidate.gift_id == "takprodam:123"
    assert candidate.title == "Плед"
    assert candidate.description == "Мягкий плед"
    assert candidate.price == 1999.50
    assert candidate.currency == "RUB"
    assert candidate.image_url == "https://example.com/img.jpg"
    assert candidate.product_url == "https://tracking.example.com/123"
    assert candidate.merchant == "Shop"
    assert candidate.category == "Текстиль"
    assert candidate.raw == product


def test_normalize_product_without_image():
    product = {
        "id": "124",
        "title": "Книга",
        "tracking_link": "https://tracking.example.com/124",
        "price": 500,
        "currency": "RUB",
    }

    candidate = normalize_product(product)

    assert candidate is not None
    assert candidate.image_url is None


def test_normalize_product_without_link():
    product = {
        "id": "125",
        "title": "Кружка",
    }

    candidate = normalize_product(product)

    assert candidate is None


def test_search_gift_candidates_empty(monkeypatch):
    def _empty_search(self, query, limit=50, offset=0, source_id=None):
        return []

    monkeypatch.setattr(TakprodamClient, "search_products", _empty_search)

    results = search_gift_candidates("плед")

    assert results == []
