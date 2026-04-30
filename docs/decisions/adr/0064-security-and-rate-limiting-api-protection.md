---
adr_id: ADR-0064
title: "Security and Rate-Limiting API Protection"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Security and Access Control
secondary_domains:
  - Transport and API
  - Dependency and Composition
  - Configuration and Secrets
owners:
  - SRE Team
date_created: 2026-04-30
last_updated: 2026-04-30
last_reviewed: 2026-04-30
next_review_due: 2026-08-28
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0055
  - ADR-0056
  - ADR-0060
  - ADR-0061
  - ADR-0063
  - ADR-0065
  - ADR-0077
  - ADR-0078
impacts:
  - ADR-0062
supersedes:
  - ADR-0037
  - ADR-0038
superseded_by: []
review_state: current
related_records:
  - ADR-0046
  - ADR-0049
  - ADR-0050
  - ADR-0054
  - ADR-0076
related_packages:
  - app/infrastructure/security
  - app/infrastructure/http
  - app/server
  - app/api
---

# Security and Rate-Limiting API Protection

## Context

- **Problem statement:** Two legacy ADRs (ADR-0037, ADR-0038) defined security and rate-limiting patterns at Tier-4 (Feature Decision). ADR-0037 established JWT bearer token validation, multi-issuer JWKS caching, the `get_current_user` Security dependency, and Slack request-signing encapsulation. ADR-0038 established layered rate limiting (WAF → ALB → SlowAPI) with sentinel bypass and custom key functions. Both are marked `review_state: stale` and predate the Tier-2 standards that now govern settings (ADR-0055), provider composition (ADR-0056), error mapping (ADR-0060), identity contracts (ADR-0061), API composition (ADR-0063), infrastructure service contracts (ADR-0077), and platform services (ADR-0078). The codebase has working security infrastructure in `infrastructure/security/` that aligns with the legacy ADRs but exhibits compliance gaps against the current architectural stack — notably: unstructured 401/403/429 error responses (violating ADR-0060 Standard 1), no Protocol contract for `JWKSManager` (violating ADR-0077 Standard 1 Category A classification), overly permissive CORS configuration in production, and non-fail-fast behavior when `ISSUER_CONFIG` is missing at startup.

- **Business/operational drivers:**
  - Consolidate security authentication and rate-limiting protection into a single Tier-2 standard, replacing fragmented Tier-4 authority.
  - Codify JWT authentication as a FastAPI `Security()` dependency pattern — not middleware — consistent with ADR-0063 Standard 4.
  - Align error responses for 401 (Unauthorized), 403 (Forbidden), and 429 (Too Many Requests) with the RFC 9457 error schema defined by ADR-0060 Standard 1.
  - Classify security infrastructure services per ADR-0077, establishing Protocol contracts where required.
  - Define CORS policy that follows OWASP REST Security guidance: restrict origins explicitly, never use wildcard origins with credentials.
  - Codify security-relevant response headers for API endpoints per OWASP REST Security Cheat Sheet.
  - Establish rate-limiting architecture that separates infrastructure-layer flood protection (WAF/ALB) from application-layer business-context limiting (SlowAPI).
  - Define security settings dissolution following ADR-0055 patterns — narrow slices, no monolithic Settings exposure.

- **Constraints:**
  - Authentication is implemented as a FastAPI `Security()` dependency, not ASGI middleware (ADR-0063 Standard 4).
  - Security services are consumed through `Annotated[Protocol, Depends(provider)]` aliases from `dependencies.py` (ADR-0048 B2, ADR-0056 Standard 4).
  - Security service singletons are initialized during lifespan startup (ADR-0046), not lazily on first request.
  - Error responses for authentication/authorization/rate-limiting failures must use the structured error schema (ADR-0060 Standard 1).
  - Security settings follow the dissolution model (ADR-0055) — partitioned into `SecuritySettings`, not scattered across `ServerSettings`.
  - Identity resolution from JWT claims is delegated to `IdentityService` (ADR-0061 Standard 3) — this ADR governs the JWT validation boundary upstream of identity resolution.
  - Type boundaries: `Protocol` for service contracts, `BaseModel` for API I/O schemas, `@dataclass(frozen=True)` for internal value types (ADR-0065).
  - Managed service delegation: JWT validation libraries (PyJWT, PyJWKClient) are Tier 2 industry-standard wrappers (ADR-0045 P7). SlowAPI is Tier 2 for rate limiting. Neither requires in-house re-implementation.

- **Non-goals:**
  - This record does not define identity resolution logic (user lookup, group membership) — governed by ADR-0061.
  - This record does not define OAuth/OIDC flow implementation (authorization code, client credentials) — if needed, a separate Tier-4 Integration Decision is appropriate.
  - This record does not prescribe IDP selection or JWT algorithm policy — those are deployment-configuration concerns.
  - This record does not define platform-transport authentication (Slack request signing, Teams bot validation) — governed by ADR-0061 Standard 3 and ADR-0078.
  - This record does not define WAF rule authoring or Terraform infrastructure — WAF configuration is an operational concern governed by infrastructure-as-code practices, not an application architecture decision.
  - This record does not define access control models (RBAC, ABAC) — that is a feature-domain concern for ADR-0066.

## Decision

- **Chosen approach:** Consolidate ADR-0037 and ADR-0038 into a single Tier-2 standard that defines JWT authentication dependency patterns, rate-limiting architecture, security error responses, CORS policy, security headers, security settings dissolution, and infrastructure service classification — all aligned with the current Wave 3–5 constraint framework.
- **Why this approach:** The two legacy ADRs addressed complementary facets of API protection (authentication and rate limiting) at Tier-4. Both are cross-cutting concerns affecting all API routes, making Tier-2 the correct classification. Consolidation establishes single authority over the security boundary between external requests and internal service invocations.

---

### Standard 1: JWT Authentication Dependency

All protected HTTP API endpoints must authenticate requests using a FastAPI `Security()` dependency that validates JWT Bearer tokens. Authentication is not implemented as middleware (ADR-0063 Standard 4).

**Rules:**

- **S1-R1**: The `get_current_user` dependency is the single entry point for HTTP API authentication. It must be consumed via `Security(get_current_user)` or `Security(get_current_user, scopes=[...])` — never called directly.
- **S1-R2**: The dependency validates JWT signature, expiration (`exp`), audience (`aud`), and issuer (`iss`) claims before returning an authenticated principal. Claims not present in the token must cause a 401 response.
- **S1-R3**: Scope enforcement uses FastAPI's `SecurityScopes` mechanism. Scope claims are extracted from both `scope` (RFC 6749 space-separated string) and `scp` (array format, Microsoft/Okta convention). If the route declares required scopes and the token lacks any of them, the dependency must return a 403 response.
- **S1-R4**: The dependency must never raise unhandled exceptions — all failure modes must be mapped to `HTTPException` with status 401 or 403 and a response body conforming to ADR-0060 Standard 1 (RFC 9457 error schema).
- **S1-R5**: JWT validation functions (`validate_jwt_token`, `get_issuer_from_token`) are synchronous (`def`). They are CPU-bound operations (signature verification, claims parsing) with no I/O. FastAPI's thread pool handles them correctly for async route handlers.
- **S1-R6**: The `get_current_user` dependency chain must be testable by overriding `get_current_user` via `app.dependency_overrides` in test fixtures (ADR-0062 Standard 6). Test doubles must not require a real JWKS endpoint.
- **S1-R7**: Pre-built DI type aliases (`CurrentUserDep`, `JWKSManagerDep`) are defined in `infrastructure/services/dependencies.py` and are the only import surface for route handlers.

**Authentication flow:**

```
Request → Bearer token extracted → issuer extracted (unverified)
  → JWKS client resolved for issuer → signing key fetched
  → JWT decoded and verified (signature, exp, aud, iss)
  → scopes extracted and checked against SecurityScopes
  → identity resolved via IdentityService (ADR-0061)
  → User returned to route handler
```

**Error responses:**

| Failure | HTTP Status | `type` | `error` |
|---------|-------------|--------|---------|
| Missing/malformed Bearer token | 401 | `/problems/authentication-required` | `AUTHENTICATION_REQUIRED` |
| Invalid/expired JWT signature | 401 | `/problems/token-invalid` | `TOKEN_INVALID` |
| Issuer not configured | 401 | `/problems/token-invalid` | `TOKEN_INVALID` |
| Insufficient scopes | 403 | `/problems/insufficient-scope` | `INSUFFICIENT_SCOPE` |
| Identity resolution failure | 401 | `/problems/identity-unknown` | `IDENTITY_UNKNOWN` |

All error responses must omit internal details (issuer URLs, JWKS endpoints, library error messages) per ADR-0060 Standard 3.

---

### Standard 2: JWKS Manager Service Contract

The `JWKSManager` is responsible for multi-issuer JWKS client lifecycle and key resolution. It is classified as **Category A** (contract-required, backing service: external JWKS endpoints) per ADR-0077.

**Rules:**

- **S2-R1**: `JWKSManager` must implement a `Protocol` contract defining its public interface. The Protocol must be defined in `infrastructure/security/` and exported via `infrastructure.services`.

  ```python
  class JWKSManagerProtocol(Protocol):
      def get_jwks_client(self, issuer: str) -> PyJWKClient | None: ...
      def warmup(self) -> None: ...
      def clear_cache(self, issuer: str | None = None) -> None: ...
  ```

- **S2-R2**: The concrete implementation delegates to `PyJWKClient` (Tier 2 managed service delegation per ADR-0045 P7). `PyJWKClient` instances are cached per issuer with `cache_jwk_set=True`.
- **S2-R3**: The `warmup()` method pre-initializes all configured issuer clients during lifespan startup (Standard 5). This ensures no lazy initialization on first request.
- **S2-R4**: The singleton is constructed via `get_jwks_manager()` provider in `providers.py` using `@lru_cache(maxsize=1)` (ADR-0056 Standard 3).
- **S2-R5**: The DI alias `JWKSManagerDep = Annotated[JWKSManagerProtocol, Depends(get_jwks_manager)]` is defined in `dependencies.py` (ADR-0056 Standard 4).

**Delegation tier:** Tier 2 — industry-standard library wrapper. PyJWT and PyJWKClient are stable, widely adopted libraries. Custom re-implementation is not warranted.

---

### Standard 3: Rate-Limiting Architecture

Rate limiting is implemented as a layered defense strategy. Each layer has a distinct purpose and scope.

**Rules:**

- **S3-R1: Infrastructure layer** (WAF and ALB): Provides global flood protection, IP reputation blocking, and connection-level limits. WAF rate-based rules use IP aggregation. This layer operates without application context (no authenticated user, no route semantics). Configuration is an infrastructure-as-code concern, not governed by this ADR.

- **S3-R2: Application layer** (SlowAPI): Provides fine-grained, business-context-aware rate limiting at the route level. Application-layer rate limiting is used only where infrastructure-layer protection is insufficient — specifically when the rate limit decision requires:
  - Authenticated user identity (per-user quotas)
  - Route-specific semantics (different limits for read vs. write operations)
  - Business-context bypass (monitoring/sentinel requests)

- **S3-R3: Limiter singleton**: The SlowAPI `Limiter` instance is created via `get_limiter()` provider in `providers.py` using `@lru_cache(maxsize=1)`. It is registered on `app.state.limiter` during application startup.

- **S3-R4: Rate limit key functions**: The default key function is IP-based (`get_remote_address`). Custom key functions may bypass rate limiting for monitoring requests (sentinel pattern) by returning `None`. Custom key functions must not log or expose client IP addresses beyond what is necessary for rate limit computation.

- **S3-R5: Decorator ordering**: Rate limit decorators must be placed below the route decorator (SlowAPI requirement):
  ```python
  @router.get("/endpoint")       # route decorator first
  @limiter.limit("50/minute")    # rate limit second
  async def endpoint(request: Request): ...
  ```

- **S3-R6: Request parameter**: Rate-limited endpoints must explicitly accept a `Request` parameter (SlowAPI requirement). This is the standard FastAPI `Request` object.

- **S3-R7: Service classification**: The rate limiter is **Category B** (shared utility, concrete OK) per ADR-0077. No Protocol contract required — SlowAPI's `Limiter` is a concrete utility with no backing service to abstract.

---

### Standard 4: Rate-Limiting Error Response

Rate-limiting error responses must conform to ADR-0060 Standard 1 (RFC 9457 error schema).

**Rules:**

- **S4-R1**: Rate limit exceeded responses must use HTTP status 429 (Too Many Requests).
- **S4-R2**: The response body must conform to the structured error schema:

  ```json
  {
    "type": "/problems/rate-limited",
    "status": 429,
    "title": "Rate limit exceeded",
    "detail": null,
    "error": "RATE_LIMITED",
    "retry_after": null
  }
  ```

- **S4-R3**: The `detail` field must not include internal rate limit counters, client IP addresses, or rate limit bucket keys.
- **S4-R4**: The custom `RateLimitExceeded` exception handler must be registered at app level via `app.add_exception_handler()` during startup (Standard 5).
- **S4-R5**: Rate limit events must be logged via structured logging (ADR-0054) with fields: `event="rate_limit_exceeded"`, `path`, `key_type` (IP/user/sentinel). Client IP may be logged server-side but must not appear in the response body.

---

### Standard 5: Security Startup and Lifespan

Security services are initialized during the application lifespan startup phase (ADR-0046 Standard 2), not lazily on first request.

**Rules:**

- **S5-R1**: `JWKSManager` is constructed and warmed up during lifespan. Warmup pre-initializes `PyJWKClient` instances for all configured issuers.
- **S5-R2**: `IdentityService` is constructed during lifespan (delegated to ADR-0061).
- **S5-R3**: The SlowAPI `Limiter` is constructed and registered on `app.state` during lifespan.
- **S5-R4**: The `RateLimitExceeded` exception handler is registered during lifespan.
- **S5-R5: Fail-fast for missing security configuration**: If `ISSUER_CONFIG` is empty or missing at startup, the application must log a warning with `event="security_services_degraded"`. The application may start in degraded mode — authenticated endpoints will return 401 at runtime. This is acceptable for non-production environments and development workflows where not all identity providers are configured. The startup log must clearly indicate the degraded state.

  **Rationale for degraded-start (not fail-fast):** The application serves unauthenticated endpoints (health checks, webhooks, Slack command handlers) that must remain available even without JWT configuration. Failing startup for missing ISSUER_CONFIG would block deployment of the full application for a configuration subset. The degraded-start approach is explicitly chosen over fail-fast for this specific service.

- **S5-R6: Lifespan initialization ordering**: Security service initialization must occur after settings loading and before route registration. The initialization function must be a dedicated phase in the lifespan (e.g., `_initialize_security_services`) with structured logging of initialization state.

---

### Standard 6: Security Settings Dissolution

Security-related settings follow the dissolution model (ADR-0055 Standard 1). Security configuration is partitioned into focused settings slices, not scattered across a monolithic `ServerSettings`.

**Rules:**

- **S6-R1**: JWT issuer configuration (`ISSUER_CONFIG`) resides in the security settings slice. The settings model validates the issuer configuration structure at construction time (Pydantic field validators).
- **S6-R2**: The dev bypass token (`DEV_BYPASS_TOKEN`) resides in the security settings slice. It is a non-production-only configuration — the settings model must validate that `DEV_BYPASS_TOKEN` is not set when `is_production` is true.
- **S6-R3**: Security services receive the narrowest settings slice needed (ADR-0055 Standard 2). `JWKSManager` receives only issuer configuration, not the full settings object. `get_current_user` accesses only the security settings slice and `is_production` flag.
- **S6-R4**: Security settings are loaded via `get_security_settings()` provider with `@lru_cache(maxsize=1)` in `providers.py`. This provider is independent of the root `get_settings()` provider.

**Migration note:** Current security settings reside in `ServerSettings` (inside `infrastructure/configuration/infrastructure/server.py`). Migration to a dedicated `SecuritySettings` model is a code change governed by ADR-0055's dissolution roadmap. This ADR establishes the target state; the timeline follows the settings dissolution implementation plan.

---

### Standard 7: CORS Policy

Cross-Origin Resource Sharing (CORS) configuration must follow OWASP REST Security guidance and be consistent across environments.

**Rules:**

- **S7-R1**: Production CORS must not use wildcard (`*`) origins. Allowed origins must be explicitly enumerated based on known consumer domains.
- **S7-R2**: `allow_credentials=True` must only be used with explicitly enumerated origins (per CORS specification: browsers reject `Access-Control-Allow-Credentials: true` when `Access-Control-Allow-Origin: *`).
- **S7-R3**: Non-production environments may use a restricted localhost origin list for development workflows.
- **S7-R4**: CORS is configured as middleware at the outermost layer (ADR-0063 Standard 4 middleware ordering).
- **S7-R5**: Allowed HTTP methods and headers should be restricted to those actually used by the API, not wildcard `*`.

**Migration note:** Current production CORS uses `allow_origins=["*"]` with `allow_credentials=True`. This is a CORS specification violation (browsers reject credentialed requests with wildcard origins). Migration to explicit origins is a code change that requires coordination with frontend consumers to enumerate allowed origins.

---

### Standard 8: Security Response Headers

API responses must include security-relevant HTTP headers per OWASP REST Security Cheat Sheet recommendations.

**Rules:**

- **S8-R1**: All API responses must include:
  - `X-Content-Type-Options: nosniff` — prevents MIME sniffing.
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` — enforces HTTPS. Only applicable when served behind TLS termination (ALB).
  - `Cache-Control: no-store` — prevents caching of API responses containing sensitive data.
  - `Content-Security-Policy: frame-ancestors 'none'` — prevents framing of API responses.

- **S8-R2**: Security headers are applied via middleware or response hooks, not per-route. The implementation must not require route handlers to set headers manually.

- **S8-R3**: The `Referrer-Policy: no-referrer` header should be included for API responses to prevent referrer leakage.

**Implementation note:** Security headers can be added via a lightweight ASGI middleware or FastAPI middleware. The middleware must be ordered per ADR-0063 Standard 4 — after CORS (so CORS headers are not overwritten) and before route handlers.

---

### Standard 9: Dev Bypass Token

A development bypass token allows non-production environments to skip JWT validation for testing and development workflows.

**Rules:**

- **S9-R1**: The dev bypass token is enabled only when `is_production` is false AND `DEV_BYPASS_TOKEN` is set in security settings.
- **S9-R2**: When bypass is active, the `get_current_user` dependency returns a synthetic User with all requested scopes granted.
- **S9-R3**: Every bypass usage must be logged with `event="dev_bypass_token_used"` and the route path, via structured logging (ADR-0054).
- **S9-R4**: The bypass token must never be accepted in production — this is enforced at the settings validation level (Standard 6, S6-R2) and at the dependency level (double-check in `get_current_user`).
- **S9-R5**: The bypass token must be a sufficiently long random string (≥32 characters). Short or guessable bypass tokens should trigger a startup warning.

---

### Standard 10: Webhook Authentication Exemption

Webhook endpoints (`/hook/{webhook_id}`) are unauthenticated by design — they do not use JWT Bearer authentication.

**Rules:**

- **S10-R1**: Webhook routes must not include `get_current_user` in their dependency chain.
- **S10-R2**: Webhook authentication (if any) is provider-specific (e.g., Slack request signing) and is handled by the platform transport layer (ADR-0061 Standard 3, ADR-0078).
- **S10-R3**: Webhook endpoints must still be protected by infrastructure-layer rate limiting (WAF rate-based rules) and application-layer rate limiting where business context is relevant.
- **S10-R4**: The unauthenticated status of webhook endpoints must be explicitly documented in OpenAPI metadata (ADR-0063 Standard 3).

---

## Alternatives Considered

1. **Maintain two separate ADRs (ADR-0037 and ADR-0038):**
   - Pros: Existing records cover the space; less work.
   - Cons: Overlapping authority at Tier-4; both are stale; neither aligns with Wave 3–5 constraint framework (ADR-0055, ADR-0060, ADR-0077).
   - Why not chosen: Consolidation at Tier-2 establishes single authority and aligns with ADR-0051 taxonomy.

2. **Security as middleware instead of dependency:**
   - Pros: Applied globally; less per-route ceremony.
   - Cons: Middleware cannot use FastAPI's `SecurityScopes` for per-route scope enforcement. Middleware authentication loses route-level granularity (some routes are unauthenticated). Violates ADR-0063 Standard 4 which mandates auth as Depends, not middleware.
   - Why not chosen: Dependency-based authentication is more composable, testable, and granular.

3. **Remove application-layer rate limiting (rely on WAF only):**
   - Pros: Simpler; fewer dependencies.
   - Cons: WAF operates on IP addresses and request patterns — it cannot enforce per-user quotas, route-semantic limits, or business-context bypass. Application-layer rate limiting addresses a fundamentally different threat model (abuse by authenticated users, not network-level floods).
   - Why not chosen: Layered defense provides defense-in-depth.

4. **Promote to Tier-1 Principle:**
   - Pros: Maximum authority.
   - Cons: This is an implementation convention (how to wire JWT validation, how to configure rate limiting), not a foundational architectural invariant. Tier-2 Standard is correct per ADR-0051 classification rules.
   - Why not chosen: Tier classification must match content scope.

5. **Fail-fast startup for missing ISSUER_CONFIG:**
   - Pros: Prevents degraded state; ensures all endpoints are fully functional at startup.
   - Cons: Blocks deployment when only a subset of configuration is missing. Unauthenticated endpoints (health, webhooks, Slack handlers) should remain available. Overly strict for development and non-production environments.
   - Why not chosen: Degraded-start with explicit warning logging balances operational resilience with configuration flexibility. This is a deliberate deviation from ADR-0045 P4 (fail-fast) — documented with accepted risk.

## Consequences

- **Positive impacts:**
  - Single authoritative standard eliminates two-way authority fragmentation between ADR-0037 and ADR-0038.
  - Structured 401/403/429 error responses align with ADR-0060 Standard 1, providing machine-readable errors for API clients.
  - Protocol contract for `JWKSManager` aligns with ADR-0077 Standard 1 and enables testability without real JWKS endpoints.
  - CORS policy correction addresses a current specification violation (wildcard origins with credentials).
  - Security headers provide defense-in-depth per OWASP recommendations.
  - Settings dissolution separates security configuration from the monolithic `ServerSettings`.

- **Tradeoffs accepted:**
  - Degraded-start for missing ISSUER_CONFIG (Standard 5) trades fail-fast strictness for operational flexibility. This is explicitly documented as a deliberate deviation from ADR-0045 P4.
  - Protocol contract for `JWKSManager` (Standard 2) adds a Protocol definition where a concrete class currently suffices. This is warranted by ADR-0077 Category A classification and testability requirements.
  - Security settings dissolution (Standard 6) is a target state — current implementation uses `ServerSettings`. Migration timeline follows ADR-0055's dissolution roadmap.

- **Risks introduced:**
  - CORS migration (Standard 7) requires coordination with frontend consumers to enumerate allowed origins. Incorrect enumeration could break legitimate cross-origin requests. Mitigation: enumerate origins incrementally; test in non-production first.
  - Security headers (Standard 8) could interfere with existing response handling if middleware ordering is incorrect. Mitigation: follow ADR-0063 Standard 4 middleware ordering strictly.
  - Rate limit error response migration (Standard 4) changes the response body shape for 429 responses. Existing API consumers that parse the current unstructured `{"message": "Rate limit exceeded"}` shape will need to adapt. Mitigation: this is a non-breaking change for consumers that only check status codes.

- **Mitigations:**
  - ADR-0062 (Testing) provides the test infrastructure for security dependency overrides and error response assertions.
  - ADR-0054 (Structured Logging) captures internal error details that are redacted from security error responses.
  - ADR-0063 (API Composition) governs the middleware ordering that security middleware must follow.

## Compliance

### Current State vs. Target State

| Area | Current State | Target State | Migration |
|------|---------------|--------------|-----------|
| JWT authentication | Implemented correctly as `Security()` dependency | No change needed | ✅ Compliant |
| Error responses (401/403) | Bare `HTTPException` with string detail | RFC 9457 structured schema (ADR-0060 S1) | Code migration needed |
| Error responses (429) | Unstructured `{"message": "..."}` | RFC 9457 structured schema | Code migration needed |
| `JWKSManager` Protocol | No Protocol contract | `JWKSManagerProtocol` defined | Code change needed |
| CORS policy | Production `allow_origins=["*"]` | Explicit origin enumeration | Code + config change needed |
| Security headers | Not set | Middleware sets OWASP-recommended headers | Code addition needed |
| Security settings | In `ServerSettings` | Dedicated `SecuritySettings` | ADR-0055 dissolution roadmap |
| Rate limit logging | No structured logging | Structured event logging | Code addition needed |
| Dev bypass validation | No production guard in settings | Settings-level validation | Code addition needed |

### Pre-Existing Non-Compliance

The codebase predates this ADR. All items in the "Migration" column above are pre-existing conditions, not violations introduced by this ADR. Migration is incremental — new security code adopts these standards immediately; legacy code migrates during its next substantive change or via the settings dissolution implementation plan.
