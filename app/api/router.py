from fastapi import APIRouter
from api.routes.system import router as system_router
from api.routes.auth import router as auth_router
from api.v1.router import router as v1_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(v1_router)
