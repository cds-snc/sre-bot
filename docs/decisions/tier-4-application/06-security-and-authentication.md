# Security & Authentication

TODO - Validate that this is still accurate; protected endpoints are currently designed to only be accessed by trusted JWKS from Backstage.

## JWT Authentication

**Decision**: JWT tokens for API authentication.

**Implementation**:
```python
# server/utils.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer

oauth2_scheme = HTTPBearer(auto_error=False)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    request: Request,
    token: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Rules**:
- ✅ Use `HTTPBearer` for token extraction
- ✅ Set token expiration
- ✅ Validate tokens in dependency
- ✅ Raise 401 for auth failures
- ❌ Never log tokens or secrets

---

## Protected Routes

**Decision**: Use dependency injection.

**Implementation**:
```python
from server.utils import get_current_user

@router.get("/protected")
def protected_endpoint(
    current_user: dict = Depends(get_current_user),
):
    # User is authenticated
    return {"user_id": current_user["sub"]}
```

**Rules**:
- ✅ Add `Depends(get_current_user)` to protected routes
- ✅ Extract user info from dependency
- ❌ Don't check auth manually in route body