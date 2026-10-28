"""GC Notify client."""

import calendar
import json
import time

import jwt
import requests
import structlog

from integrations.notify.settings import get_notify_settings

logger = structlog.get_logger()


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
    log = logger.bind(client_id=client_id)
    if not secret:
        log.error("jwt_token_creation_failed", error="Missing secret key")
        raise ValueError("Missing secret key")
    if not client_id:
        log.error("jwt_token_creation_failed", error="Missing client id")
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
    settings = get_notify_settings()
    client_id = settings.sre_user_name.get_secret_value()
    secret = settings.sre_client_secret.get_secret_value()

    # If the client_id or secret is missing, raise an error
    if not client_id:
        error = "NOTIFY__SRE_USER_NAME is missing"
        logger.error(
            "authorization_header_creation_failed",
            error=error,
        )
        raise ValueError(error)
    if not secret:
        error = "NOTIFY__SRE_CLIENT_SECRET is missing"
        logger.error(
            "authorization_header_creation_failed",
            error=error,
        )
        raise ValueError(error)

    # Create the jwt token and return the authorization header
    token = create_jwt_token(secret=secret, client_id=client_id)
    return "Authorization", f"Bearer {token}"


def post_event(url, payload):
    """Function to post an api call to Notify"""
    # Create the authorization headers
    header_key, header_value = create_authorization_header()
    header = {header_key: header_value, "Content-Type": "application/json"}

    # Post the response
    response = requests.post(url, data=json.dumps(payload), headers=header, timeout=get_notify_settings().timeout_seconds)
    return response


def revoke_api_key(api_key: str, api_type: str, github_repo: str, source: str) -> str:
    """Function to revoke an api key by calling Notify's revoke api endpoint.

    Returns:
        "revoked" if the key was successfully revoked (201),
        "not_found" if the key was not found (200),
        "error" for any other response or failure.
    """
    log = logger.bind(
        api_key=api_key,
        api_type=api_type,
        github_repo=github_repo,
        source=source,
    )
    tenant = get_notify_settings().tenant
    if tenant is None:
        log.warning("revoke_api_key_not_configured")
        return "error"

    url = tenant.api_url.rstrip("/") + "/sre-tools/api-key-revoke"

    # generate the payload
    payload = {
        "token": api_key,
        "type": api_type,
        "url": github_repo,
        "source": source,
    }

    # post the event (ie call the api)
    response = post_event(url, payload)
    if response.status_code == 201:
        log.info("revoke_api_key_success", api_key=api_key)
        return "revoked"
    elif response.status_code == 200:
        log.warning("revoke_api_key_not_found", api_key=api_key)
        return "not_found"
    else:
        log.error(
            "revoke_api_key_error",
            api_key=api_key,
            response_code=response.status_code,
        )
        return "error"
