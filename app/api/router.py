from fastapi import APIRouter
from api.routes.system import router as system_router
from api.routes.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(auth_router)
