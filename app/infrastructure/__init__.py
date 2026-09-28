"""Infrastructure layer - dependency injection and core services.

Public API:
- Dependency injection providers (get_settings, etc.)
- Type aliases for FastAPI routes (SettingsDep, CurrentUserDep, etc.)

All other infrastructure packages are internal implementation details.
Use the services layer for all infrastructure access.
"""
