from functools import lru_cache
from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_base: AnyHttpUrl = Field(..., alias="API_BASE")
    frontend_base: AnyHttpUrl = Field(..., alias="FRONTEND_BASE")
    cors_origin_regex: Optional[str] = Field(None, alias="CORS_ORIGIN_REGEX")
    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    session_cookie_name: str = Field("gifty_session", alias="SESSION_COOKIE_NAME")
    session_ttl_seconds: int = Field(60 * 60 * 24 * 30, alias="SESSION_TTL_SECONDS")
    state_ttl_seconds: int = Field(600, alias="STATE_TTL_SECONDS")
    session_cookie_domain: Optional[str] = Field(None, alias="SESSION_COOKIE_DOMAIN")
    session_cookie_secure: bool = Field(True, alias="SESSION_COOKIE_SECURE")
    session_cookie_samesite: str = Field("lax", alias="SESSION_COOKIE_SAMESITE")

    google_client_id: str = Field(..., alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(..., alias="GOOGLE_CLIENT_SECRET")
    google_authorize_url: str = Field(
        "https://accounts.google.com/o/oauth2/v2/auth", alias="GOOGLE_AUTHORIZE_URL"
    )
    google_token_url: str = Field("https://oauth2.googleapis.com/token", alias="GOOGLE_TOKEN_URL")
    google_userinfo_url: str = Field(
        "https://openidconnect.googleapis.com/v1/userinfo", alias="GOOGLE_USERINFO_URL"
    )

    yandex_client_id: str = Field(..., alias="YANDEX_CLIENT_ID")
    yandex_client_secret: str = Field(..., alias="YANDEX_CLIENT_SECRET")
    yandex_authorize_url: str = Field("https://oauth.yandex.com/authorize", alias="YANDEX_AUTHORIZE_URL")
    yandex_token_url: str = Field("https://oauth.yandex.com/token", alias="YANDEX_TOKEN_URL")
    yandex_userinfo_url: str = Field("https://login.yandex.ru/info", alias="YANDEX_USERINFO_URL")

    vk_client_id: str = Field(..., alias="VK_CLIENT_ID")
    vk_client_secret: str = Field(..., alias="VK_CLIENT_SECRET")
    vk_authorize_url: str = Field("https://oauth.vk.com/authorize", alias="VK_AUTHORIZE_URL")
    vk_token_url: str = Field("https://oauth.vk.com/access_token", alias="VK_TOKEN_URL")
    vk_userinfo_url: str = Field("https://api.vk.com/method/users.get", alias="VK_USERINFO_URL")
    vk_api_version: str = Field("5.199", alias="VK_API_VERSION")

    takprodam_api_base: Optional[str] = Field(None, alias="TAKPRODAM_API_BASE")
    takprodam_api_token: Optional[str] = Field(None, alias="TAKPRODAM_API_TOKEN")
    takprodam_source_id: Optional[int] = Field(None, alias="TAKPRODAM_SOURCE_ID")
    embedding_model: str = Field("BAAI/bge-m3", alias="EMBEDDING_MODEL")
    internal_api_token: str = Field("default_internal_token", alias="INTERNAL_API_TOKEN")
    debug: bool = Field(False, alias="DEBUG")
    env: str = Field("prod", alias="ENV")
    cors_origins: str = Field("*", alias="CORS_ORIGINS")
    secret_key: str = Field("change-me-in-production", alias="SECRET_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
