"""Opsgenie integration module."""

from .client import (
    api_get_request,
    api_post_request,
    create_alert,
    get_on_call_users,
    healthcheck,
)

__all__ = [
    "get_on_call_users",
    "create_alert",
    "healthcheck",
    "api_get_request",
    "api_post_request",
]
