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

import structlog
from google.oauth2 import service_account  # type: ignore
from googleapiclient.discovery import Resource, build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore
from integrations.utils.api import convert_kwargs_to_camel_case
from core.config import settings

# Define the default arguments
GOOGLE_WORKSPACE_CUSTOMER_ID = settings.google_workspace.GOOGLE_WORKSPACE_CUSTOMER_ID
GCP_SRE_SERVICE_ACCOUNT_KEY_FILE = (
    settings.google_workspace.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE
)
SRE_BOT_EMAIL = settings.google_workspace.SRE_BOT_EMAIL
INCIDENT_TEMPLATE = settings.google_resources.incident_template_id

logger = structlog.get_logger()


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

    if not creds_json:
        logger.error("credentials_json_missing")
        raise ValueError("Credentials JSON not set")

    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_info)
        if delegated_user_email:
            creds = creds.with_subject(delegated_user_email)
        if scopes:
            creds = creds.with_scopes(scopes)
    except JSONDecodeError as json_decode_exception:
        logger.error("invalid_credentials_json", error=str(json_decode_exception))
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
        non_critical_errors = {
            "get_user": ["timed out"],
            "get_sheet": ["Unable to parse range"],
        }
        argument_string = ", ".join(
            [str(arg) for arg in args] + [f"{k}={v}" for k, v in kwargs.items()]
        )
        argument_string = f"({argument_string})"

        try:
            logger.debug(
                "executing_google_api_call",
                function=func.__name__,
                module=func.__module__,
                arguments=argument_string,
            )
            result = func(*args, **kwargs)
            # Check if the result is a tuple and has two elements (for backward compatibility)
            if isinstance(result, tuple) and len(result) == 2:
                result, unsupported_params = result
                if unsupported_params:
                    logger.warning(
                        "unsupported_parameters_warning",
                        function=func.__name__,
                        module=func.__module__,
                        unsupported_params=", ".join(unsupported_params),
                    )
            logger.debug(
                "google_api_call_success",
                function=func.__name__,
                module=func.__module__,
            )
            return result
        except HttpError as e:
            message = str(e)
            func_name = func.__name__
            if func_name in non_critical_errors and any(
                error in message for error in non_critical_errors[func_name]
            ):
                logger.warning(
                    "google_api_http_warning",
                    function=func.__name__,
                    module=func.__module__,
                    arguments=argument_string,
                    error=str(e),
                )
            else:
                logger.error(
                    "google_api_http_error",
                    function=func.__name__,
                    module=func.__module__,
                    error=str(e),
                )
                raise e
        except Exception as e:  # Catch-all for any other types of exceptions
            message = str(e)
            func_name = func.__name__
            if func_name in non_critical_errors and any(
                error in message for error in non_critical_errors[func_name]
            ):
                logger.warning(
                    "google_api_generic_warning",
                    function=func.__name__,
                    module=func.__module__,
                    arguments=argument_string,
                    error=str(e),
                )
            else:
                logger.error(
                    "google_api_generic_error",
                    function=func.__name__,
                    module=func.__module__,
                    error=str(e),
                )
            raise e

    return wrapper


def execute_google_api_call(
    service_name: str,
    version: str,
    resource_path: str,
    method: str,
    scopes: list[str] | None = None,
    delegated_user_email: str | None = None,
    paginate: bool = False,
    **kwargs: Any,
) -> Any:
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
        Any: The result of the API call. If paginate is True, returns a list of all results.
    """
    if delegated_user_email is None:
        delegated_user_email = SRE_BOT_EMAIL
    service = get_google_service(
        service_name,
        version,
        scopes,
        delegated_user_email,
    )
    resource_obj = service

    for resource in resource_path.split("."):
        try:
            resource_obj = getattr(resource_obj, resource)()
        except Exception as e:
            logger.error(
                "resource_access_error",
                resource=resource,
                error=str(e),
            )
            raise AttributeError(
                f"Error accessing {resource} on resource object. Exception: {e}"
            ) from e

    try:
        api_method = getattr(resource_obj, method)
    except Exception as e:
        logger.error(
            "api_method_error",
            method=method,
            error=str(e),
        )
        raise AttributeError(
            f"Error executing API method {method}. Exception: {e}"
        ) from e

    supported_params = get_google_api_command_parameters(resource_obj, method)
    formatted_kwargs = convert_kwargs_to_camel_case(kwargs) if kwargs else {}
    filtered_params = {
        k: v for k, v in formatted_kwargs.items() if k in supported_params
    }
    unsupported_params = set(formatted_kwargs.keys()) - set(filtered_params.keys())
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
    logger.debug(
        "getting_api_command_parameters",
        method=method,
    )
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
    logger.debug(
        "api_command_parameters_obtained",
        method=method,
        parameters=parameter_names,
    )
    return parameter_names
