"""健康检查路由：/healthz (liveness) 与 /readyz (readiness)。"""
from fastapi import APIRouter, Response, status

from app.infra import database, redis

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe (PG + Redis)")
async def readyz(response: Response) -> dict[str, object]:
    db_ok = await database.ping()
    redis_ok = await redis.ping()
    ready = db_ok and redis_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ready": ready,
        "checks": {"db": db_ok, "redis": redis_ok},
    }
