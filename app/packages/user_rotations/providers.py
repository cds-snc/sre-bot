"""Singleton provider wiring for the user-rotations domain service."""

from functools import lru_cache

from packages.user_rotations.service import UserRotationsService
from packages.user_rotations.settings import get_rotations


@lru_cache(maxsize=1)
def get_user_rotations_service() -> UserRotationsService:
    """Build the service from the configured rotation files."""
    return UserRotationsService(rotations=get_rotations())
