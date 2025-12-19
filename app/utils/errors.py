from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette import status


class ErrorPayload(BaseModel):
    code: str
    message: str
    fields: Optional[dict[str, Any]] = None

    class Config:
        populate_by_name = True
        json_encoders = {Exception: str}


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
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.code, exc.message, exc.http_status, exc.fields)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        code = "http_error"
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        fields = exc.detail if isinstance(exc.detail, dict) else None
        return error_response(code, message, exc.status_code, fields)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            "validation_error",
            "Invalid request",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"details": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        return error_response("internal_error", "Unexpected error", status.HTTP_500_INTERNAL_SERVER_ERROR)
