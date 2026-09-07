from fastapi import APIRouter

from app.api.v1 import divination_meihua

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(divination_meihua.router)
