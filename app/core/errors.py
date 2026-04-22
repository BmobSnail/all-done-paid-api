"""统一错误响应 schema 与异常体系。

响应格式：
    {"error": {"code": "...", "message": "...", "request_id": "..."}}

HTTP 状态码语义：
- 401 missing_credentials       - 无 Authorization
- 401 invalid_api_key            - key 解析失败
- 403 api_key_disabled           - key 被吊销/过期
- 402 quota_exceeded             - 日配额耗尽（付费回收 / 升级提示）
- 429 rate_limited               - QPS / burst / 并发命中
- 422 validation_error           - 入参不合法
- 500 internal_error             - 未捕获异常
- 502 upstream_unavailable       - LLM provider 故障且 fallback 未恢复
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """业务错误基类。"""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    default_message: str = "Internal server error"

    def __init__(self, message: str | None = None, **extra: Any) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.extra = extra


class MissingCredentialsError(ApiError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "missing_credentials"
    default_message = "Missing Authorization header"


class InvalidApiKeyError(ApiError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_api_key"
    default_message = "API key is invalid"


class ApiKeyDisabledError(ApiError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "api_key_disabled"
    default_message = "API key has been disabled or has expired"


class QuotaExceededError(ApiError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "quota_exceeded"
    default_message = "Daily quota exceeded"


class RateLimitedError(ApiError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    default_message = "Too many requests"


class ValidationApiError(ApiError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"
    default_message = "Validation failed"


class UpstreamUnavailableError(ApiError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_unavailable"
    default_message = "Upstream LLM provider unavailable"


def _build(req: Request, code: str, message: str, http_status: int, extra: dict[str, Any] | None = None) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(req.state, "request_id", None),
        }
    }
    if extra:
        body["error"].update(extra)
    return JSONResponse(content=body, status_code=http_status)


async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return _build(request, exc.code, exc.message, exc.status_code, exc.extra)


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _build(
        request,
        "validation_error",
        "Validation failed",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        {"errors": exc.errors()},
    )


async def _generic_handler(request: Request, exc: Exception) -> JSONResponse:
    return _build(
        request,
        "internal_error",
        "Internal server error",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def install(app: FastAPI) -> None:
    """注册全局 exception handler。"""
    app.add_exception_handler(ApiError, _api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _generic_handler)
