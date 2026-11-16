"""Opsgenie vendor package: the client factory, its error classifier and the settings slice."""

from .client import build_opsgenie_client, classify_opsgenie_error
from .settings import OpsGenieSettings, OpsGenieTenant, get_opsgenie_settings

__all__ = [
    "OpsGenieSettings",
    "OpsGenieTenant",
    "build_opsgenie_client",
    "classify_opsgenie_error",
    "get_opsgenie_settings",
]
