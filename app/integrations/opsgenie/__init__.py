"""Opsgenie integration module."""

from .client import (
    OpsGenieAPIError,
    api_get_request,
    get_on_call_user_for_rotation,
    get_on_call_users,
    healthcheck,
)

__all__ = [
    "OpsGenieAPIError",
    "get_on_call_users",
    "get_on_call_user_for_rotation",
    "healthcheck",
    "api_get_request",
]
