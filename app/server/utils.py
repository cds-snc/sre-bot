from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt  # type: ignore

from core.config import settings
from core.logging import get_module_logger


ACCESS_TOKEN_EXPIRE_MINUTES = settings.server.ACCESS_TOKEN_EXPIRE_MINUTES
ACCESS_TOKEN_MAX_AGE_MINUTES = settings.server.ACCESS_TOKEN_MAX_AGE_MINUTES
SECRET_KEY = settings.server.SECRET_KEY
ALGORITHM = "HS256"

logger = get_module_logger()
oauth2_scheme = HTTPBearer(auto_error=False)


def log_ops_message(client, message):
    channel_id = "C0388M21LKZ"
    logger.info("ops_message_logged", message=message)
    client.conversations_join(channel=channel_id)
    client.chat_postMessage(channel=channel_id, text=message, as_user=True)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Generates a JSON Web Token (JWT) for authentication purposes.

    Args:
        data (dict): The data to include in the token payload.
        expires_delta (Optional[timedelta], optional): The expiration time for the token.
            If not provided, the token will expire after a default duration.
            Defaults to None.

    Returns:
        str: The encoded JWT token as a string.

    Raises:
        ValueError: If the expires_delta is negative or exceeds the maximum allowed duration.
        HTTPException: If there is an error during JWT encoding.
    """
    if expires_delta and expires_delta.total_seconds() < 0:
        raise ValueError("expires_delta cannot be negative")

    if (
        expires_delta
        and expires_delta.total_seconds() > ACCESS_TOKEN_MAX_AGE_MINUTES * 60
    ):
        raise ValueError("expires_delta exceeds maximum allowed duration")

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except JWTError as e:
        logger.error("jwt_encoding_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to encode JWT",
        ) from e
    logger.info("jwt_token_created")
    return encoded_jwt


async def get_current_user(
    request: Request,
    token: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
):
    """
    Extracts and verifies the JWT token from the request cookies to authenticate the user.

    Parameters:
    request (Request): The HTTP request object containing the cookies.

    Returns:
    str: The user identifier extracted from the JWT token payload.

    Raises:
    HTTPException: If the JWT token is not found, is invalid, or does not contain a valid user identifier.
    """
    jwt_token = token.credentials if token else request.cookies.get("access_token")
    if not jwt_token:
        logger.error("jwt_token_missing", request_cookies=request.cookies)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        user = payload.get("sub")
        if user is None:
            logger.error("jwt_token_invalid", payload=payload)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
    except JWTError as e:
        logger.error("jwt_token_decoding_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from e
    return user


def get_user_email_from_request(request: Request):
    """
    Retrieve the user's email address from the request session.

    This function extracts the user's email address from the session data stored in the request.
    It performs necessary checks to ensure the request and session data are valid.

    Args:
        request (Request): The FastAPI request object containing session data.

    Raises:
        HTTPException: If the request or session data is missing or invalid.

    Returns:
        str or None: The user's email address if found, otherwise None.
    """
    if not request or not request.session:
        raise HTTPException(
            status_code=400, detail="Invalid request or missing session data"
        )

    user_email = request.session.get("user").get("email")
    if user_email:
        return user_email
    return None
