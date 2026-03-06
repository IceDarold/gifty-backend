from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@pytest.fixture
def _set_bot_token(monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "telegram_bot_token", "token", raising=False)
    return None


def test_webapp_auth_returns_500_when_bot_token_missing(client, monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "telegram_bot_token", None, raising=False)
    resp = client.post("/api/v1/internal/webapp/auth", json={"init_data": "x"})
    assert resp.status_code == 500


def test_webapp_auth_dev_bypass_success(client, _set_bot_token, monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "env", "dev", raising=False)
    repo = SimpleNamespace(
        get_subscriber=AsyncMock(
            return_value=SimpleNamespace(chat_id=1821014162, name="Dev", role="admin", permissions=["x"])
        )
    )
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)

    # Empty init_data triggers dev fallback user.
    resp = client.post("/api/v1/internal/webapp/auth", json={"init_data": ""})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["user"]["id"] == 1821014162


def test_webapp_auth_prod_invalid_signature_forbidden(client, _set_bot_token, monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "env", "prod", raising=False)
    monkeypatch.setattr(internal_routes, "verify_telegram_init_data", lambda init_data, token: False, raising=True)
    resp = client.post("/api/v1/internal/webapp/auth", json={"init_data": "user=%7B%22id%22%3A1%7D"})
    assert resp.status_code == 403


def test_webapp_auth_prod_missing_user_id_400(client, _set_bot_token, monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "env", "prod", raising=False)
    monkeypatch.setattr(internal_routes, "verify_telegram_init_data", lambda init_data, token: True, raising=True)
    resp = client.post("/api/v1/internal/webapp/auth", json={"init_data": "user=%7B%7D"})
    assert resp.status_code == 400


def test_webapp_auth_access_denied_for_non_admin(client, _set_bot_token, monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "env", "prod", raising=False)
    monkeypatch.setattr(internal_routes, "verify_telegram_init_data", lambda init_data, token: True, raising=True)
    repo = SimpleNamespace(get_subscriber=AsyncMock(return_value=SimpleNamespace(chat_id=1, name="U", role="user", permissions=[])))
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)
    resp = client.post("/api/v1/internal/webapp/auth", json={"init_data": "user=%7B%22id%22%3A1%7D"})
    assert resp.status_code == 403


class _FakeMappingsResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)


def test_products_endpoint_enriches_categories(fake_db, client, monkeypatch):
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    products = [
        SimpleNamespace(
            product_id="site:1",
            title="t",
            description="d",
            price=1.5,
            currency="RUB",
            image_url="i",
            product_url="u",
            merchant="m",
            category=None,
            is_active=True,
            created_at=now,
            updated_at=now,
            site_key="site",
        )
    ]

    class _Repo:
        def __init__(self, db):
            self.db = db

        async def get_products(self, **kwargs):
            return products

        async def count_products(self, **kwargs):
            return 1

    # imported inside handler
    import app.repositories.catalog as catalog_mod

    monkeypatch.setattr(catalog_mod, "PostgresCatalogRepository", _Repo, raising=True)

    fake_db.execute = AsyncMock(
        side_effect=[
            _FakeMappingsResult([{"product_id": "site:1", "cnt": 2}]),
            _FakeMappingsResult(
                [
                    {
                        "product_id": "site:1",
                        "category_id": 10,
                        "category_name": "C",
                        "category_url": "http://c",
                        "last_seen_at": now,
                    }
                ]
            ),
        ]
    )

    resp = client.get("/api/v1/internal/products")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["scraped_categories_count"] == 2
    assert body["items"][0]["scraped_category"]["id"] == 10


def test_merchants_list_and_update(fake_db, client):
    from app.models import Merchant

    # list_merchants: first execute returns scalars().all(), second returns scalar()
    class _Res:
        def __init__(self, rows=None, scalar=None):
            self._rows = rows or []
            self._scalar = scalar

        def scalars(self):
            return SimpleNamespace(all=lambda: list(self._rows))

        def scalar(self):
            return self._scalar

        def scalar_one_or_none(self):
            return self._rows[0] if self._rows else None

    fake_db.execute = AsyncMock(
        side_effect=[
            _Res(rows=[Merchant(site_key="a", name="A")]),
            _Res(scalar=1),
            _Res(rows=[]),  # update_merchant fetch existing: none
        ]
    )
    fake_db.flush = AsyncMock()
    fake_db.commit = AsyncMock()
    fake_db.add = lambda obj: None

    resp = client.get("/api/v1/internal/merchants", params={"q": "a"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    bad = client.patch("/api/v1/internal/merchants/   ", json={"name": "x"})
    assert bad.status_code == 400

    ok = client.patch("/api/v1/internal/merchants/site", json={"name": "X", "base_url": "http://x"})
    assert ok.status_code == 200
    assert ok.json()["item"]["site_key"] == "site"
