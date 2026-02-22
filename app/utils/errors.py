from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette import status

logger = logging.getLogger(__name__)


class ErrorPayload(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={Exception: str}
    )

    code: str
    message: str
    fields: Optional[dict[str, Any]] = None


class AppError(Exception):
    def __init__(self, code: str, message: str, http_status: int, fields: Optional[dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.fields = fields or {}
        super().__init__(message)


def error_response(code: str, message: str, http_status: int, fields: Optional[dict[str, Any]] = None) -> JSONResponse:
    payload = {"error": {"code": code, "message": message}}
    if fields:
        payload["error"]["fields"] = fields
    return JSONResponse(status_code=http_status, content=payload)


def install_exception_handlers(app: FastAPI) -> None:
    async def _log_bad_request(request: Request, error_payload: dict[str, Any]) -> None:
        if request.url.path != "/api/v1/recommendations/generate":
            return
        body: str | dict[str, Any] | None = None
        try:
            raw = await request.body()
            if raw:
                try:
                    body = await request.json()
                except Exception:
                    body = raw.decode("utf-8", errors="replace")
        except Exception:
            body = None
        logger.warning(
            "bad_request path=%s method=%s client=%s error=%s body=%s",
            request.url.path,
            request.method,
            request.client.host if request.client else None,
            error_payload,
            body,
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.http_status in {status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT}:
            await _log_bad_request(request, {"code": exc.code, "message": exc.message, "fields": exc.fields})
        return error_response(exc.code, exc.message, exc.http_status, exc.fields)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = "http_error"
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        fields = exc.detail if isinstance(exc.detail, dict) else None
        if exc.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT}:
            await _log_bad_request(request, {"code": code, "message": message, "fields": fields})
        return error_response(code, message, exc.status_code, fields)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        await _log_bad_request(
            request,
            {"code": "validation_error", "message": "Invalid request", "details": exc.errors()},
        )
        return error_response(
            "validation_error",
            "Invalid request",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"details": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # 1. Log the error locally
        logger.exception("unhandled_exception path=%s", request.url.path)
        
        # 2. Capture to PostHog if configured
        try:
            from app.config import get_settings
            import posthog
            
            settings = get_settings()
            if settings.posthog_api_key:
                # Initialize posthog client if not already done (it handles session/batching internally)
                posthog.project_api_key = settings.posthog_api_key
                posthog.host = "https://app.posthog.com"
                
                # Capture the error
                posthog.capture(
                    distinct_id="system",  # Use a system-level id or try to get user id if available
                    event="server_error",
                    properties={
                        "path": str(request.url.path),
                        "method": request.method,
                        "error_type": type(exc).__name__,
                        "error_detail": str(exc),
                        "env": settings.env
                    }
                )
        except Exception as ph_err:
            logger.error("Failed to capture error to PostHog: %s", ph_err)

        # 3. Send Notification alert
        try:
            from app.services.notifications import get_notification_service
            notifier = get_notification_service()
            await notifier.notify(
                topic="system_error",
                message=f"CRITICAL: Unhandled exception in {request.url.path}",
                data={
                    "path": str(request.url.path),
                    "method": request.method,
                    "error": f"{type(exc).__name__}: {str(exc)}",
                    "status": "500"
                }
            )
        except Exception as notify_err:
            logger.error("Failed to send system error notification: %s", notify_err)

        return error_response("internal_error", "Unexpected error", status.HTTP_500_INTERNAL_SERVER_ERROR)
