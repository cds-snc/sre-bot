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
    Extracts and verifies the JWT token from the request cookies to authenticate the user.

    Parameters:
    request (Request): The HTTP request object containing the cookies.

    Returns:
    str: The user identifier extracted from the JWT token payload.

    Raises:
    HTTPException: If the JWT token is not found, is invalid, or does not contain a valid user identifier.
    """
    jwt_token = request.cookies.get("access_token")
    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
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
