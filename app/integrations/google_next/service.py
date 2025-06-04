"""
Google Service Module.

This module provides a function to get an authenticated Google service, a decorator to handle Google API errors, and a generic function to execute the Google API call.

Functions:
    get_google_service(service: str, version: str) -> googleapiclient.discovery.Resource:
        Returns an authenticated Google service resource for the specified service and version.

    handle_google_api_errors(func: Callable) -> Callable:
        Decorator that catches and logs any HttpError or Error exceptions that occur when the decorated function is called.

"""

import json
from functools import wraps
from json import JSONDecodeError
from typing import Any, Callable

from google.oauth2 import service_account  # type: ignore
from googleapiclient.discovery import Resource, build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

from core.config import settings
from core.logging import get_module_logger


# Define the default arguments
SRE_BOT_EMAIL = settings.google_workspace.SRE_BOT_EMAIL
GOOGLE_WORKSPACE_CUSTOMER_ID = settings.google_workspace.GOOGLE_WORKSPACE_CUSTOMER_ID
GCP_SRE_SERVICE_ACCOUNT_KEY_FILE = (
    settings.google_workspace.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE
)
logger = get_module_logger()


def get_google_service(
    service: str,
    version: str,
    scopes: list[str] | None = None,
    delegated_user_email: str | None = None,
) -> Resource:
    """
    Get an authenticated Google service.

    Args:
        service (str): The Google service to get.
        version (str): The version of the service to get.
        delegated_user_email (str): The email address of the user to impersonate.
        scopes (list): The list of scopes to request.

    Returns:
        Resource: The authenticated Google service resource.
    """

    creds_json = GCP_SRE_SERVICE_ACCOUNT_KEY_FILE
    if not delegated_user_email:
        delegated_user_email = SRE_BOT_EMAIL

    if not creds_json:
        logger.error(
            "credentials_json_missing",
            service=service,
            version=version,
        )
        raise ValueError("Credentials JSON not set")

    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_info)
        creds = creds.with_subject(delegated_user_email)
        if scopes:
            creds = creds.with_scopes(scopes)
    except JSONDecodeError as json_decode_exception:
        logger.error(
            "invalid_credentials_json",
            service=service,
            version=version,
            error=str(json_decode_exception),
            error_type="JSONDecodeError",
        )
        raise JSONDecodeError(
            msg="Invalid credentials JSON", doc="Credentials JSON", pos=0
        ) from json_decode_exception
    return build(service, version, credentials=creds, cache_discovery=False)


def handle_google_api_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle Google API errors.

    Args:
        func (function): The function to decorate.

        Returns:
        The decorated function.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        warnings = ["timed out", "resource not found"]
        argument_string = ", ".join(
            [str(arg) for arg in args] + [f"{k}={v}" for k, v in kwargs.items()]
        )
        argument_string = f"({argument_string})"

        try:
            logger.debug(
                "executing_google_api_call",
                function=func.__name__,
                module=func.__module__,
                service="google_api",
                arguments=argument_string,
            )
            result = func(*args, **kwargs)
            logger.debug(
                "google_api_call_success",
                function=func.__name__,
                module=func.__module__,
                service="google_api",
            )
            return result
        except HttpError as e:
            message = str(e).lower()
            if any(error in message for error in warnings):
                logger.warning(
                    "google_api_http_warning",
                    function=func.__name__,
                    module=func.__module__,
                    service="google_api",
                    arguments=argument_string,
                    error=str(e),
                )
            else:
                logger.error(
                    "google_api_http_error",
                    function=func.__name__,
                    module=func.__module__,
                    service="google_api",
                    error=str(e),
                )
            raise e
        except Exception as e:  # Catch-all for any other types of exceptions
            logger.error(
                "google_api_generic_error",
                function=func.__name__,
                module=func.__module__,
                service="google_api",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise e

    return wrapper


def execute_google_api_call(
    service: Resource,
    resource_path: str,
    method: str,
    paginate: bool = False,
    **kwargs: Any,
) -> Any:
    """Execute a Google API call on a resource.

    Args:
        service (Resource): The Google service resource.
        resource_path (str): The path to the resource, which can include nested resources separated by dots.
        method (str): The method to call on the resource.
        paginate (bool, optional): Whether to paginate the API call.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        Any: The result of the API call. If p/aginate is True, returns a list of all results.
    """
    if not service:
        logger.error(
            "service_missing",
            resource_path=resource_path,
            method=method,
            service="google_api",
        )
        raise ValueError("Service not provided")

    for resource in resource_path.split("."):
        try:
            service = getattr(service, resource)()
        except Exception as e:
            logger.error(
                "resource_access_error",
                resource=resource,
                resource_path=resource_path,
                method=method,
                service="google_api",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AttributeError(
                f"Error accessing {resource} on resource object. Exception: {e}"
            ) from e

    try:
        api_method = getattr(service, method)
    except Exception as e:
        logger.error(
            "api_method_error",
            method=method,
            resource_path=resource_path,
            service="google_api",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise AttributeError(
            f"Error executing API method {method}. Exception: {e}"
        ) from e

    if paginate:
        all_results = []
        request = api_method(**kwargs)
        while request is not None:
            results = request.execute()
            if results is not None:
                all_results.extend(results.get(resource, []))
            request = getattr(service, method + "_next")(request, results)
        return all_results
    else:
        return api_method(**kwargs).execute()


def get_google_api_command_parameters(service, method):
    """
    Get the parameter names for a Google API command, excluding non-parameter documentation.

    Args:
        service (object): The Google API resource object.
        method (str): The name of the API method to get the parameters for.

    Returns:
        list: The names of the parameters for the API method, excluding non-parameter documentation.
    """
    logger.debug(
        "getting_api_command_parameters",
        method=method,
        service="google_api",
    )
    api_method = getattr(service, method)
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
    logger.debug(
        "api_command_parameters_obtained",
        method=method,
        service="google_api",
        parameters=parameter_names,
    )
    return parameter_names
