# Type Hints Pattern

**Enforcement**: REQUIRED for all functions

## Rule

All functions must have type hints for parameters and return values.

---

## Function Pattern

```python
from typing import Dict, List, Any, Optional

def process_users(
    user_ids: List[str],
    settings: Settings,
    include_inactive: bool = False
) -> Dict[str, Any]:
    """Process users and return results.
    
    Args:
        user_ids: List of user IDs to process.
        settings: Application settings.
        include_inactive: Include inactive users (default False).
    
    Returns:
        Dict containing processed user data.
    """
    results = {}
    for user_id in user_ids:
        results[user_id] = process_user(user_id)
    return results
```

**Pattern**: Type all parameters and return value. Add docstring.

---

## Common Types

```python
# Basic types
def func(name: str, count: int, active: bool) -> str:
    pass

# Optional
def func(value: Optional[str] = None) -> Optional[int]:
    pass

# Collections
def func(items: List[str]) -> Dict[str, Any]:
    pass

def func(mapping: Dict[str, int]) -> List[Any]:
    pass

# Custom types
from infrastructure.configuration import Settings
from infrastructure.operations import OperationResult

def func(settings: Settings) -> OperationResult:
    pass
```

---

## Class Pattern

```python
class UserService:
    """User service with typed methods."""
    
    def __init__(self, settings: Settings) -> None:
        """Initialize service.
        
        Args:
            settings: Application settings.
        """
        self.settings = settings
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID.
        
        Args:
            user_id: User identifier.
        
        Returns:
            User data dict or None if not found.
        """
        return {"id": user_id, "name": "Test"}
    
    def list_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List users.
        
        Args:
            limit: Maximum number of users to return.
        
        Returns:
            List of user data dicts.
        """
        return []
```

**Pattern**: Type all methods including `__init__`. `__init__` returns `None`.

---

## OperationResult Pattern

```python
from infrastructure.operations import OperationResult

def sync_groups() -> OperationResult:
    """Sync groups from provider.
    
    Returns:
        OperationResult with sync status.
    """
    try:
        groups = fetch_groups()
        return OperationResult.success(data=groups)
    except Exception as e:
        return OperationResult.permanent_error(
            message=str(e),
            code="SYNC_FAILED"
        )
```

**Pattern**: Functions returning results use `-> OperationResult`.

---

## Forbidden Patterns

```python
# ❌ No type hints
def process(data):  # WRONG
    return data

# ❌ Missing return type
def process(data: dict):  # WRONG - missing -> Type
    return data

# ❌ Missing parameter types
def process(data) -> dict:  # WRONG - data has no type
    return data

# ❌ Using Any unnecessarily
def process(data: Any) -> Any:  # WRONG - be specific
    return data

# Better:
def process(data: Dict[str, str]) -> Dict[str, int]:
    return {k: len(v) for k, v in data.items()}
```

---

## FastAPI Dependency Pattern

```python
from infrastructure.services import SettingsDep
from fastapi import Depends

# ✅ Using SettingsDep
@router.get("/config")
def get_config(settings: SettingsDep) -> Dict[str, str]:
    return {"env": settings.environment}

# ✅ Custom dependency
def get_current_user() -> Dict[str, str]:
    return {"id": "123", "name": "User"}

@router.get("/me")
def get_me(user: Dict[str, str] = Depends(get_current_user)) -> Dict[str, str]:
    return user
```

**Pattern**: Dependencies use `= Depends(...)`, return type specified.

---

## Pre-Implementation Checklist

Before generating functions:

1. ☐ All parameters have type hints
2. ☐ Return type specified with `->`
3. ☐ `__init__` returns `-> None`
4. ☐ Use `Optional[T]` for nullable values
5. ☐ Use specific types (not `Any` unless required)
6. ☐ Docstring with Args/Returns sections
7. ☐ OperationResult for operation functions

**Mypy must pass: `mypy .` with no errors.**
