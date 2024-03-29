"""
Google Service Module.

This module provides a function to get an authenticated Google service and a decorator to handle Google API errors.

Functions:
    get_google_service(service: str, version: str) -> googleapiclient.discovery.Resource:
        Returns an authenticated Google service resource for the specified service and version.

    handle_google_api_errors(func: Callable) -> Callable:
        Decorator that catches and logs any HttpError or Error exceptions that occur when the decorated function is called.

"""
import os
import logging
import json

from json import JSONDecodeError
from dotenv import load_dotenv
from functools import wraps
from google.oauth2 import service_account  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError, Error  # type: ignore
from google.auth.exceptions import RefreshError  # type: ignore

load_dotenv()


def get_google_service(service, version, delegated_user_email=None, scopes=None):
    """
    Get an authenticated Google service.

    Args:
        service (str): The Google service to get.
        version (str): The version of the service to get.
        delegated_user_email (str): The email address of the user to impersonate.
        scopes (list): The list of scopes to request.

    Returns:
        The authenticated Google service resource.
    """

    creds_json = os.environ.get("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", False)

    if creds_json is False:
        raise ValueError("Credentials JSON not set")

    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_info)
        if delegated_user_email:
            creds = creds.with_subject(delegated_user_email)
        if scopes:
            creds = creds.with_scopes(scopes)
    except JSONDecodeError as json_decode_exception:
        logging.error("Error while loading credentials JSON: %s", json_decode_exception)
        raise JSONDecodeError(
            msg="Invalid credentials JSON", doc="Credentials JSON", pos=0
        ) from json_decode_exception
    return build(service, version, credentials=creds, cache_discovery=False)


def handle_google_api_errors(func):
    """Decorator to handle Google API errors.

    Args:
        func (function): The function to decorate.

        Returns:
        The decorated function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            logging.error(f"An HTTP error occurred in function '{func.__name__}': {e}")
            return None
        except ValueError as e:
            logging.error(f"A ValueError occurred in function '{func.__name__}': {e}")
            return None
        except RefreshError as e:
            logging.error(f"A RefreshError occurred in function '{func.__name__}': {e}")
            return None
        except Error as e:
            logging.error(f"An error occurred in function '{func.__name__}': {e}")
            return None

    return wrapper
