from fastapi import APIRouter

api_v1 = APIRouter(prefix="/api/v1")

# 业务路由后续在此 include（divination / keys / billing 等）
