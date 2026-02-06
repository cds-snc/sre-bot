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
from typing_extensions import Self

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
