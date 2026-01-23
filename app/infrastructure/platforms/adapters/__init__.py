"""Platform adapters for wrapping FastAPI endpoints with platform-native interfaces.

Adapters translate platform-specific events into HTTP calls to internal endpoints,
maintaining platform-independence in business logic while enabling platform-native features.

Architecture:
    Platform Event → Adapter.parse_payload() → CommandPayload
                   → Adapter.execute_command() → HTTP POST localhost:8000
                   → FastAPI route handler → Business logic
                   → JSON response → Adapter.format_response()
                   → Platform-specific format (Block Kit, Adaptive Cards, etc.)

Benefits:
    - Business logic testable via standard HTTP
    - Platform SDKs isolated to adapters
    - Consistent audit logging and idempotency
    - Easy to add new platforms

Modules:
    base: Base adapter classes for commands, views, cards
"""

from infrastructure.platforms.adapters.base import BaseCommandAdapter

__all__ = ["BaseCommandAdapter"]
