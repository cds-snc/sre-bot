# Validation Patterns

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
