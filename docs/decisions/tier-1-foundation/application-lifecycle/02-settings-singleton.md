# Settings Singleton Pattern

ONE Settings instance per ECS task via `@lru_cache`.

---

## Implementation

```python
# infrastructure/services/providers.py
from functools import lru_cache
from infrastructure.configuration import Settings

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton Settings - created once per ECS task."""
    return Settings()  # Pydantic validates on instantiation
```

```python
# infrastructure/configuration/__init__.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application configuration from environment."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )
    
    environment: str = "development"
    log_level: str = "INFO"
    
    class AWSConfig(BaseSettings):
        aws_region: str
        aws_account_id: str
    
    aws: AWSConfig
```

---

## Environment Variables

Nested config uses double underscore:

```bash
# .env
ENVIRONMENT=production
LOG_LEVEL=INFO
AWS__AWS_REGION=us-east-1
AWS__AWS_ACCOUNT_ID=123456789012
```

---

## Usage

**Routes** (dependency injection):
```python
from infrastructure.services import SettingsDep

@router.get("/")
def handler(settings: SettingsDep):
    return {"region": settings.aws.aws_region}
```

**Jobs/Services**:
```python
from infrastructure.services import get_settings

settings = get_settings()  # Returns cached singleton
return {"region": settings.aws.aws_region}
```

---

## Rules

- ✅ Use `@lru_cache(maxsize=1)`
- ✅ Use double underscore for nested settings
- ✅ Validate at instantiation time
- ❌ NEVER: `Settings()`
- ❌ NEVER: Direct import from `infrastructure.configuration`
- ❌ NEVER: Call `get_settings()` in service constructors (receive as parameter)
