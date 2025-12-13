"""
Type aliases for FastAPI dependency injection.

Provides annotated type hints for common infrastructure dependencies.
"""

from typing import Annotated
from fastapi import Depends
from infrastructure.configuration import Settings
from infrastructure.services.providers import get_settings, get_logger

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Logger dependency
LoggerDep = Annotated[object, Depends(get_logger)]

__all__ = [
    "SettingsDep",
    "LoggerDep",
]
