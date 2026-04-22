"""FastAPI 路由依赖：鉴权 / 限流 / 幂等。

设计原则：用 Depends 而非全局中间件，便于按路由组开关。
"""
from __future__ import annotations

from fastapi import Header, Request

from app.services import auth as auth_service


async def require_api_key(
    request: Request,
    authorization: str | None = Header(default=None),
) -> auth_service.AuthContext:
    """付费 API 路由必须 Depends(require_api_key)。

    成功后将 AuthContext 注入 request.state.auth，供下游中间件 / 服务读取。
    """
    ctx = await auth_service.authenticate(authorization)
    request.state.auth = ctx
    return ctx
