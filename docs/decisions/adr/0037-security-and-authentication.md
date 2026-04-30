---
adr_id: ADR-0037
title: "Security & Authentication"
status: Accepted
decision_type: Feature
tier: Tier-4
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by: []
related_records:
  - ADR-0023
  - ADR-0062
related_packages: []
review_state: stale
---
# Security & Authentication

## Context

The application supports multiple transports (HTTP API, Slack commands) with different authentication mechanisms. HTTP requires JWT bearer tokens from trusted issuers; Slack uses request signing. Both require a consistent authenticated user model.

## Decision

HTTP endpoints require JWT Bearer tokens validated against trusted JWKS endpoints. Slack uses request signing (handled by platform layer). Get_current_user() dependency resolves authenticated principal for all protected endpoints. Multi-issuer JWKS validation supports multiple identity providers.

## Consequences

- ✅ Multiple identity providers supported via multi-issuer configuration
- ✅ JWKS keys are cached to avoid round-trips
- ✅ Authentication is centralized in one dependency
- ✅ Platform-specific auth is encapsulated in platform layer
- ⚠️ Requires ISSUER_CONFIG environment variable

---

## Authentication Model

**Decision**: All API endpoints (except webhooks) require a signed JWT Bearer token issued by a trusted identity provider.  The Slack transport layer uses Slack's own request-signing mechanism — JWT is not involved there.

Two transports, two auth mechanisms:

| Transport | Mechanism | Who verifies |
|---|---|---|
| HTTP (FastAPI) | JWT Bearer via JWKS | `get_current_user()` dependency |
| Slack commands | Slack request signing | `SlackPlatformProvider` (platform layer) |

Webhooks (`/hook/{webhook_id}`) are unauthenticated by design.

---

## JWT Validation

**Decision**: Multi-issuer JWKS validation.  Each trusted issuer (e.g. a Backstage or Okta tenant) is configured with its JWKS URI.  The `JWKSManager` maintains one `PyJWKClient` per issuer and caches responses.

**Configuration** (`ISSUER_CONFIG` env var — JSON):

```json
{
  "https://example.okta.com": {
    "jwks_uri": "https://example.okta.com/oauth2/v1/keys",
    "algorithms": ["RS256"],
    "audience": "sre-bot"
  }
}
```

**Implementation** (`infrastructure/security/`):

```python
# jwks.py — multi-issuer client cache
class JWKSManager:
    def __init__(self, issuer_config: Dict[str, Dict[str, Any]]): ...
    def get_jwks_client(self, issuer: str) -> Optional[PyJWKClient]: ...
    def warmup(self) -> None: ...  # called at application startup

# jwt.py — plain validation callable (not a FastAPI dep)
def validate_jwt_token(
    jwks_manager: JWKSManager,
    credentials: HTTPAuthorizationCredentials,
) -> Dict[str, Any]: ...
```

**Rules**:

- ✅ `JWKSManager` is a singleton — created once via `get_jwks_manager()` in `infrastructure.services`
- ✅ Keys are cached with `cache_jwk_set=True` — no round-trip per request
- ✅ `validate_jwt_token` is a plain callable; it is not a FastAPI dependency
- ✅ Error details from JWT libraries are never forwarded to callers (OWASP A02)
- ✅ JWT functions are sync (`def`) — typically CPU-bound token validation, no I/O
- ✅ For async routes, call sync JWT functions directly (FastAPI's thread pool handles them)
- ❌ Never expose raw JWT exceptions to client (forbidden by OWASP A02)

---

## get_current_user Dependency

**Decision**: A single reusable FastAPI `Security()` dependency resolves the authenticated principal for every protected endpoint.

```python
# infrastructure/security/current_user.py
def get_current_user(
    security_scopes: SecurityScopes,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    jwks_manager: Annotated[JWKSManager, Depends(get_jwks_manager)],
    identity_service: Annotated[IdentityService, Depends(get_identity_service)],
) -> User:
    ...
```

`SecurityScopes` is automatically populated by FastAPI from all `Security()` declarations in the route and its dependency chain.

Scope claims are extracted from either:

- `scope` — space-separated string (RFC 6749 / OAuth 2.0)
- `scp` — string array (Microsoft / Okta convention)

---

## Protected Routes

**Decision**: Route handlers declare authentication and scope requirements via `Security(get_current_user, scopes=[...])`.  Both the function and DI type aliases are accessed from `infrastructure.services` — the central namespace for all infrastructure.

```python
from fastapi import Security
from typing import Annotated
from infrastructure.identity.models import User
from infrastructure.services import get_current_user

# Authentication only — any valid JWT accepted:
@router.get("/me")
def get_me(
    current_user: Annotated[User, Security(get_current_user)],
) -> dict:
    return {"email": current_user.email}

# Authentication + scope check — token must carry the named scope:
@router.post("/access/sync-runs")
def sync(
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-sync"])],
) -> AccessSyncResponse:
    ...
```

Pre-built type alias for no-scope use:

```python
from infrastructure.services import CurrentUserDep

@router.get("/protected")
def endpoint(current_user: CurrentUserDep) -> dict:
    return {"email": current_user.email}
```

**Rules**:

- ✅ Import `get_current_user` and `CurrentUserDep` from `infrastructure.services` only
- ✅ Each protected feature package declares its own scope string (`sre-bot:<resource>`)
- ✅ 401 for missing/invalid token, 403 for insufficient scopes — never 500
- ❌ Never check auth manually inside the route body

---

## Startup Warmup

**Decision**: Security infrastructure is initialized at application startup in `lifespan.py`, not lazily on first request.

```python
# server/lifespan.py
def _initialize_security_services(app, settings, logger) -> None:
    if not settings.server.ISSUER_CONFIG:
        logger.warning("security_services_no_issuer_config")
        return
    jwks_manager = get_jwks_manager()  # creates + caches singleton
    jwks_manager.warmup()              # pre-creates PyJWKClient per issuer
    get_identity_service()             # creates + caches singleton
```

**Rules**:

- ✅ Singletons are populated during lifespan, not on first request
- ✅ Missing `ISSUER_CONFIG` logs a warning — any authenticated endpoint will return 500 at runtime
- ✅ Follows the same `get_<service>()` pattern as directory provider warmup
