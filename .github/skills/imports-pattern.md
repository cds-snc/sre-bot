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

```python
# ✅ Routes/Controllers
from infrastructure.services import SettingsDep

@router.get("/endpoint")
def handler(settings: SettingsDep):
    region = settings.aws.aws_region
```

```python
# ✅ Jobs/Modules/Services
from infrastructure.services import get_settings

def process():
    settings = get_settings()
    return settings.environment
```

```python
# ❌ FORBIDDEN - Direct Settings import
from infrastructure.configuration import Settings
settings = Settings()  # WRONG

from infrastructure.configuration import settings  # WRONG - doesn't exist
```

**Enforcement**: Only import `SettingsDep` or `get_settings` from `infrastructure.services`.

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
