import logging
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Request


logging.basicConfig(level=logging.INFO)

load_dotenv()

SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or None
if SECRET_KEY is None:
    raise Exception("Missing env variables")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))


def log_ops_message(client, message):
    channel_id = "C0388M21LKZ"
    logging.info(f"Ops msg: {message}")
    client.conversations_join(channel=channel_id)
    client.chat_postMessage(channel=channel_id, text=message, as_user=True)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Generates a JSON Web Token (JWT) for authentication purposes.

    Args:
        data (dict): The data to include in the token payload.
        expires_delta (Optional[timedelta], optional): The time duration for which the token is valid. Defaults to None.

    Returns:
        str: The encoded JWT token as a string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(request: Request):
    """
    Retrieves the current authenticated user from the request.

    This asynchronous function attempts to retrieve the user information
    from either the session token or the session user stored in the request.
    It performs the following steps:
    1. Checks for the presence of an access token and session user in the request.
    2. If neither is present, raises an HTTP 401 Unauthorized exception.
    3. Attempts to decode the access token to extract the user information.
    4. If the token is invalid or the user information is not present in the token,
       it raises an HTTP 401 Unauthorized exception.
    5. Returns the user information if successfully extracted from the token.

    Args:
        request (Request): The FastAPI request object containing session data.

    Raises:
        HTTPException: If neither the access token nor the session user is present in the request.
        HTTPException: If the access token is invalid or the user information is not found.

    Returns:
        str: The user information extracted from the token or session.
    """
    # we are going to get the access token and the session user from the request to double check
    token = request.session.get("access_token")
    session_user = request.session.get("user")
    if not token and not session_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = payload.get("sub")
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    return user
