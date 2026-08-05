"""Opsgenie integration module."""

from .client import (
    OpsGenieAPIError,
    api_get_request,
    api_post_request,
    create_alert,
    get_on_call_user_for_rotation,
    get_on_call_users,
    healthcheck,
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
