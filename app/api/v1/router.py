from fastapi import APIRouter
from api.v1.routes.geolocate import router as geolocate_router
from api.v1.routes.access import router as access_router
from api.v1.routes.webhooks import router as webhooks_router
# from modules.groups.api import router as groups_router


# Main v1 router (includes all endpoints)
router = APIRouter()
router.include_router(geolocate_router)
router.include_router(access_router)
router.include_router(webhooks_router)
# router.include_router(groups_router)

# Legacy router (excludes new endpoints like groups)
legacy_router = APIRouter()
legacy_router.include_router(geolocate_router)
legacy_router.include_router(access_router)
legacy_router.include_router(webhooks_router)
