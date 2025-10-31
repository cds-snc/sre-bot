from typing import List

from fastapi import APIRouter, HTTPException, Depends

from core.logging import get_module_logger
from modules.groups import service, schemas, models

logger = get_module_logger()

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


@router.post("/add", response_model=schemas.ActionResponse)
def add_member_endpoint(request: schemas.AddMemberRequest):
    """Add member endpoint.

    Delegates to the `service.add_member` function and returns the
    Pydantic `ActionResponse` model directly.
    """
    try:
        return service.add_member(request)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.exception("add_member_endpoint_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remove", response_model=schemas.ActionResponse)
def remove_member_endpoint(request: schemas.RemoveMemberRequest):
    try:
        return service.remove_member(request)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        logger.exception("remove_member_endpoint_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[dict])
def list_groups_endpoint(request: schemas.ListGroupsRequest = Depends()):
    """List groups for a user.

    Accepts query parameters that map to `schemas.ListGroupsRequest` so OpenAPI
    documents the expected parameters (`user_email`, optional `provider`).
    """
    try:
        groups = service.list_groups(request)
        # Convert dataclasses to serializable dicts
        return [models.as_canonical_dict(g) for g in groups]
    except Exception as e:
        logger.exception("list_groups_endpoint_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk", response_model=schemas.BulkOperationResponse)
def bulk_operations_endpoint(request: schemas.BulkOperationsRequest):
    try:
        return service.bulk_operations(request)
    except Exception as e:
        logger.exception("bulk_operations_endpoint_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
