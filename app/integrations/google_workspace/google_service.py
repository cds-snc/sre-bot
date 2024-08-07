"""
Google Service Module.

This module provides a function to get an authenticated Google service, a decorator to handle Google API errors, and a generic function to execute the Google API call.

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
from integrations.utils.api import convert_kwargs_to_camel_case

# Define the default arguments
DEFAULT_DELEGATED_ADMIN_EMAIL = os.environ.get("GOOGLE_DELEGATED_ADMIN_EMAIL")
DEFAULT_GOOGLE_WORKSPACE_CUSTOMER_ID = os.environ.get("GOOGLE_WORKSPACE_CUSTOMER_ID")

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
            result = func(*args, **kwargs)
            # Check if the result is a tuple and has two elements (for backward compatibility)
            if isinstance(result, tuple) and len(result) == 2:
                result, unsupported_params = result
                if unsupported_params:
                    logging.warning(
                        f"Unknown parameters in '{func.__name__}' were detected: {', '.join(unsupported_params)}"
                    )
            return result
        except HttpError as e:
            logging.error(f"An HTTP error occurred in function '{func.__name__}': {e}")
        except ValueError as e:
            logging.error(f"A ValueError occurred in function '{func.__name__}': {e}")
        except RefreshError as e:
            logging.error(f"A RefreshError occurred in function '{func.__name__}': {e}")
        except Error as e:
            logging.error(f"An error occurred in function '{func.__name__}': {e}")
        except Exception as e:  # Catch-all for any other types of exceptions
            logging.error(
                f"An unexpected error occurred in function '{func.__name__}': {e}"
            )
        return None

    return wrapper


def execute_google_api_call(
    service_name,
    version,
    resource_path,
    method,
    scopes=None,
    delegated_user_email=None,
    paginate=False,
    **kwargs,
):
    """Execute a Google API call on a resource.

    Args:
        service_name (str): The name of the Google service.
        version (str): The version of the Google service.
        resource_path (str): The path to the resource, which can include nested resources separated by dots.
        method (str): The method to call on the resource.
        scopes (list, optional): The scopes for the Google service.
        delegated_user_email (str, optional): The email address of the user to impersonate.
        paginate (bool, optional): Whether to paginate the API call.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        dict or list: The result of the API call. If paginate is True, returns a list of all results.
    """
    service = get_google_service(service_name, version, delegated_user_email, scopes)
    resource_obj = service

    for resource in resource_path.split("."):
        try:
            resource_obj = getattr(resource_obj, resource)()
        except Exception as e:
            raise AttributeError(
                f"Error accessing {resource} on resource object. Exception: {e}"
            )

    try:
        api_method = getattr(resource_obj, method)
    except Exception as e:
        raise AttributeError(f"Error executing API method {method}. Exception: {e}")

    supported_params = get_google_api_command_parameters(resource_obj, method)
    formatted_kwargs = convert_kwargs_to_camel_case(kwargs) if kwargs else {}
    filtered_params = {
        k: v for k, v in formatted_kwargs.items() if k in supported_params
    }
    unsupported_params = set(formatted_kwargs.keys()) - set(filtered_params.keys())
    # filtered_params = kwargs
    if paginate:
        all_results = []
        request = api_method(**filtered_params)
        while request is not None:
            results = request.execute()
            if results is not None:
                all_results.extend(results.get(resource, []))
            request = getattr(resource_obj, method + "_next")(request, results)
        return all_results, unsupported_params
    else:
        return api_method(**filtered_params).execute(), unsupported_params


def get_google_api_command_parameters(resource_obj, method):
    """
    Get the parameter names for a Google API command, excluding non-parameter documentation.

    Args:
        resource_obj (object): The Google API resource object.
        method (str): The name of the API method to get the parameters for.

    Returns:
        list: The names of the parameters for the API method, excluding non-parameter documentation.
    """
    api_method = getattr(resource_obj, method)
    # Add known parameters not documented in the docstring
    parameter_names = ["fields"]

    if hasattr(api_method, "__doc__") and api_method.__doc__:
        parsing_parameters = False
        doc_lines = api_method.__doc__.splitlines()
        for line in doc_lines:
            if line.startswith("Args:"):
                parsing_parameters = True
            elif line.startswith("Returns:"):
                parsing_parameters = False
            elif parsing_parameters and ":" in line:
                param, _ = line.split(":", 1)
                parameter_names.append(param.strip())

    return parameter_names
