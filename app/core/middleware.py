"""通用中间件：注入 request_id。

鉴权 / 限流 / 计费等业务中间件后续单独文件。
"""
from __future__ import annotations

import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response
