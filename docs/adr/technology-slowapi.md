---
title: "Technology Selection: SlowAPI"
status: Accepted
type: Selection
tier: Tier-2
governance_domain: [application]
concerns: [security, api]
constrained_by: [api-security.md, layered-architecture.md, package-management.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Technology Selection: SlowAPI

## Context and Problem Statement

The API security standard ([api-security.md](api-security.md)) requires application-layer rate limiting on inbound HTTP routes — a per-IP default for unauthenticated traffic, per-principal limits for authenticated routes, and a substitutable storage backend (in-memory for single-process deployments, Redis-backed for multi-task fleets). Limit breaches are translated to RFC 9457 problem-details with `urn:problem:rate-limited` and HTTP `429 Too Many Requests`. The standard does not pick the library that implements the limiter; it leaves the seam at the FastAPI middleware/dependency boundary.

The problem this record addresses: **which Python library does the application use as its application-layer rate limiter, and on what grounds?** The selection criteria are:

1. **Native FastAPI integration** — the limiter must compose as either FastAPI middleware or as a `Depends()`-injected dependency, with access to the resolved request and the authenticated principal.
2. **Pluggable storage backend** — the standard requires an in-memory backend (default, single-process) and a Redis backend (multi-task production); the library must support both without re-implementation.
3. **Per-key flexible limits** — the limiter must permit different keys per route (per-IP for `/login`, per-principal for `/api/v1/*`, per-path for narrow endpoints) without ceremony.
4. **Documented exception path** — limit breaches must be observable as a typed exception (or a typed handler hook) so the application can translate them to problem-details.
5. **Stewardship and maturity** — maintained, packaged on PyPI, used at scale.
6. **Tier-2 economics** — per [package-management.md](package-management.md), a small, focused library beats a hand-rolled component.

**Constraints:**

- Limit policy lives with the API security standard. This record does not redefine *what* the limits are; it only picks the library that enforces them.
- The application runs `desired_count >= 2` ([cloud-portability.md](cloud-portability.md)). A naive in-memory limiter would let a client circumvent limits by hitting different tasks. The library's storage backend must support a shared store (Redis) for production.
- The library's exception type must compose with the application's problem-details mapper ([api-design-error-mapping.md](api-design-error-mapping.md)). A limiter whose only output is a fixed Starlette `JSONResponse` is unfit; the application owns the response shape.

**Non-goals:**

- This record does not redefine any rule from the API security standard. Where the library and the standard appear to disagree, the standard wins; the wiring code reconciles.
- This record does not pick the *infrastructure* rate limiter (CDN, WAF, API Gateway). Those operate at a different layer and are governed by deployment configuration, not application code.
- This record does not pin a specific minor version. The rule is "current stable on PyPI"; minor-version pinning is a `pyproject.toml` concern.

## Considered Options

**Option 1 — SlowAPI.** A FastAPI/Starlette-native rate-limiting library, conceptually a port of Flask-Limiter to the ASGI ecosystem. Provides a `Limiter` object, decorator-based per-route limits (`@limiter.limit("5/minute")`), a `key_func` for limit-key derivation (per-IP, per-principal, custom), pluggable storage (in-memory, Redis, Memcached, MongoDB), a `RateLimitExceeded` exception that the application can catch and translate, and a documented Starlette/FastAPI middleware-installation path.

**Option 2 — fastapi-limiter.** A FastAPI-native rate limiter that requires Redis as its storage backend. No in-memory mode. Async-first.

**Option 3 — starlette-limiter** (or similar Starlette-native middleware). Lower-level Starlette middleware with per-route limit configuration; smaller community than SlowAPI.

**Option 4 — Hand-rolled middleware over Redis.** Custom ASGI middleware that increments a Redis counter per (key, window) and rejects on overflow. No external dependency.

## Decision Outcome

**Chosen: Option 1 — SlowAPI.**

SlowAPI satisfies every selection criterion. It composes natively with FastAPI as a `Depends()`-friendly limiter object plus a Starlette middleware installation; the per-route decorator pattern fits FastAPI's idiom; the `key_func` mechanism makes per-IP and per-principal keying straightforward without a custom adapter; the `RateLimitExceeded` exception is the documented hook through which the application translates limit breaches into problem-details rather than accepting the library's default response. Storage backends include in-memory (default) and Redis (production), satisfying the dual-environment constraint without re-implementation. The library's stewardship and adoption (used in numerous FastAPI applications, included in major FastAPI-template projects) make it the de facto choice in this ecosystem. fastapi-limiter (Option 2) is async-first and cleanly written but mandates Redis even in development, which complicates local runs. starlette-limiter (Option 3) is lower-level and has a smaller community. Hand-rolling (Option 4) re-implements key derivation, sliding-window/leaky-bucket semantics, storage abstraction, and exception shape — all subtle, all available off-the-shelf.

### What the application uses

The limiter is constructed once in the application's security wiring module, registered with FastAPI as middleware, and applied to routes via decorator and (where uniform) via dependency injection:

```python
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,                # default key
    storage_uri=settings.rate_limit_storage_uri, # "memory://" or "redis://..."
    headers_enabled=True,                       # emit RateLimit-* response headers
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limited_handler)
```

Per-route limits use the decorator with the route's documented limit; routes that limit per authenticated principal pass a custom `key_func`:

```python
@router.post("/items")
@limiter.limit("60/minute", key_func=lambda r: r.state.user.user_id)
async def create_item(...): ...
```

The application **does not** rely on:

- **SlowAPI's default 429 response.** The application's exception handler translates `RateLimitExceeded` into RFC 9457 problem-details with `urn:problem:rate-limited`, `Retry-After`, and the standard correlation context per [api-design-error-mapping.md](api-design-error-mapping.md). The library's default JSON shape is not exposed to clients.
- **SlowAPI's auto-discovery of the principal.** Per-principal keying uses the application's authenticated `User.user_id` ([identity-resolution.md](identity-resolution.md)), bound to `request.state.user` upstream by the security dependency. The library is given a `key_func` that reads from there.

### Storage backend selection

The limiter's `storage_uri` is a settings-driven scalar:

- `memory://` for local development and tests. Fast, zero-dependency, scoped to one process.
- `redis://...` for production. Required because `desired_count >= 2`; without a shared store, a client can multiplex requests across tasks to defeat the limit.

The application reads the URI from a settings class owned by the security boundary ([configuration-ownership.md](configuration-ownership.md)). Settings validation rejects any value other than these two scheme prefixes; downstream backends supported by SlowAPI (Memcached, MongoDB) are not enabled without a deliberate standard amendment.

### Exception translation

The single hook that bridges SlowAPI to the application's error model is the exception handler:

```python
@app.exception_handler(RateLimitExceeded)
async def _rate_limited_handler(request, exc):
    return await operation_result_to_response(
        OperationResult.transient_error(
            error_code="rate_limited",
            message=str(exc.detail),
            retry_after=exc.retry_after_seconds,
        ),
        request=request,
    )
```

This composes the library's exception with the application's central problem-details translator ([api-design-error-mapping.md](api-design-error-mapping.md)): the response body is RFC 9457-shaped, the correlation context is present, and the `Retry-After` header is set from the exception's documented attribute. SlowAPI's own response is never seen by clients.

### Library version pinning

`pyproject.toml` requires `slowapi >= 0.1.9` (the stable line that supports modern Starlette/FastAPI versions and the in-memory + Redis storage backends used by this application). Minor-version upgrades are managed through the dependency-bump workflow ([package-management.md](package-management.md)); breaking-change releases are reviewed.

### Substitution path

If a future need requires a different limiter (e.g., a token-bucket library with sliding-window precision, a higher-throughput Redis adapter), the substitution is bounded to:

1. Replace the SlowAPI imports in the security wiring module with the new library's primitives.
2. Replace the per-route decorator (or move limits to declarative middleware configuration with the new library's vocabulary).
3. Re-target the exception handler at the new library's exception type; the central problem-details translator is unchanged.
4. Confirm the storage-URI configuration shape is compatible (or migrate it).

Routes' per-route limit *values* (`"60/minute"`) are part of the security standard's policy surface; they are reviewed when changed regardless of which library enforces them.

### Pros and cons of the options

**SlowAPI.** Good: native FastAPI composition; pluggable storage including in-memory; documented `RateLimitExceeded`; per-`key_func` flexibility. Bad: depends on the older `limits` library internally (an artifact of the Flask-Limiter heritage; not user-visible).

**fastapi-limiter.** Good: async-first; clean. Bad: Redis-only — local dev and tests would need a Redis container or a stub.

**starlette-limiter.** Good: lower-level, fewer indirections. Bad: smaller community; less adoption; less precedent for FastAPI integration.

**Hand-rolled.** Good: zero dependency. Bad: re-implements all the subtle pieces; correctness regressions are hard to detect; key-function flexibility, sliding-window math, and storage abstraction must all be built and maintained.

## Consequences

**Positive:**

- Per-route limits are a one-line decorator. Adding rate limiting to a new route is trivial; reviewing limit values is concentrated at the route definition.
- The application's response shape on limit breach is the same RFC 9457 shape as every other error; clients do not see two error formats.
- Storage substitution (in-memory ↔ Redis) is a settings change, not a code change.
- The library's adoption in the FastAPI ecosystem means fixes and CVE updates flow through normal dependency-bump cadence.

**Tradeoffs accepted:**

- One additional runtime dependency (and its transitive `limits` library). Acceptable: the alternative is hand-rolled code with the same surface area.
- The decorator pattern means limit values are spread across route modules rather than centralized. Acceptable: limits are a property of the route, and reviewing them at the route's definition is the right locality.
- SlowAPI's default response is bypassed by an exception handler the application installs explicitly. Acceptable: the application owns the wire shape; the library is the enforcement mechanism, not the response builder.

**Risks and mitigations:**

- **A future SlowAPI release changes `RateLimitExceeded`'s attribute names or removes `retry_after_seconds`.** *Mitigation:* the exception handler is the only consumer; a contract test asserts the attributes the handler reads remain present; a breaking-change release is reviewed before bump.
- **The Redis backend has an outage; rate limiting falls back to in-memory and limits are no longer shared across tasks.** *Mitigation:* the Redis storage adapter has a documented failure mode (raises on connection error); the security wiring decides whether to fail closed (return 503) or fail open (allow without limits, alarm on the failure). The default posture is fail-closed; the standard names this as a configuration-time decision.
- **A custom `key_func` raises.** SlowAPI does not catch `key_func` exceptions; the request returns 500 instead of being rate-limited. *Mitigation:* `key_func`s are pure-by-construction (`get_remote_address`; or `lambda r: r.state.user.user_id` after the security dependency has run); review enforces.

## Confirmation

Compliance is verified by:

- **Code review.** `import slowapi` appears in the security wiring module. Routes that require rate limiting carry the `@limiter.limit(...)` decorator. The exception handler for `RateLimitExceeded` is registered exactly once at app construction.
- **Static analysis.** A check confirms no route returns SlowAPI's default 429 response (i.e., no path bypasses the exception handler).
- **Tests.** A test asserts that exceeding the documented limit on a sample route produces an RFC 9457 problem-details body with `type` ending in `rate-limited`, the correlation ID present, and the `Retry-After` header set. A test asserts the in-memory backend works in single-process tests; a test asserts the Redis URI is rejected when the backend is not reachable (fail-closed posture).
- **Dependency declaration.** `pyproject.toml` declares `slowapi >= 0.1.9` under the application's runtime dependencies; the storage URI is sourced from settings, not hard-coded.

## Source References

1. SlowAPI — Project Repository
   - URL: <https://github.com/laurentS/slowapi>
   - Accessed: 2026-05-08
   - Relevance: Establishes SlowAPI's stewardship, FastAPI/Starlette integration model, decorator-based limit declaration, `key_func` mechanism, and pluggable storage. Grounds every binding the application makes against the library.

2. SlowAPI — Documentation
   - URL: <https://slowapi.readthedocs.io/en/latest/>
   - Accessed: 2026-05-08
   - Relevance: Documents `Limiter`, `SlowAPIMiddleware`, `RateLimitExceeded`, `headers_enabled` (RFC 6585 `RateLimit-*` response headers), `storage_uri` formats (`memory://`, `redis://`, etc.), and the exception-handler pattern. Grounds the application's wiring code and the storage-URI policy.

3. RFC 6585 — Additional HTTP Status Codes (§4 "429 Too Many Requests")
   - URL: <https://www.rfc-editor.org/rfc/rfc6585#section-4>
   - Accessed: 2026-05-08
   - Relevance: Defines the HTTP `429 Too Many Requests` status and the `Retry-After` header semantics. Grounds the response shape the application emits when SlowAPI raises `RateLimitExceeded`.

4. RFC 9457 — Problem Details for HTTP APIs
   - URL: <https://www.rfc-editor.org/rfc/rfc9457>
   - Accessed: 2026-05-08
   - Relevance: Defines the `application/problem+json` body shape the application uses for all error responses, including rate-limit breaches. Grounds the rule that SlowAPI's default response is replaced by the application's central problem-details translator.

5. fastapi-limiter — Project Repository
   - URL: <https://github.com/long2ice/fastapi-limiter>
   - Accessed: 2026-05-08
   - Relevance: Documents fastapi-limiter as a Redis-only alternative. Grounds the comparison and the rejection on storage-flexibility criterion.

6. OWASP API Security Top 10 (2023) — API4:2023 Unrestricted Resource Consumption
   - URL: <https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/>
   - Accessed: 2026-05-08
   - Relevance: Establishes rate limiting as a primary control against resource-exhaustion attacks. Grounds the necessity of an application-layer limiter even when an upstream WAF or CDN is present.

## Change Log

- 2026-05-08: Created. Selects SlowAPI (`>= 0.1.9`) as the application-layer rate-limiting library composing with FastAPI. Documents the wiring shape (decorator + middleware + exception handler), the storage-URI policy (`memory://` for local, `redis://` for production), the exception-translation hook that routes `RateLimitExceeded` through the central RFC 9457 problem-details mapper, and the substitution path bounded to the security wiring module.
