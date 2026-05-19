"""
Type aliases for FastAPI dependency injection.

Provides annotated type hints for common infrastructure dependencies.
"""

from typing import Annotated

from fastapi import Depends

from infrastructure.clients.maxmind import MaxMindClient
from infrastructure.configuration import AppSettings, Settings
from infrastructure.events.service import EventDispatcher
from infrastructure.i18n.service import TranslationService
from infrastructure.services.providers import (
    get_app_settings,
    get_event_dispatcher,
    get_maxmind_client,
    get_settings,
    get_translation_service,
)

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]
AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]


# MaxMind client dependency - provides IP geolocation operations
# Usage: maxmind.geolocate(ip_address="8.8.8.8")
# For types and data classes: from infrastructure.clients.maxmind import GeoLocationData
MaxMindClientDep = Annotated[MaxMindClient, Depends(get_maxmind_client)]

# Events dispatcher dependency
EventDispatcherDep = Annotated[EventDispatcher, Depends(get_event_dispatcher)]

# Translation service dependency
TranslationServiceDep = Annotated[TranslationService, Depends(get_translation_service)]


__all__ = [
    "SettingsDep",
    "AppSettingsDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
]
