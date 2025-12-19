import os
import time
import hmac
import json
import hashlib
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

TAKPRODAM_BASE = "https://api.takprodam.ru/v2/publisher"
API_TOKEN = os.getenv("TAKPRODAM_API_TOKEN", "").strip()
SOURCE_ID = os.getenv("TAKPRODAM_SOURCE_ID", "").strip()
DB_PATH = os.getenv("DB_PATH", "./gifty_takprodam.sqlite").strip()

if not API_TOKEN:
    raise RuntimeError("TAKPRODAM_API_TOKEN is missing in env")
if not SOURCE_ID:
    raise RuntimeError("TAKPRODAM_SOURCE_ID is missing in env")


# -----------------------------
# Takprodam client
# -----------------------------
@dataclass
class TakprodamClient:
    api_token: str
    base_url: str = TAKPRODAM_BASE
    timeout_s: int = 30

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        r = requests.get(url, headers=self._headers(), params=params or {}, timeout=self.timeout_s)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Takprodam error {r.status_code}: {r.text}")
        return r.json()

    # 1) Площадки
    def get_sources(self) -> List[Dict[str, Any]]:
        data = self._get("/source/")
        return data.get("items", [])

    # 2) Категории
    def get_categories(self) -> List[Dict[str, Any]]:
        data = self._get("/product-category/")
        return data.get("items", [])

    # 3) Товары с партнёрскими ссылками
    def get_products_with_links(
        self,
        source_id: str,
        page: int = 1,
        limit: int = 200,
        marketplace: Optional[str] = None,
        category_id: Optional[int] = None,
        payment_type: Optional[str] = None,
        favorite: Optional[bool] = None,
        subid: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"source_id": source_id, "page": page, "limit": limit}
        if marketplace:
            params["marketplace"] = marketplace
        if category_id is not None:
            params["category_id"] = category_id
        if payment_type:
            params["payment_type"] = payment_type
        if favorite is not None:
            params["favorite"] = str(favorite).lower()
        if subid:
            params["subid"] = subid  # Takprodam умеет прокидывать subid для атрибуции. :contentReference[oaicite:1]{index=1}

        return self._get("/product/", params=params)

    # 4) Акции/промокоды
    def get_promotions(
        self,
        source_id: str,
        page: int = 1,
        limit: int = 200,
        marketplace: Optional[str] = None,
        promotion_type: Optional[str] = None,
        favorite: Optional[bool] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"source_id": source_id, "page": page, "limit": limit}
        if marketplace:
            params["marketplace"] = marketplace
        if promotion_type:
            params["promotion_type"] = promotion_type
        if favorite is not None:
            params["favorite"] = str(favorite).lower()
        return self._get("/promotion/", params=params)

    # 5) Товары внутри акции
    def get_promotion_products(
        self,
        source_id: str,
        promotion_id: int,
        page: int = 1,
        limit: int = 200,
        marketplace: Optional[str] = None,
        category_id: Optional[int] = None,
        subid: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "source_id": source_id,
            "promotion_id": promotion_id,
            "page": page,
            "limit": limit,
        }
        if marketplace:
            params["marketplace"] = marketplace
        if category_id is not None:
            params["category_id"] = category_id
        if subid:
            params["subid"] = subid
        return self._get("/promotion/product/", params=params)

    # 6) Комиссии и статусы заказов
    def get_commissions(
        self,
        source_id: str,
        page: int = 1,
        limit: int = 200,
        marketplace: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"source_id": source_id, "page": page, "limit": limit}
        if marketplace:
            params["marketplace"] = marketplace
        if status:
            params["status"] = status
        return self._get("/commission/", params=params)


# -----------------------------
# Storage (SQLite)
# -----------------------------
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        product_id INTEGER,
        product_sku TEXT,
        title TEXT,
        image_url TEXT,
        price REAL,
        commission REAL,
        product_category TEXT,
        marketplace_title TEXT,
        store_title TEXT,
        external_link TEXT,
        tracking_link TEXT,
        payment_type TEXT,
        favorite INTEGER,
        legal_text TEXT,
        updated_at INTEGER
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_products_title ON products(title);
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS promotions (
        id INTEGER PRIMARY KEY,
        title TEXT,
        promotion_type TEXT,
        marketplace_title TEXT,
        store_title TEXT,
        discount_type TEXT,
        discount_value REAL,
        start_date TEXT,
        end_date TEXT,
        coupon TEXT,
        landing_link TEXT,
        legal_text TEXT,
        updated_at INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER NOT NULL,
        product_id TEXT NOT NULL,
        gift_id TEXT,
        placement TEXT,
        subid TEXT,
        tracking_link TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS commissions (
        id TEXT PRIMARY KEY,
        status TEXT,
        commission_date TEXT,
        marketplace TEXT,
        subid TEXT,
        publisher_fee REAL,
        total_cart REAL,
        currency TEXT,
        raw_json TEXT,
        updated_at INTEGER
    )
    """)

    con.commit()
    con.close()


def upsert_categories(items: List[Dict[str, Any]]) -> None:
    con = db()
    cur = con.cursor()
    for it in items:
        cur.execute(
            "INSERT OR REPLACE INTO categories(id, title) VALUES(?, ?)",
            (int(it["id"]), str(it["title"])),
        )
    con.commit()
    con.close()


def upsert_products(items: List[Dict[str, Any]]) -> None:
    now = int(time.time())
    con = db()
    cur = con.cursor()

    for it in items:
        cur.execute(
            """
            INSERT OR REPLACE INTO products(
                id, product_id, product_sku, title, image_url, price, commission, product_category,
                marketplace_title, store_title, external_link, tracking_link, payment_type, favorite, legal_text, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(it.get("id")),
                it.get("product_id"),
                it.get("product_sku"),
                it.get("title"),
                it.get("image_url"),
                it.get("price"),
                it.get("commission"),
                it.get("product_category"),
                it.get("marketplace_title"),
                it.get("store_title"),
                it.get("external_link"),
                it.get("tracking_link"),  # партнёрская ссылка уже готова в ответе :contentReference[oaicite:2]{index=2}
                it.get("payment_type"),
                1 if it.get("favorite") else 0,
                it.get("legal_text"),      # маркировка рекламы :contentReference[oaicite:3]{index=3}
                now,
            ),
        )

    con.commit()
    con.close()


def upsert_promotions(items: List[Dict[str, Any]]) -> None:
    now = int(time.time())
    con = db()
    cur = con.cursor()

    for it in items:
        cur.execute(
            """
            INSERT OR REPLACE INTO promotions(
                id, title, promotion_type, marketplace_title, store_title,
                discount_type, discount_value, start_date, end_date, coupon, landing_link, legal_text, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(it.get("id")),
                it.get("title"),
                it.get("promotion_type"),
                it.get("marketplace_title"),
                it.get("store_title"),
                it.get("discount_type"),
                it.get("discount_value"),
                it.get("start_date"),
                it.get("end_date"),
                it.get("coupon"),
                it.get("landing_link"),
                it.get("legal_text"),
                now,
            ),
        )

    con.commit()
    con.close()


def upsert_commissions(items: List[Dict[str, Any]]) -> None:
    now = int(time.time())
    con = db()
    cur = con.cursor()
    for it in items:
        cid = str(it.get("id"))
        cur.execute(
            """
            INSERT OR REPLACE INTO commissions(
                id, status, commission_date, marketplace, subid, publisher_fee, total_cart, currency, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                it.get("status"),
                it.get("commission_date"),
                (it.get("order_product") or {}).get("marketplace_title") if isinstance(it.get("order_product"), dict) else it.get("marketplace"),
                it.get("subid"),  # subid приходит обратно в комиссиях :contentReference[oaicite:4]{index=4}
                it.get("publisher_fee"),
                it.get("total_cart"),
                it.get("currency"),
                json.dumps(it, ensure_ascii=False),
                now,
            ),
        )
    con.commit()
    con.close()


# -----------------------------
# Gifty-oriented helpers
# -----------------------------
def make_subid(gift_id: str, placement: str) -> str:
    # subid — твой “сквозной id” для аналитики: какие подборки/карточки реально продают
    # Можно сделать богаче: giftId|placement|ts|abVariant
    return f"gifty:{gift_id}:{placement}"


def add_subid_to_tracking_link(tracking_link: str, subid: str) -> str:
    # В API есть параметр subid в запросах, но на практике часто удобнее:
    # 1) хранить tracking_link
    # 2) на клике добавлять subid как параметр (если ссылка это допускает)
    # Это демо; в проде проверь, какой параметр Takprodam реально использует в tracking_link.
    sep = "&" if "?" in tracking_link else "?"
    return f"{tracking_link}{sep}subid={requests.utils.quote(subid)}"


# -----------------------------
# Sync jobs
# -----------------------------
def sync_categories(client: TakprodamClient) -> int:
    cats = client.get_categories()
    upsert_categories(cats)
    return len(cats)


def sync_products(client: TakprodamClient, source_id: str, marketplace: Optional[str] = None, max_pages: int = 20) -> int:
    total = 0
    page = 1
    while page <= max_pages:
        data = client.get_products_with_links(
            source_id=source_id,
            page=page,
            limit=200,
            marketplace=marketplace,
        )
        items = data.get("items", [])
        if not items:
            break
        upsert_products(items)
        total += len(items)
        page += 1

        total_count = data.get("total_count")
        limit = data.get("limit", 200)
        if isinstance(total_count, int) and total >= total_count:
            break

    return total


def sync_promotions(client: TakprodamClient, source_id: str, marketplace: Optional[str] = None, max_pages: int = 10) -> int:
    total = 0
    page = 1
    while page <= max_pages:
        data = client.get_promotions(source_id=source_id, page=page, limit=200, marketplace=marketplace)
        items = data.get("items", [])
        if not items:
            break
        upsert_promotions(items)
        total += len(items)
        page += 1

        total_count = data.get("total_count")
        if isinstance(total_count, int) and total >= total_count:
            break

    return total


def sync_commissions(client: TakprodamClient, source_id: str, marketplace: Optional[str] = None, max_pages: int = 10) -> int:
    total = 0
    page = 1
    while page <= max_pages:
        data = client.get_commissions(source_id=source_id, page=page, limit=200, marketplace=marketplace)
        items = data.get("items", [])
        if not items:
            break
        upsert_commissions(items)
        total += len(items)
        page += 1

        total_count = data.get("total_count")
        if isinstance(total_count, int) and total >= total_count:
            break

    return total


# -----------------------------
# FastAPI app (demo API for Gifty)
# -----------------------------
app = FastAPI(title="Gifty x Takprodam demo")
client = TakprodamClient(api_token=API_TOKEN)


class SyncResult(BaseModel):
    categories: int
    products: int
    promotions: int
    commissions: int


class GiftItem(BaseModel):
    id: str
    title: str
    image_url: Optional[str] = None
    price: Optional[float] = None
    commission: Optional[float] = None
    marketplace_title: Optional[str] = None
    store_title: Optional[str] = None
    tracking_link: Optional[str] = None
    legal_text: Optional[str] = None


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.post("/sync", response_model=SyncResult)
def run_sync(marketplace: Optional[str] = None) -> SyncResult:
    cats = sync_categories(client)
    prods = sync_products(client, SOURCE_ID, marketplace=marketplace)
    promos = sync_promotions(client, SOURCE_ID, marketplace=marketplace)
    comms = sync_commissions(client, SOURCE_ID, marketplace=marketplace)
    return SyncResult(categories=cats, products=prods, promotions=promos, commissions=comms)


@app.get("/gifts", response_model=List[GiftItem])
def list_gifts(q: Optional[str] = None, limit: int = 30) -> List[GiftItem]:
    con = db()
    cur = con.cursor()

    if q:
        cur.execute(
            """
            SELECT id, title, image_url, price, commission, marketplace_title, store_title, tracking_link, legal_text
            FROM products
            WHERE title LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (f"%{q}%", int(limit)),
        )
    else:
        cur.execute(
            """
            SELECT id, title, image_url, price, commission, marketplace_title, store_title, tracking_link, legal_text
            FROM products
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (int(limit),),
        )

    rows = cur.fetchall()
    con.close()

    return [GiftItem(**dict(r)) for r in rows]


@app.get("/buy/{product_id}")
def buy(product_id: str, gift_id: str = "unknown", placement: str = "default") -> Dict[str, Any]:
    """
    Это то, что будет дергаться на кнопке "Купить" в Gifty.
    Мы:
    - достаем tracking_link из базы
    - добавляем subid (gift_id + placement)
    - логируем клик
    - возвращаем redirect_url для фронта
    """
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, tracking_link, legal_text FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found in local catalog. Run /sync first.")
    tracking_link = row["tracking_link"]
    legal_text = row["legal_text"]
    if not tracking_link:
        raise HTTPException(status_code=400, detail="Product has no tracking_link")

    subid = make_subid(gift_id=gift_id, placement=placement)
    redirect_url = add_subid_to_tracking_link(tracking_link, subid)

    cur.execute(
        "INSERT INTO clicks(ts, product_id, gift_id, placement, subid, tracking_link) VALUES (?, ?, ?, ?, ?, ?)",
        (int(time.time()), product_id, gift_id, placement, subid, redirect_url),
    )
    con.commit()
    con.close()

    return {
        "redirect_url": redirect_url,
        "legal_text": legal_text,  # можно показывать возле кнопки/в футере карточки
        "subid": subid,
    }


@app.post("/webhook/takprodam")
async def takprodam_webhook(request: Request) -> Dict[str, Any]:
    """
    Демо-приёмник postback/webhook.
    Важно: в реальном проде почти всегда нужно:
    - проверять подпись/secret от Takprodam (если они выдают)
    - логировать raw payload
    Здесь мы просто складываем комиссии в БД.
    """
    payload = await request.json()

    # ожидаем либо один объект, либо список объектов
    items = payload if isinstance(payload, list) else [payload]
    normalized: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict) or "id" not in it:
            continue
        normalized.append(it)

    if normalized:
        upsert_commissions(normalized)

    return {"ok": True, "received": len(normalized)}


# Run:
# uvicorn takprodam_gifty_demo:app --reload --port 8000
