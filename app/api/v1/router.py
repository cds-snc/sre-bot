from fastapi import APIRouter
from api.v1.routes.geolocate import router as geolocate_router
from api.v1.routes.access import router as access_router
from api.v1.routes.webhooks import router as webhooks_router


router = APIRouter()
router.include_router(geolocate_router)
router.include_router(access_router)
router.include_router(webhooks_router)
