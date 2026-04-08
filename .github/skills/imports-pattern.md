# Import Pattern Rules

**Enforcement**: CRITICAL - Violations block implementation

## Rules

### 1. All Imports at Module Top

```python
# ✅ CORRECT
from infrastructure.services import get_settings
from infrastructure.operations import OperationResult
import structlog

def my_function():
    settings = get_settings()
    return OperationResult.success()
```

```python
# ❌ FORBIDDEN - Never import inside functions
def my_function():
    from infrastructure.services import get_settings  # WRONG
    settings = get_settings()
```

**Enforcement**: Scan for imports inside function bodies. Reject code with lazy imports.

---

### 2. Settings Import Pattern

**Core infrastructure** (`infrastructure/`, `server/`, legacy `modules/`) — use the central `Settings` singleton via `infrastructure.services`:

```python
# ✅ HTTP route handlers — use FastAPI DI type alias
from infrastructure.services import SettingsDep

@router.get("/endpoint")
def handler(settings: SettingsDep):
    region = settings.aws.aws_region
```

```python
# ✅ providers.py only — extract a slice and inject into the service
# infrastructure/services/providers.py
from infrastructure.services.providers import get_settings

@lru_cache(maxsize=1)
def get_aws_clients() -> AWSClients:
    settings = get_settings()
    return AWSClients(aws_settings=settings.aws)  # pass the slice, not settings
```

**Feature packages** (`packages/<name>/`) — define their own `BaseSettings`. Two patterns depending on whether env vars already exist in production SSM. Never import `get_settings` from `infrastructure.services`:

```python
# ✅ packages/my_feature/settings.py — Pattern A: new package, dedicated SSM parameter
# env_prefix handles the namespace; no Field(alias) needed
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class MyFeatureSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MY_FEATURE_")
    api_key: str        # reads MY_FEATURE_API_KEY
    dry_run: bool = False

@lru_cache(maxsize=1)
def get_my_feature_settings() -> MyFeatureSettings:
    return MyFeatureSettings()
```

```python
# ✅ packages/incident/settings.py — Pattern B: migrated module, keys already in SSM
# No env_prefix; Field(alias) maps each field to its exact deployed env var name
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class IncidentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
    channel: str = Field(default="", alias="INCIDENT_CHANNEL")
```

```python
# ✅ packages/my_feature/service.py  — consume feature settings locally
from packages.my_feature.settings import get_my_feature_settings

def do_something():
    settings = get_my_feature_settings()
    return settings.api_key
```

```python
# ❌ FORBIDDEN - Direct Settings instantiation
from infrastructure.configuration import Settings
settings = Settings()  # WRONG

# ❌ FORBIDDEN - Feature package importing the central get_settings
# packages/my_feature/anything.py
from infrastructure.services import get_settings  # WRONG in feature packages
settings = get_settings().my_feature_section      # WRONG

# ❌ FORBIDDEN - Passing the full Settings to a service that needs only a slice
return MyService(settings=get_settings())  # WRONG — pass settings.my_section
```

**Enforcement**: `get_settings()` from `infrastructure.services` is only called inside `providers.py`. Feature packages own their settings via a local `BaseSettings` + `@lru_cache` provider.

---

### 3. Service Provider Imports

```python
# ✅ CORRECT
from infrastructure.services import (
    get_aws_clients,
    get_platform_service,
    get_identity_service,
)

clients = get_aws_clients()
```

```python
# ❌ FORBIDDEN - Direct service imports
from infrastructure.clients.aws import AWSClients
clients = AWSClients(settings)  # WRONG - use provider
```

**Enforcement**: Import services from `infrastructure.services` module only.

---

### 4. Import Order

```python
# ✅ CORRECT ORDER
# 1. Standard library
import os
from typing import Dict, Any

# 2. Third-party
import structlog
from fastapi import APIRouter

# 3. Local infrastructure
from infrastructure.services import get_settings, SettingsDep
from infrastructure.operations import OperationResult

# 4. Local modules
from modules.groups.schemas import GroupSchema
```

**Enforcement**: Standard → Third-party → Infrastructure → Modules.

---

## Pre-Implementation Checklist

Before generating code:

1. ☐ All imports at top of file (not in functions)
2. ☐ Settings via `SettingsDep` or `get_settings()`
3. ☐ Services via `get_*()` providers
4. ☐ Import order: stdlib → third-party → infrastructure → modules
5. ☐ No direct instantiation of Settings or services

**If any checklist item fails, do NOT generate code. Ask user to clarify.**
