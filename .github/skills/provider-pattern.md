# Provider Pattern

**Reference**: `docs/decisions/tier-1-foundation/application-lifecycle/04-provider-discovery.md`

## Pattern

Providers use `@lru_cache` singleton pattern. Services receive dependencies via `__init__`.

---

## Provider Function Template

```python
# infrastructure/services/*.py
from functools import lru_cache
from infrastructure.services import get_settings

@lru_cache(maxsize=1)
def get_my_service() -> MyService:
    """Get singleton service instance.
    
    Returns:
        MyService: Configured service singleton.
    """
    settings = get_settings()
    return MyService(settings=settings)
```

**Pattern**: `@lru_cache(maxsize=1)` + dependency injection.

---

## Service Class Template

```python
# infrastructure/services/my_service.py
from infrastructure.configuration import Settings

class MyService:
    """Service with dependency injection."""
    
    def __init__(self, settings: Settings):
        """Receive dependencies via __init__.
        
        Args:
            settings: Application settings.
        """
        self.settings = settings
        self.region = settings.aws.aws_region
    
    def process(self) -> str:
        """Process with injected settings."""
        return f"Processing in {self.region}"
```

**Pattern**: Receive all dependencies in `__init__`, store as instance variables.

---

## Module-Level Registry Pattern

```python
# modules/groups/providers/__init__.py
from typing import Dict, Optional

_PROVIDERS: Dict[str, Any] = {}
_PRIMARY_PROVIDER: Optional[str] = None

def load_providers() -> str:
    """Discover and load providers at startup."""
    global _PROVIDERS, _PRIMARY_PROVIDER
    
    settings = get_settings()
    
    # Lazy import - only load if configured
    if settings.google and settings.google.credentials_base64:
        from modules.groups.providers.google import GoogleGroupProvider
        _PROVIDERS["google"] = GoogleGroupProvider(settings=settings)
        if not _PRIMARY_PROVIDER:
            _PRIMARY_PROVIDER = "google"
    
    return _PRIMARY_PROVIDER

def get_active_providers() -> Dict[str, Any]:
    """Get all active providers."""
    return _PROVIDERS.copy()
```

**Pattern**: Module-level dict populated at startup, lazy imports for conditional providers.

---

## Lazy Import Pattern

```python
def load_providers():
    """Load providers with lazy imports."""
    settings = get_settings()
    
    # Check config first
    if settings.google:
        # Import only if configured
        from modules.groups.providers.google import GoogleProvider
        provider = GoogleProvider(settings=settings)
```

**Pattern**: Check config, then import. Prevents loading unconfigured providers.

---

## Forbidden Patterns

```python
# ❌ Provider without @lru_cache
def get_service():
    return MyService()  # WRONG - creates new instance each time

# ❌ Service fetching dependencies
class MyService:
    def __init__(self):
        self.settings = get_settings()  # WRONG - receive via parameter

# ❌ Top-level imports for conditional providers
from modules.groups.providers.google import GoogleProvider  # WRONG
# Import happens even if not configured

def load_providers():
    if settings.google:
        provider = GoogleProvider()  # Already imported above

# ❌ Direct instantiation in provider
@lru_cache(maxsize=1)
def get_service():
    # WRONG - hardcoded, not using settings
    return MyService(region="us-east-1")
```

---

## Pre-Implementation Checklist

Before creating provider/service:

1. ☐ Provider function has `@lru_cache(maxsize=1)`
2. ☐ Provider calls `get_settings()` 
3. ☐ Service receives `Settings` in `__init__`
4. ☐ Conditional providers use lazy imports
5. ☐ Module-level registry for provider collections
6. ☐ Registry populated at startup, immutable after
