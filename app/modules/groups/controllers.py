from typing import List

from fastapi import APIRouter, Depends

from core.logging import get_module_logger
from modules.groups import service, schemas, models

logger = get_module_logger()

# Controllers are thin adapters: they accept Pydantic request models, call the
# service boundary, and return Pydantic response models. We intentionally do
# NOT keep any legacy compatibility shims.
router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


@router.post("/add", response_model=schemas.ActionResponse)
def add_member_endpoint(request: schemas.AddMemberRequest):
    """Add member endpoint.

    Delegates to the `service.add_member` function and returns the
    Pydantic `ActionResponse` model directly.
    """
    return service.add_member(request)


@router.post("/remove", response_model=schemas.ActionResponse)
def remove_member_endpoint(request: schemas.RemoveMemberRequest):
    return service.remove_member(request)


@router.get("/", response_model=List[schemas.GroupResponse])
def list_groups_endpoint(request: schemas.ListGroupsRequest = Depends()):
    """List groups for a user.

    Accepts query parameters that map to `schemas.ListGroupsRequest` so OpenAPI
    documents the expected parameters (`user_email`, optional `provider`).
    """
    groups = service.list_groups(request)
    # Convert dataclasses to Pydantic response models
    return [
        schemas.GroupResponse.model_validate(models.as_canonical_dict(g))
        for g in groups
    ]


@router.post("/bulk", response_model=schemas.BulkOperationResponse)
def bulk_operations_endpoint(request: schemas.BulkOperationsRequest):
    return service.bulk_operations(request)
