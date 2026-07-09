"""Opsgenie integration module."""

from .client import (
    OpsGenieAPIError,
    get_on_call_users,
    get_on_call_user_for_rotation,
    create_alert,
    healthcheck,
    api_get_request,
    api_post_request,
)

__all__ = [
    "OpsGenieAPIError",
    "get_on_call_users",
    "get_on_call_user_for_rotation",
    "create_alert",
    "healthcheck",
    "api_get_request",
    "api_post_request",
]
