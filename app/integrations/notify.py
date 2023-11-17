import os
import jwt
import time
import calendar
import logging
import requests
import json


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
    assert secret, "Missing secret key"
    assert client_id, "Missing client id"

    headers = {"typ": "JWT", "alg": "HS256"}

    claims = {"iss": client_id, "iat": epoch_seconds()}
    t = jwt.encode(payload=claims, key=secret, headers=headers)
    if isinstance(t, str):
        return t
    else:
        return t.decode()


# Function to create the authorization header for the Notify API
def create_authorization_header():
    # get the client_id and secret from the environment variables
    client_id = os.getenv("NOTIFY_SRE_USER_NAME")
    secret = os.getenv("NOTIFY_SRE_CLIENT_SECRET")

    # If the client_id or secret is missing, raise an assertion error
    assert client_id, "NOTIFY_SRE_USER_NAME is missing"
    assert secret, "NOTIFY_SRE_CLIENT_SECRET is missing"

    # Create the jwt token and return the authorization header
    token = create_jwt_token(secret=secret, client_id=client_id)
    return "Authorization", "Bearer {}".format(token)


# Function to post an api call to Notify
def post_event(url, payload):
    # Create the authorization headers
    header_key, header_value = create_authorization_header()
    header = {header_key: header_value, "Content-Type": "application/json"}

    # Post the response
    response = requests.post(url, data=json.dumps(payload), headers=header, timeout=60)
    return response


# Function to revoke an api key by calling Notify's revoke api endpoint
def revoke_api_key(api_key, api_type, github_repo, source):
    # get the url and jwt_token
    url = os.getenv("NOTIFY_API_URL")

    if url is None:
        logging.error("NOTIFY_API_URL usmissing")
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
        logging.info(f"API key {api_key} has been successfully revoked")
        return True
    else:
        logging.error(
            f"API key {api_key} could not be revoked. Response code: {response.status_code}"
        )
        return False
