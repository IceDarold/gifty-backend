from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.utils.errors import AppError


@dataclass
class TokenResult:
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[datetime]
    id_token: Optional[str]
    raw: Dict[str, Any]


@dataclass
class OAuthProfile:
    provider_user_id: str
    email: Optional[str]
    name: Optional[str]
    avatar_url: Optional[str]


@dataclass
class ProviderConfig:
    name: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: List[str]
    client_id: str
    client_secret: str
    extra_auth_params: Optional[Dict[str, str]] = None


def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(15.0))


def get_provider_config(provider: str, settings: Settings) -> ProviderConfig:
    normalized = provider.lower()
    if normalized == "google":
        return ProviderConfig(
            name="google",
            authorize_url=settings.google_authorize_url,
            token_url=settings.google_token_url,
            userinfo_url=settings.google_userinfo_url,
            scopes=["openid", "email", "profile"],
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            extra_auth_params={"access_type": "offline", "prompt": "consent"},
        )
    if normalized == "yandex":
        return ProviderConfig(
            name="yandex",
            authorize_url=settings.yandex_authorize_url,
            token_url=settings.yandex_token_url,
            userinfo_url=settings.yandex_userinfo_url,
            scopes=["login:email", "login:info"],
            client_id=settings.yandex_client_id,
            client_secret=settings.yandex_client_secret,
            extra_auth_params={"force_confirm": "yes"},
        )
    if normalized == "vk":
        return ProviderConfig(
            name="vk",
            authorize_url=settings.vk_authorize_url,
            token_url=settings.vk_token_url,
            userinfo_url=settings.vk_userinfo_url,
            scopes=["email"],
            client_id=settings.vk_client_id,
            client_secret=settings.vk_client_secret,
            extra_auth_params={"v": settings.vk_api_version, "display": "page"},
        )
    raise AppError("unsupported_provider", "Unsupported provider", 400)


def build_authorize_url(config: ProviderConfig, redirect_uri: str, state: str, code_challenge: str) -> str:
    params: Dict[str, Any] = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if config.extra_auth_params:
        params.update(config.extra_auth_params)
    return f"{config.authorize_url}?{urlencode(params)}"


async def exchange_code_for_tokens(
    config: ProviderConfig, code: str, redirect_uri: str, code_verifier: str
) -> TokenResult:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": config.client_id,
        "code_verifier": code_verifier,
    }
    # VK does not require code_verifier but we can still pass it.
    if config.client_secret:
        data["client_secret"] = config.client_secret

    async with _http_client() as client:
        response = await client.post(config.token_url, data=data)
    if response.status_code >= 400:
        raise AppError("oauth_token_error", f"Token exchange failed: {response.text}", response.status_code)
    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise AppError("oauth_token_error", "Token exchange did not return access_token", 502)

    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    id_token = payload.get("id_token")

    expires_at = None
    if expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    return TokenResult(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        id_token=id_token,
        raw=payload,
    )


async def fetch_profile(config: ProviderConfig, tokens: TokenResult, settings: Settings) -> OAuthProfile:
    async with _http_client() as client:
        headers = {"Authorization": f"Bearer {tokens.access_token}"}
        # VK uses query parameters instead of headers.
        if config.name == "vk":
            params = {"access_token": tokens.access_token, "v": settings.vk_api_version, "fields": "photo_200"}
            response = await client.get(config.userinfo_url, params=params)
        elif config.name == "yandex":
            response = await client.get(config.userinfo_url, headers=headers, params={"format": "json"})
        else:
            response = await client.get(config.userinfo_url, headers=headers)

    if response.status_code >= 400:
        raise AppError("oauth_profile_error", f"Profile fetch failed: {response.text}", response.status_code)

    data = response.json()
    if config.name == "google":
        return OAuthProfile(
            provider_user_id=str(data.get("sub") or ""),
            email=data.get("email"),
            name=data.get("name"),
            avatar_url=data.get("picture"),
        )
    if config.name == "yandex":
        email = None
        if isinstance(data.get("emails"), list) and data["emails"]:
            email = data["emails"][0]
        email = email or data.get("default_email")
        real_name = data.get("real_name") or data.get("display_name") or None
        avatar_id = data.get("default_avatar_id")
        avatar_url = f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200" if avatar_id else None
        return OAuthProfile(
            provider_user_id=str(data.get("id") or ""),
            email=email,
            name=real_name,
            avatar_url=avatar_url,
        )
    if config.name == "vk":
        users = data.get("response") or []
        profile = users[0] if users else {}
        full_name = " ".join(filter(None, [profile.get("first_name"), profile.get("last_name")])) or None
        email = tokens.raw.get("email")
        return OAuthProfile(
            provider_user_id=str(profile.get("id") or tokens.raw.get("user_id") or ""),
            email=email,
            name=full_name,
            avatar_url=profile.get("photo_200"),
        )

    raise AppError("unsupported_provider", "Unsupported provider", 400)
