"""FastAPI 应用入口。"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import api_v1, health
from app.core import errors
from app.core.config import get_settings
from app.core.middleware import request_id_middleware
from app.infra import database, redis
from app.infra.llm import client as llm_client


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    database.init_engine()
    redis.init_redis()
    llm_client.init()
    try:
        yield
    finally:
        await redis.dispose_redis()
        await database.dispose_engine()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.PAID_APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
    )

    if s.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=s.cors_origins_list,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    app.add_middleware(BaseHTTPMiddleware, dispatch=request_id_middleware)
    errors.install(app)

    # /healthz 与 /readyz 暴露在根路径，方便反代健康检查
    app.include_router(health.router)
    # 业务接口走 /api/v1/*
    app.include_router(api_v1)

    return app


app = create_app()
