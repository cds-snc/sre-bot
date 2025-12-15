"""Base Pydantic model configurations for infrastructure.

This module defines base model configurations and patterns used across
the application for consistent data validation and serialization.
"""

from pydantic import BaseModel, ConfigDict


class InfrastructureModel(BaseModel):
    """Base model for all infrastructure components.

    Provides standard Pydantic configuration for:
    - JSON serialization with populate_by_name
    - Validation on assignment
    - Type coercion
    """

    model_config = ConfigDict(
        use_enum_values=False,  # Keep enums as enum objects, not values
        populate_by_name=True,  # Accept both field name and alias
        validate_assignment=True,  # Validate on assignment
        from_attributes=True,  # Support creating from objects with attributes
        str_strip_whitespace=True,  # Strip whitespace from strings
    )
