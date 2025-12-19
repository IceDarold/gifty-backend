from __future__ import annotations

import base64
import secrets
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import Response

from app.config import Settings


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def generate_session_id() -> str:
    return uuid.uuid4().hex


def build_set_cookie_kwargs(settings: Settings, max_age: Optional[int] = None) -> dict:
    return {
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite.capitalize(),
        "domain": settings.session_cookie_domain,
        "path": "/",
        "max_age": max_age or settings.session_ttl_seconds,
    }


def set_session_cookie(response: Response, session_id: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        **build_set_cookie_kwargs(settings),
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.session_cookie_domain,
        path="/",
    )


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

