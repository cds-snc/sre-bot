---
adr_id: ADR-0034
title: "Validation Patterns"
status: Superseded
decision_type: Feature
tier: Tier-4
date_created: unknown
last_updated: 2026-04-30
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0063
related_records:
  - ADR-0040
related_packages: []
review_state: stale
---
# Validation Patterns

## Context

Request validation must be predictable, composable, and maintain clear boundaries between input validation and business logic. Pydantic validators provide a structured way to validate and coerce HTTP request data.

## Decision

Use Pydantic field_validator and model_validator decorators for validation. Discriminated unions enable single endpoints to accept multiple request shapes selected by a Literal field. Business logic assumes validated data.

## Consequences

- ✅ Validation rules are co-located with schemas
- ✅ Multi-field validation is explicit and composable
- ✅ Discriminated unions provide type-safe polymorphism
- ✅ Business logic never receives invalid data
- ⚠️ Requires careful use of validator modes (before/after)

---

## Field Validators

**Decision**: Use Pydantic validators.

**Implementation**:
```python
from pydantic import BaseModel, field_validator

class UserRequest(BaseModel):
    username: str
    email: str
    
    @field_validator('username', mode='after')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v
    
    @field_validator('email', mode='after')
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()
```

**Rules**:
- ✅ Use `@field_validator` for custom validation
- ✅ Use `mode='after'` for post-Pydantic validation
- ✅ Use `mode='before'` for pre-processing
- ✅ Return modified value (for coercion)
- ❌ Don't use validators for business logic

---

## Model Validators

**Decision**: Use model validators.

**Implementation**:
```python
from pydantic import BaseModel, model_validator
from typing import Self

class PasswordReset(BaseModel):
    password: str
    password_confirm: str
    
    @model_validator(mode='after')
    def passwords_match(self) -> Self:
        if self.password != self.password_confirm:
            raise ValueError('Passwords do not match')
        return self
```

**Rules**:
- ✅ Use `@model_validator` for multi-field checks
- ✅ Return `self` from after validators
- ✅ Use `mode='after'` for validated data
- ❌ Don't modify fields in model validators

---

## Discriminated Unions

**Decision**: Use Pydantic discriminated unions when a single endpoint accepts multiple request shapes selected by a Literal field.

Declare each shape as a separate model with a `Literal` discriminator field. Combine them into a union type using `Annotated[Union[...], Field(discriminator="field_name")]`. Pydantic validates against the correct model before the request reaches the route handler.

```python
# packages/feature/schemas.py
from typing import Annotated, Literal, Union

from pydantic import BaseModel, EmailStr, Field


class UserActionRequest(BaseModel):
    action_type: Literal["user"] = "user"
    user_email: EmailStr = Field(..., description="Email of the target user.")
    platform: str = Field(..., description="Target platform key.")
    dry_run: bool = Field(default=False)


class PlatformActionRequest(BaseModel):
    action_type: Literal["platform"] = "platform"
    platform: str = Field(..., description="Target platform key.")
    dry_run: bool = Field(default=False)


ActionRequest = Annotated[
    Union[UserActionRequest, PlatformActionRequest],
    Field(discriminator="action_type"),
]
```

```python
# packages/feature/transport/routes.py
from packages.feature.schemas import ActionRequest, UserActionRequest

@router.post("/actions")
def action_endpoint(request: ActionRequest) -> ActionResponse:
    if isinstance(request, UserActionRequest):
        result = service.user_action(user_email=str(request.user_email), ...)
    else:
        result = service.platform_action(platform=request.platform, ...)
    ...
```

**Rules**:
- ✅ Use `Literal["value"]` as the discriminator field type
- ✅ Combine shapes with `Annotated[Union[...], Field(discriminator=...)]`
- ✅ Use `isinstance` to branch on the resolved type in the route handler
- ✅ Each shape is a complete, independently documented model
- ❌ Do not pass the union type into business logic \u2014 extract typed fields at the route boundary
