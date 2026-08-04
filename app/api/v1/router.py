from fastapi import APIRouter

from api.v1.routes.geolocate import router as legacy_geolocate_router
from api.v1.routes.webhooks import router as webhooks_router

# Main v1 router (includes all endpoints)
router = APIRouter()
router.include_router(webhooks_router)

# Legacy router (excludes new endpoints like groups)
legacy_router = APIRouter()
legacy_router.include_router(legacy_geolocate_router)
legacy_router.include_router(webhooks_router)
