"""GC Notify client."""

import calendar
import json
import time

import jwt
import requests
from core.config import settings
from core.logging import get_module_logger

logger = get_module_logger()
NOTIFY_SRE_USER_NAME = settings.notify.NOTIFY_SRE_USER_NAME
NOTIFY_SRE_CLIENT_SECRET = settings.notify.NOTIFY_SRE_CLIENT_SECRET
NOTIFY_API_URL = settings.notify.NOTIFY_API_URL


# generate the epoch seconds for the jwt token
def epoch_seconds():
    return calendar.timegm(time.gmtime())


def create_jwt_token(secret, client_id):
    """
    Generate a JWT Token for the Notify API

    Tokens have a header consisting of:
    {
        "typ": "JWT",
        "alg": "HS256"
    }

    Parameters:
    secret: Application signing secret
    client_id: Identifier for the client

    Claims are:
    iss: identifier for the client
    iat: epoch seconds for the token (UTC)

    Returns a JWT token for this request
    """
    if not secret:
        logger.error("jwt_token_creation_failed", error="Missing secret key")
        raise ValueError("Missing secret key")
    if not client_id:
        logger.error("jwt_token_creation_failed", error="Missing client id")
        raise ValueError("Missing client id")

    headers = {"typ": "JWT", "alg": "HS256"}

    claims = {"iss": client_id, "iat": epoch_seconds()}
    t = jwt.encode(payload=claims, key=secret, headers=headers)
    if isinstance(t, str):
        return t
    else:
        return t.decode()


def create_authorization_header():
    """Function to create the authorization header for the Notify API"""
    # get the client_id and secret from the environment variables
    client_id = NOTIFY_SRE_USER_NAME
    secret = NOTIFY_SRE_CLIENT_SECRET

    # If the client_id or secret is missing, raise an error
    if not client_id:
        error = "NOTIFY_SRE_USER_NAME is missing"
        logger.error(
            "authorization_header_creation_failed",
            error=error,
        )
        raise ValueError(error)
    if not secret:
        error = "NOTIFY_SRE_CLIENT_SECRET is missing"
        logger.error(
            "authorization_header_creation_failed",
            error=error,
        )
        raise ValueError(error)

    # Create the jwt token and return the authorization header
    token = create_jwt_token(secret=secret, client_id=client_id)
    return "Authorization", "Bearer {}".format(token)


def post_event(url, payload):
    """Function to post an api call to Notify"""
    # Create the authorization headers
    header_key, header_value = create_authorization_header()
    header = {header_key: header_value, "Content-Type": "application/json"}

    # Post the response
    response = requests.post(url, data=json.dumps(payload), headers=header, timeout=60)
    return response


def revoke_api_key(api_key, api_type, github_repo, source):
    """Function to revoke an api key by calling Notify's revoke api endpoint"""
    # get the url and jwt_token

    if not settings.is_production:
        logger.info("revoke_api_key_skipped", api_key=api_key)
        return False
    url = NOTIFY_API_URL

    if url is None:
        logger.error("revoke_api_key_error", error="NOTIFY_API_URL is missing")
        return False

    # append the revoke-endpoint to the url
    url = url + "/sre-tools/api-key-revoke"

    # generate the payload
    payload = {
        "token": api_key,
        "type": api_type,
        "url": github_repo,
        "source": source,
    }

    # post the event (ie call the api)
    response = post_event(url, payload)
    # A successful response has a status code of 201
    if response.status_code == 201:
        logger.info("revoke_api_key_success", api_key=api_key)
        return True
    else:
        logger.error(
            "revoke_api_key_error",
            api_key=api_key,
            response_code=response.status_code,
        )
        return False
