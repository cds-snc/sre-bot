"""GC Notify vendor package: the client factory, its error classifier and the settings slice."""

from .client import build_notify_client, classify_notify_error
from .settings import NotifySettings, NotifyTenant, get_notify_settings

__all__ = [
    "NotifySettings",
    "NotifyTenant",
    "build_notify_client",
    "classify_notify_error",
    "get_notify_settings",
]
