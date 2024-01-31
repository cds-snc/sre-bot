"""Google Service Module."""
import os
import logging
import json

from json import JSONDecodeError
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()


def get_google_service(service, version):
    """
    Get an authenticated Google service.

    Args:
        service (str): The Google service to get.
        version (str): The version of the service to get.

    Returns:
        The authenticated Google service resource.
    """

    creds_json = os.environ.get("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", False)

    if creds_json is False:
        raise ValueError("Credentials JSON not set")

    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_info)
    except JSONDecodeError as json_decode_exception:
        logging.error("Error while loading credentials JSON: %s", json_decode_exception)
        raise JSONDecodeError(
            msg="Invalid credentials JSON", doc="Credentials JSON", pos=0
        ) from json_decode_exception
    return build(service, version, credentials=creds, cache_discovery=False)
