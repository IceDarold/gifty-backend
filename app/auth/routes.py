from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from app.auth import pkce, session_store, state_store
from app.auth.deps import get_current_user
from app.auth.providers import (
    OAuthProfile,
    TokenResult,
    build_authorize_url,
    exchange_code_for_tokens,
    fetch_profile,
    get_provider_config,
)
from app.config import get_settings
from app.db import get_db
from app.models import OAuthAccount, User
from app.redis_client import get_redis
from app.schemas import UserDTO
from app.utils.errors import AppError
from app.utils.security import clear_session_cookie, generate_session_id, generate_state, set_session_cookie

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


def _safe_return_to(raw: Optional[str]) -> str:
    if not raw:
        return "/"
    if raw.startswith("//"):
        return "/"
    if raw.startswith("http://") or raw.startswith("https://"):
        target = urlparse(raw)
        frontend = urlparse(str(settings.frontend_base))
        if target.netloc != frontend.netloc:
            return "/"
        path = target.path or "/"
        if target.query:
            path = f"{path}?{target.query}"
        if target.fragment:
            path = f"{path}#{target.fragment}"
        return path
    return raw if raw.startswith("/") else "/"


def _frontend_redirect_path(return_to: str) -> str:
    cleaned = _safe_return_to(return_to)
    return str(settings.frontend_base).rstrip("/") + cleaned


@router.get("/{provider}/start", summary="Запуск OAuth авторизации")
async def oauth_start(
    provider: str,
    redis: Redis = Depends(get_redis),
    return_to: str = "/",
):
    """
    Инициирует процесс входа через стороннего провайдера (google, yandex, vk).
    Генерирует `state` и `code_verifier` (PKCE) и перенаправляет на страницу авторизации провайдера.
    """
    config = get_provider_config(provider, settings)
    state = generate_state()
    code_verifier = pkce.generate_code_verifier()
    code_challenge = pkce.generate_code_challenge(code_verifier)

    payload = {
        "provider": config.name,
        "code_verifier": code_verifier,
        "return_to": _safe_return_to(return_to),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await state_store.save_state(redis, state, payload, ttl_seconds=settings.state_ttl_seconds)

    redirect_uri = f"{settings.api_base}/api/v1/auth/{config.name}/callback"
    authorize_url = build_authorize_url(config, redirect_uri=redirect_uri, state=state, code_challenge=code_challenge)
    return RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)


async def _upsert_user(
    db: AsyncSession,
    provider_name: str,
    profile: OAuthProfile,
    tokens: TokenResult,
) -> User:
    result = await db.execute(
        select(OAuthAccount)
        .options(selectinload(OAuthAccount.user))
        .where(
            OAuthAccount.provider == provider_name,
            OAuthAccount.provider_user_id == profile.provider_user_id,
        )
    )
    account = result.scalars().first()

    if account:
        user = account.user
    else:
        user = User(name=profile.name, email=profile.email, avatar_url=profile.avatar_url)
        db.add(user)
        await db.flush()
        account = OAuthAccount(
            user_id=user.id,
            provider=provider_name,
            provider_user_id=profile.provider_user_id,
        )
        db.add(account)

    account.email_at_provider = profile.email
    account.access_token = tokens.access_token
    account.refresh_token = tokens.refresh_token
    account.expires_at = tokens.expires_at

    # Keep user fields up to date when present in profile
    if profile.name:
        user.name = profile.name
    if profile.email and not user.email:
        user.email = profile.email
    if profile.avatar_url:
        user.avatar_url = profile.avatar_url

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{provider}/callback", summary="Обработка ответа от OAuth провайдера")
async def oauth_callback(
    provider: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """
    Эндпоинт, на который провайдер возвращает пользователя с временным кодом.
    Обменивает код на токены, создает или обновляет профиль пользователя и устанавливает сессионную куку.
    """
    if not code or not state:
        raise AppError("invalid_request", "code and state are required", status.HTTP_400_BAD_REQUEST)

    stored = await state_store.pop_state(redis, state)
    if not stored:
        raise AppError("invalid_state", "State is missing or expired", status.HTTP_400_BAD_REQUEST)

    config = get_provider_config(provider, settings)
    if stored.get("provider") != config.name:
        raise AppError("invalid_state", "Provider mismatch for state", status.HTTP_400_BAD_REQUEST)

    code_verifier = stored.get("code_verifier")
    if not code_verifier:
        raise AppError("invalid_state", "Missing code_verifier", status.HTTP_400_BAD_REQUEST)

    redirect_uri = f"{settings.api_base}/api/v1/auth/{config.name}/callback"
    tokens = await exchange_code_for_tokens(config, code=code, redirect_uri=redirect_uri, code_verifier=code_verifier)
    profile = await fetch_profile(config, tokens, settings)

    user = await _upsert_user(db, config.name, profile, tokens)

    session_id = generate_session_id()
    await session_store.create_session(
        redis,
        session_id,
        {"user_id": str(user.id), "created_at": datetime.now(timezone.utc).isoformat()},
        ttl_seconds=settings.session_ttl_seconds,
    )

    redirect_target = _frontend_redirect_path(stored.get("return_to"))
    response = RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)
    set_session_cookie(response, session_id, settings)
    return response


@router.get("/me", response_model=UserDTO, summary="Информация о текущем пользователе")
async def current_user(user: User = Depends(get_current_user)) -> UserDTO:
    """
    Возвращает профиль текущего авторизованного пользователя на основе сессионной куки.
    """
    return UserDTO.from_orm(user)


@router.post("/logout", summary="Выход из системы")
async def logout(request: Request, redis: Redis = Depends(get_redis)) -> JSONResponse:
    """
    Удаляет сессию из Redis и очищает сессионную куку на клиенте.
    """
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        await session_store.delete_session(redis, session_id)
    response = JSONResponse({"ok": True})
    clear_session_cookie(response, settings)
    return response


