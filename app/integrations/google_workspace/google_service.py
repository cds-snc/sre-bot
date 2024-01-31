"""Google Service Module."""
import os
import pickle
import base64
import logging

from pickle import UnpicklingError
from dotenv import load_dotenv
# from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

PICKLE_STRING = os.environ.get("PICKLE_STRING", False)


def get_google_service(service, version):
    """
    Get an authenticated Google service.

    Args:
        service (str): The Google service to get.
        version (str): The version of the service to get.

    Returns:
        The authenticated Google service resource.
    """

    creds = None

    # # This is for local testing only
    # # get the file service_account_file.json from the current folder
    # service_account_file = os.path.join(
    #     os.path.dirname(__file__), "service_account_file.json"
    # )

    # if not os.path.exists(service_account_file):
    #     raise ValueError("Service account file not found")

    # creds = service_account.Credentials.from_service_account_file(service_account_file)

    if PICKLE_STRING is False:
        raise ValueError("Pickle string not set")

    try:
        pickle_string = base64.b64decode(PICKLE_STRING)
        # ignore Bandit complaint about insecure pickle
        creds = pickle.loads(pickle_string)  # nosec
    except UnpicklingError as pickle_read_exception:
        logging.error("Error while loading pickle string: %s", pickle_read_exception)
        raise UnpicklingError("Invalid pickle string") from pickle_read_exception

    return build(service, version, credentials=creds)
