from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

from app.utils.telegram_auth import verify_telegram_init_data


def _sign(init_data_without_hash: str, bot_token: str) -> str:
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret_key, init_data_without_hash.encode(), hashlib.sha256).hexdigest()


def test_verify_telegram_init_data_missing_hash():
    assert verify_telegram_init_data("user=%7B%7D", "t") is False


def test_verify_telegram_init_data_happy_path():
    bot_token = "token"
    payload = {"auth_date": "1", "query_id": "q", "user": '{"id":1}'}
    base = urlencode(payload)
    good_hash = _sign("\n".join(f"{k}={v}" for k, v in sorted(payload.items())), bot_token)
    full = base + "&hash=" + good_hash
    assert verify_telegram_init_data(full, bot_token) is True


def test_verify_telegram_init_data_bad_signature():
    bot_token = "token"
    full = "auth_date=1&user=%7B%22id%22%3A1%7D&hash=deadbeef"
    assert verify_telegram_init_data(full, bot_token) is False

