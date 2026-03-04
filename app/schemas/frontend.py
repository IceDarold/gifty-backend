from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


ReleaseStatus = Literal["draft", "ready", "active", "archived"]
HealthStatus = Literal["unknown", "healthy", "unhealthy"]


class FrontendConfigRequest(BaseModel):
    host: str
    path: str = "/"
    query_params: dict[str, str] = Field(default_factory=dict)
    country: Optional[str] = None
    sticky_release_id: Optional[int] = None


class FrontendConfigResponse(BaseModel):
    target_url: str
    release_id: int
    cache_ttl: int
    sticky_key: str
    flags: dict[str, Any] = Field(default_factory=dict)


class FrontendAppCreate(BaseModel):
    key: str
    name: str
    is_active: bool = True


class FrontendAppUpdate(BaseModel):
    key: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None


class FrontendAppDTO(BaseModel):
    id: int
    key: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FrontendReleaseCreate(BaseModel):
    app_id: int
    version: str
    target_url: str
    status: ReleaseStatus = "draft"
    health_status: HealthStatus = "unknown"
    flags: dict[str, Any] = Field(default_factory=dict)


class FrontendReleaseUpdate(BaseModel):
    version: Optional[str] = None
    target_url: Optional[str] = None
    status: Optional[ReleaseStatus] = None
    health_status: Optional[HealthStatus] = None
    flags: Optional[dict[str, Any]] = None


class FrontendReleaseDTO(BaseModel):
    id: int
    app_id: int
    version: str
    target_url: str
    status: ReleaseStatus
    health_status: HealthStatus
    flags: dict[str, Any]
    validated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FrontendProfileCreate(BaseModel):
    key: str
    name: str
    is_active: bool = True


class FrontendProfileUpdate(BaseModel):
    key: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None


class FrontendProfileDTO(BaseModel):
    id: int
    key: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FrontendRuleCreate(BaseModel):
    profile_id: int
    priority: int = 100
    host_pattern: str = "*"
    path_pattern: str = "/*"
    query_conditions: dict[str, str] = Field(default_factory=dict)
    target_release_id: int
    flags_override: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class FrontendRuleUpdate(BaseModel):
    priority: Optional[int] = None
    host_pattern: Optional[str] = None
    path_pattern: Optional[str] = None
    query_conditions: Optional[dict[str, str]] = None
    target_release_id: Optional[int] = None
    flags_override: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class FrontendRuleDTO(BaseModel):
    id: int
    profile_id: int
    priority: int
    host_pattern: str
    path_pattern: str
    query_conditions: dict[str, str]
    target_release_id: int
    flags_override: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FrontendRuntimeStateUpdate(BaseModel):
    active_profile_id: Optional[int] = None
    fallback_release_id: Optional[int] = None
    sticky_enabled: Optional[bool] = None
    sticky_ttl_seconds: Optional[int] = Field(default=None, ge=60, le=86400)
    cache_ttl_seconds: Optional[int] = Field(default=None, ge=1, le=300)


class FrontendRuntimeStateDTO(BaseModel):
    id: int
    active_profile_id: Optional[int] = None
    fallback_release_id: Optional[int] = None
    sticky_enabled: bool
    sticky_ttl_seconds: int
    cache_ttl_seconds: int
    updated_by: Optional[int] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class FrontendAllowedHostCreate(BaseModel):
    host: str
    is_active: bool = True


class FrontendAllowedHostUpdate(BaseModel):
    host: Optional[str] = None
    is_active: Optional[bool] = None


class FrontendAllowedHostDTO(BaseModel):
    id: int
    host: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FrontendAuditLogDTO(BaseModel):
    id: int
    actor_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishRequest(BaseModel):
    active_profile_id: int
    fallback_release_id: int
    sticky_enabled: Optional[bool] = None
    sticky_ttl_seconds: Optional[int] = Field(default=None, ge=60, le=86400)
    cache_ttl_seconds: Optional[int] = Field(default=None, ge=1, le=300)


class RollbackRequest(BaseModel):
    app_id: Optional[int] = None


class ValidateReleaseResponse(BaseModel):
    release_id: int
    ok: bool
    reason: Optional[str] = None
    status_code: Optional[int] = None
    health_status: HealthStatus
    validated_at: Optional[datetime] = None
