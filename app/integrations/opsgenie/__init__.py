"""Opsgenie integration module."""

from .client import (
    get_on_call_users,
    create_alert,
    healthcheck,
    api_get_request,
    api_post_request,
)

__all__ = [
    "get_on_call_users",
    "create_alert",
    "healthcheck",
    "api_get_request",
    "api_post_request",
]
