# Configuration Management

## Settings Singleton Pattern

ONE Settings instance per process via `@lru_cache`. Validation runs on first call; invalid config raises `ValidationError` and terminates startup.

```python
# infrastructure/services/providers.py
from functools import lru_cache
from infrastructure.configuration import Settings

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton Settings instance - created once per ECS task."""
    return Settings()
```

**Routes** (FastAPI dependency injection):
```python
import structlog
from infrastructure.services import SettingsDep

logger = structlog.get_logger()

@router.get("/example")
def example(settings: SettingsDep):
    log = logger.bind()
    log.info("example_called")
    return {"region": settings.aws.aws_region}
```

**Jobs/Modules** (background tasks):
```python
from infrastructure.services import get_settings

def background_job():
    settings = get_settings()  # Returns cached singleton
    return {"region": settings.aws.aws_region}
```

**Providers** (infrastructure only):
```python
from functools import lru_cache
from infrastructure.services.providers import get_settings
from my_service import MyService

@lru_cache(maxsize=1)
def get_my_service() -> MyService:
    settings = get_settings()  # Cached singleton
    return MyService(settings=settings)
```

**Anti-patterns**:
```python
# ❌ FORBIDDEN: Direct instantiation
from infrastructure.configuration import Settings
settings = Settings()

# ❌ FORBIDDEN: Repeated calls in one scope
def process():
    region = get_settings().aws.aws_region
    env = get_settings().environment
    return {"region": region, "env": env}
```

---

## Rules

- ✅ Use `get_settings()` from `infrastructure.services`
- ✅ Routes use `SettingsDep` type alias
- ✅ Services receive settings via constructor
- ❌ NEVER: `Settings()`
- ❌ NEVER: `from infrastructure.configuration import settings`
- ❌ NEVER: Call `get_settings()` inside service constructors (receive as parameter instead)

---

## Environment Variables

Nested settings use double underscore delimiter.

```bash
# .env
AWS__AWS_REGION=us-east-1
SLACK__SLACK_TOKEN=xoxb-token
```

```python
settings.aws.aws_region  # us-east-1
settings.slack.slack_token  # xoxb-token
```

Rules:
- ✅ Use `__` for nested settings
- ✅ Uppercase for env var names
- ❌ Single underscore for nesting
