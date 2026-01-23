import structlog
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, HTTPException

from integrations.aws.organizations import get_active_account_names
from models.webhooks import AccessRequest
from modules.aws.aws import request_aws_account_access
from modules.aws.aws_access_requests import get_active_requests, get_past_requests
from server.utils import (
    get_current_user,
    get_user_email_from_request,
)


from core.security import validate_jwt_token
from api.dependencies.rate_limits import get_limiter


logger = structlog.get_logger()

router = APIRouter(tags=["Access"])
limiter = get_limiter()


@router.post("/request_access")
@limiter.limit("10/minute")
async def create_access_request(
    request: Request,
    access_request: AccessRequest,
    use: dict = Depends(get_current_user),
):
    """
    Endpoint to create an AWS access request.

    This asynchronous function handles POST requests to the "/request_access" endpoint. It performs several validation checks on the provided access request data and then attempts to create an access request in the system. The function is protected by a rate limiter and requires user authentication.

    Args:
        request (Request): The FastAPI request object.
        access_request (AccessRequest): The data model representing the access request.
        use (dict, optional): Dependency that provides the current user context. Defaults to Depends(get_current_user).

    Raises:
        HTTPException: If any validation checks fail or if the request creation fails.

    Returns:
        dict: A dictionary containing a success message and the access request data if the request is successfully created.
    """
    # Check if the account and reason fields are provided
    if not access_request.account or not access_request.reason:
        raise HTTPException(status_code=400, detail="Account and reason are required")

    # Check if the start date is at least 5 minutes in the future
    if (
        access_request.startDate.replace(tzinfo=timezone.utc) + timedelta(minutes=5)
    ) < datetime.now().replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="Start date must be in the future")

    # Check if the end date is after the start date
    if access_request.endDate.replace(tzinfo=timezone.utc) <= access_request.startDate:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # If the request is for more than 24 hours in the future, this is not allowed
    if access_request.endDate.replace(tzinfo=timezone.utc) > datetime.now().replace(
        tzinfo=timezone.utc
    ) + timedelta(days=1):
        raise HTTPException(
            status_code=400,
            detail="The access request cannot be for more than 24 hours",
        )

    # get the user email from the request
    user_email = get_user_email_from_request(request)

    # Store the request in the database
    response = request_aws_account_access(
        access_request.account,
        access_request.reason,
        access_request.startDate,
        access_request.endDate,
        user_email,
        "read",
    )
    # Return a success message and the access request data if the request is created successfully
    if response:
        return {
            "message": "Access request created successfully",
            "data": access_request,
        }
    else:
        # Raise an HTTP 500 error if the request creation fails
        raise HTTPException(status_code=500, detail="Failed to create access request")


@router.get("/accounts")
@limiter.limit("5/minute")
async def get_accounts(
    request: Request, token_data: dict = Depends(validate_jwt_token)
):
    """
    Endpoint to retrieve active AWS account names.

    This asynchronous function handles GET requests to the "/accounts" endpoint.
    It retrieves a list of active AWS account names. The function is protected by a rate limiter and requires user authentication.

    Args:
        request (Request): The FastAPI request object.
        user (dict, optional): Dependency that provides the current user context. Defaults to Depends(get_current_user).

    Returns:
        list: A list of active AWS account names.
    """
    logger.info(
        "get_accounts",
        user=token_data["sub"],
        email=token_data["email"],
        issuer=token_data["iss"],
        token_data=token_data,
    )
    return get_active_account_names()


@router.get("/active_requests")
@limiter.limit("5/minute")
async def get_aws_active_requests(
    request: Request, user: dict = Depends(get_current_user)
):
    """
    Retrieves the active access requests from the database.
    Args:
        request (Request): The HTTP request object.
    Returns:
        list: The list of active access requests.
    """
    return get_active_requests()


@router.get("/past_requests")
@limiter.limit("5/minute")
async def get_aws_past_requests(
    request: Request, user: dict = Depends(get_current_user)
):
    """
    Retrieves the past access requests from the database.
    Args:
        request (Request): The HTTP request object.
    Returns:
        list: The list of past access requests.
    """
    return get_past_requests()
