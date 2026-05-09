---
title: "API Security"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [api, security]
constrained_by: [layered-architecture.md, dependency-injection.md, configuration-ownership.md, type-boundaries.md, api-design-error-mapping.md, cross-channel-correlation.md, logging-observability.md, data-redaction-policy.md, application-lifecycle.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# API Security

## Context and Problem Statement

The application's HTTP surface is the boundary between external callers and internal feature services. Every inbound request arrives over the public internet (with the application's other features open as well, per the discussion in `transport-slack.md`); every authenticated request carries a principal whose identity must be verified, whose scopes must be checked, and whose abuse posture must be bounded. Without a single shared rule, each feature reinvents authentication semantics, authorization enforcement, rate-limiting backoff, and the response shapes for security failures.

The problem this record addresses: **what is the application's HTTP security posture — authentication mechanism, authorization model, rate-limiting strategy, CORS policy, security-response headers — and how do those concerns compose with the existing rules for HTTP error responses, correlation, and observability?** The answer determines:

1. How an inbound request is authenticated and what token format the application expects.
2. How a route declares the scopes it requires; how the framework enforces them; how the principal reaches handler code.
3. Whether per-IP and per-principal rate limiting are applied, where, and what response a throttled caller sees.
4. Which origins may make cross-origin requests; how CORS is configured for browser-side callers; how credentials interact with the policy.
5. Which response headers harden the application against common browser-side attacks; which are set by the application versus the network perimeter.
6. How security failures (401, 403, 429) flow into the existing problem-details body shape governed by the API error-mapping decision.

**Constraints:**

- HTTP error response bodies are RFC 9457 problem-details per `api-design-error-mapping.md`. Security failures (401, 403, 429) follow that shape; this record specifies the *what* and *when*, not the body schema.
- The correlation `request_id` is bound at the inbound adapter per `cross-channel-correlation.md`; security events are logged with that `request_id` per `logging-observability.md`.
- Sensitive values (tokens, signatures, session identifiers) are redacted at the structured-record egress per `data-redaction-policy.md`; security events log structurally — never with secrets in free-text messages.
- Configuration follows the per-domain `BaseSettings` pattern: vendor credentials and connectivity in the infrastructure layer per `configuration-ownership.md`. Identity-provider credentials (JWKS endpoint URLs, allowed issuers/audiences) live in security-domain settings.
- The application is one component of a layered defense: a network perimeter (load balancer, WAF) sits in front. This record specifies the application-layer controls; perimeter controls are an operations concern and are complementary, not a substitute.

**Non-goals:**

- This record does not define the canonical `User` value type, the per-transport identity-resolution rules, or the relationship between an authenticated principal and downstream domain models. Those are owned by `identity-resolution.md`.
- This record does not specify per-platform inbound verification (Slack signing-secret HMAC, Teams Bot Framework JWT). Those are owned by their respective transport records.
- This record does not pick the secrets-management mechanism (vault provider, rotation cadence). Secrets reach the application as environment variables per `cloud-portability.md`; storage and rotation are an operations concern.
- This record does not specify the network perimeter (WAF rules, DDoS protection, IP allow-lists, ALB configuration). Those are operations concerns.
- This record does not redefine static security analysis (Bandit) — that is owned by `code-quality-tooling.md` — nor dependency-vulnerability scanning.
- This record does not specify session management for browser-state (cookies, CSRF tokens). The application's HTTP surface is API-shaped (token-authenticated, stateless); session/CSRF concerns surface only if a future record adds a browser-cookie flow.

## Considered Options

**Option 1 — Token-based authentication (JWT bearer) with scope authorization, application-layer rate limiting, explicit CORS, OWASP-recommended security headers.** A canonical, widely-deployed posture for token-authenticated APIs. JWT bearer tokens validated against a JWKS endpoint (multi-issuer support), authorization by scope claim, rate limiting via SlowAPI integrated into FastAPI. CORS uses an explicit allow-list. Security headers follow OWASP recommendations.

**Option 2 — API keys with role-based authorization.** Static long-lived keys per consumer; per-key rate limiting; role assigned at key issuance. Simpler than JWT; weaker against compromise (no expiry; no fine-grained scopes); poor fit for delegated-identity scenarios.

**Option 3 — mTLS + service-account model.** Mutual TLS at the network layer for caller authentication; service accounts for principal identification. Operationally heavy; requires every caller to manage client certificates; appropriate for service-to-service traffic, not the application's intended surface.

**Option 4 — Bare endpoints (no application-layer authentication); rely on perimeter.** All security at the WAF/ALB layer. The application trusts every inbound request. Fragile (perimeter misconfiguration becomes a full bypass); rejected by defense-in-depth principles.

## Decision Outcome

**Chosen: Option 1 — JWT bearer authentication with scope authorization, application-layer rate limiting, explicit CORS, OWASP-recommended security headers.**

The application's HTTP surface authenticates inbound requests via signed JWTs, authorizes by scopes declared on each route, rate-limits at the application layer (complementing perimeter rate limiting), enforces an explicit CORS allow-list, and emits the OWASP-recommended security-response headers. Each piece composes with the existing records: authentication failures map to `401`, authorization failures map to `403`, rate-limit exceeded maps to `429`, all rendered as RFC 9457 problem-details per `api-design-error-mapping.md`, all logged with the bound `request_id` per `cross-channel-correlation.md` and `logging-observability.md`.

### Authentication: JWT bearer with multi-issuer JWKS

- **Token format.** RFC 7519 JSON Web Tokens, presented in the `Authorization: Bearer <token>` header per RFC 6750.
- **Signature verification.** RS256 (RSASSA-PKCS1-v1_5 with SHA-256) at minimum; ES256 (ECDSA P-256 with SHA-256) supported. Keys are fetched from each configured issuer's JWKS endpoint per RFC 7517; key material is cached with rotation per the SDK's standard cache (typical TTL: 1 hour).
- **Validated claims.** `iss` (issuer — must match a configured allowed issuer), `aud` (audience — must include the application's audience identifier), `exp` (not expired), `nbf` (if present, valid now), `iat` (sanity check). Tokens missing any required claim are rejected.
- **Multi-issuer support.** The application supports multiple identity providers concurrently. A `JWKSManager` infrastructure service (Path A: cloud-portable capability per `infrastructure-service-classification.md`) maintains one JWKS client per allowed issuer. Adding a new issuer is a configuration edit, not a code change.
- **Settings.** Allowed issuers and their audience identifiers are declared in security-domain settings (`SecuritySettings`) at `app/infrastructure/security/settings.py`. Each issuer entry carries its JWKS URL and the audiences it asserts.
- **Implementation seam.** Authentication is performed by a FastAPI `Security()` dependency (`get_current_user`) — a function injected via `Annotated[User, Security(get_current_user, scopes=[...])]`. The dependency is the only seam at which JWT validation runs; route handlers do not validate tokens themselves.

### Authorization: scope-based via FastAPI `SecurityScopes`

- **Scope claim.** The token's authorization is expressed as a list of scopes. Two scope-claim formats are accepted: RFC 6749 space-separated string (`"scope": "read:items write:items"`) and array form (`"scope": ["read:items", "write:items"]`); the validator recognizes both.
- **Per-route declaration.** Each authenticated route names its required scopes via FastAPI's `SecurityScopes`: `Annotated[User, Security(get_current_user, scopes=["read:incidents"])]`. The dependency checks that the token's scopes contain every requested scope; missing scopes produce `403`.
- **Permission boundary.** Scope checks are enforced at the route's dependency edge, not inside service code. A service receiving an authenticated `User` may assume the principal has the route's declared scopes; service-level role-based authorization for fine-grained permissions (e.g., "user owns this resource") is a service-level concern and is not in scope for this record.
- **Unauthenticated routes** (health checks, public webhooks) declare no `Security()` dependency. The set of unauthenticated routes is short and reviewed; the default for a feature route is "authenticated."

### Rate limiting: SlowAPI at the application layer

- **Library.** SlowAPI provides rate limiting for FastAPI/Starlette via a `Limiter` registered on `app.state` and per-route `@limiter.limit("…")` decorators or dependency-style injection.
- **Default key function.** `slowapi.util.get_remote_address` (per-IP). For authenticated routes, a custom key function is used to scope by principal identifier (extracted from the authenticated `User`), so a single principal cannot exceed its quota across IPs.
- **Limits.** Per-route limits are declared on each route; defaults are conservative and tightened for sensitive routes (write operations, identity-affecting endpoints). The limits are documented alongside the route declaration.
- **Storage backend.** In-memory by default for single-process deployments; a Redis-backed store (or equivalent) is configured when the application runs as multiple replicas. The backend choice follows the deployment topology and is set in `SecuritySettings`.
- **Layered with the perimeter.** The application-layer limit is **complementary** to perimeter limits (WAF, ALB). The perimeter blocks pathological volumes before they reach the application; the application enforces per-principal and per-feature limits the perimeter cannot see.
- **Error response.** A request that exceeds its limit raises `slowapi.errors.RateLimitExceeded`; an exception handler (registered once at app construction per `api-design-error-mapping.md`) translates it into a `429` problem-details body with `error_code = "rate_limited"` and `retry_after` populated from the limit's reset window. The `Retry-After` HTTP header is also set per RFC 9110.

### CORS policy

- **Explicit allow-list, no wildcard with credentials.** Cross-origin requests are governed by an explicit list of allowed origins declared in `SecuritySettings`. Production deployments enumerate the trusted origins (no `*`); non-production deployments may allow `localhost` development origins explicitly.
- **`allow_credentials=True` with wildcard origins is forbidden.** The CORS spec (and browser implementations) reject credentialed requests against wildcard origins; the application's policy refuses to construct a configuration that would silently break credentialed flows.
- **Allowed methods, headers, and exposed headers.** The policy declares the methods the application's API accepts (typically `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`), the request headers it accepts (`Authorization`, `Content-Type`, `X-Request-ID`, `traceparent`), and the response headers it exposes (`X-Request-ID`, `traceparent`, `Retry-After`). The configuration is centralized in `SecuritySettings` and applied via FastAPI's `CORSMiddleware`.

### Security-response headers

The application sets the following response headers on every HTTP response, via a single ASGI middleware registered once at app construction. The middleware runs after the route handler produces its response and before the response is serialized to the wire.

| Header | Value | Why |
| --- | --- | --- |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` | Browsers that have once seen the response over HTTPS continue to insist on HTTPS for the lifetime of the directive. |
| `X-Content-Type-Options` | `nosniff` | Disables MIME-type sniffing; browsers treat declared `Content-Type` as authoritative. |
| `X-Frame-Options` | `DENY` | Disallows the response from being framed; complementary to CSP `frame-ancestors`. |
| `Content-Security-Policy` | `default-src 'self'; form-action 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; upgrade-insecure-requests` | Restricts the document's loadable resources; primary defense against XSS for any HTML the API may render. |
| `Referrer-Policy` | `no-referrer` | Prevents the application's URLs from leaking via the `Referer` header on outbound navigation. |
| `Cache-Control` | `no-store` (for authenticated responses); per-route otherwise | Authenticated responses must not be stored by intermediate caches. Public, cacheable responses set their own `Cache-Control` per route. |
| `Permissions-Policy` | Disable browser features the application does not use | Defense in depth against features the application does not need. |

The middleware does not strip server-identifying headers (`Server`, `X-Powered-By`); those are typically removed at the network perimeter where it is more reliable than at the framework layer.

### Mapping security failures to problem-details responses

Per `api-design-error-mapping.md`, security failures produce RFC 9457 problem-details bodies. The mapping:

| Failure | HTTP status | `type` URI | Notes |
| --- | --- | --- | --- |
| Missing or malformed bearer token | `401` | `urn:problem:unauthorized` | `WWW-Authenticate: Bearer` header set per RFC 6750. |
| Token expired or signature invalid | `401` | `urn:problem:unauthorized` | Body's `error_code` distinguishes (`token_expired`, `signature_invalid`, etc.). |
| Authenticated but insufficient scopes | `403` | `urn:problem:forbidden` | `error_code = "insufficient_scope"`; the body names the missing scopes only when disclosing them is safe (the route's own declared scopes are not secret). |
| Rate limit exceeded | `429` | `urn:problem:rate-limited` | `Retry-After` header and `retry_after` body extension populated from the limit's reset window. |

Internal details (which key in the JWKS failed validation, which limit bucket overflowed, the principal's identifier) are **not** disclosed in the body. The `request_id` extension is always present so operators can correlate to logs.

### Development bypass token

- **Mechanism.** A non-production-only mechanism by which a static, well-known token bypasses JWT validation and grants a synthetic principal with all requested scopes. Useful for local development and for integration tests that exercise authenticated routes without a real identity provider.
- **Settings guard.** `dev_bypass_enabled` (boolean) defaults to `false`; it is only honoured in non-production environments. Production environments hard-fail at boot if the flag is set to `true`.
- **Application-level guard.** The dependency (`get_current_user`) refuses to honour the dev bypass token when the deployment is production, even if the setting is misconfigured. Two guards (settings-level and dependency-level) ensure the bypass cannot leak into production.
- **Audit logging.** Every use of the dev bypass token logs at `info` with `event="dev_bypass_used"` and the route path. The log record carries the `request_id` for correlation.

### Webhook authentication

Inbound webhooks (Slack events, Teams events, third-party integrations) do not present JWT bearer tokens; they authenticate via per-platform mechanisms documented in their respective transport records:

- **Slack** uses HMAC-SHA256 signing-secret verification (HTTP Events mode) or the pre-authenticated WebSocket (Socket Mode), per `transport-slack.md`.
- **Teams** uses Bot Framework JWT validation, per `transport-teams.md`.
- **Other webhook providers** authenticate per their own scheme; each new webhook integration's record specifies the verification mechanism.

This record establishes that webhook authentication is **per-platform**, not unified — the same heterogeneous-platforms principle that `multi-transport-architecture.md` applies to inbound dispatch applies to inbound authentication.

### Startup behaviour

The security subsystem deviates from the application's general fail-fast lifespan posture in one specific way: **a missing or empty `SecuritySettings.allowed_issuers` does not halt startup**. The application logs a `warning` (`event="security_subsystem_degraded"`) and starts. Authenticated routes return `401` at runtime when no issuer is configured (because no token can validate); unauthenticated routes (health checks, webhooks, Slack handlers) continue to work.

The rationale: many deployments need the application's non-authenticated surface (health checks, Slack workspace integration, webhooks from internal services) even when the public API is not configured for the deployment. A hard fail-fast on missing JWT configuration would block those deployments unnecessarily. The deviation is explicit and documented; it is the only deviation from fail-fast in the security subsystem.

### Composition with `OperationResult` and the central exception handler

- A handler that depends on `Security()` and the dependency raises (token invalid, scope insufficient, rate limit exceeded) — the exception propagates out of the handler. The host's central exception handler (registered per `api-design-error-mapping.md`) translates it into the corresponding problem-details response.
- A handler whose service returns `OperationResult.UNAUTHORIZED` for a domain-level authorization failure (e.g., "this user owns a different tenant's resource") — the handler renders via the per-platform helper, which produces a `403` problem-details body. The HTTP status comes from the `OperationStatus → HTTP` mapping; the body shape is the same as for security-dependency failures.

## Consequences

**Positive:**

- Authentication and authorization use a widely-deployed standard (JWT bearer + scopes); third-party identity providers, SDKs, and tooling all understand the model.
- Multi-issuer support means the application can honour tokens from multiple identity providers (an enterprise SSO, a CI service-account provider, a customer's own OIDC provider) without per-issuer feature work.
- Rate limiting is layered: the perimeter handles volumetric attacks; the application handles per-principal and per-feature quotas. Each layer does what it does best.
- CORS is explicit; misconfigurations (wildcard with credentials) cannot be silently created.
- Security headers are set by one middleware against the OWASP-recommended list; new routes inherit the protection automatically.
- Security failures use the same problem-details shape as every other error response. Consumers parse one error body schema; the `request_id` ties any failure to logs.
- The dev bypass mechanism is non-production-only with two guards. Local development and integration tests do not require a real identity provider.

**Tradeoffs accepted:**

- JWT validation is a per-request operation. The cost is bounded (signature check + claim validation against cached JWKS); performance impact is small.
- Multi-issuer support adds configuration surface (one issuer entry per allowed identity provider). The cost is a configuration line per issuer; the benefit is operational flexibility.
- Application-layer rate limiting is bypassable if the perimeter is misconfigured (a request that reaches the application bypassed the perimeter). Mitigation is the layered defense: each layer has a budget.
- The non-fail-fast posture for missing issuer configuration is a deliberate deviation from the lifespan rule. It is documented; the alternative (hard fail) was rejected because it would block deployments that legitimately use only the unauthenticated surface.

**Risks:**

- A new identity provider is added to the issuer list with mistaken audience or signature algorithm. Mitigation: a validation step at boot confirms each configured issuer's JWKS endpoint responds and the keys match the expected algorithm.
- An unauthenticated route is added by mistake (a developer forgets the `Security()` dependency on an authenticated feature). Mitigation: code review against a checklist; unauthenticated routes are reviewed at PR time (see Confirmation).
- The dev bypass leaks into production through misconfiguration. Mitigation: two guards (settings-level guard and dependency-level guard); production rejects bypass usage even if the setting is somehow set.
- A wildcard CORS origin is configured by mistake with credentials. Mitigation: a settings validator rejects the combination at boot.
- A high-volume legitimate caller hits the rate limit and is blocked. Mitigation: per-principal limits are tunable per route; integration tests for high-volume callers exercise the actual limit; the perimeter's rate limit is sized to be looser than the application's.

## Confirmation

Compliance is verified by:

- **Repository structure.** `app/infrastructure/security/` contains the `JWKSManager`, the `get_current_user` dependency, the `SecuritySettings` declaration, the rate limiter setup, the CORS configuration, and the security-headers middleware. There is one configuration site per concern.
- **Settings.** `SecuritySettings` declares `allowed_issuers` (list of issuer entries with `iss`, `audience`, `jwks_url`), `cors_allowed_origins` (list of explicit origins), `rate_limit_storage_backend` (literal: `memory` or `redis`), `dev_bypass_enabled` (bool, false in production by validator). The settings validator rejects `cors_allowed_origins=["*"]` when `cors_allow_credentials=True`.
- **Code review.** A PR adding a new route is reviewed against (1) whether the route declares `Security(get_current_user, scopes=[...])` (steady-state default for feature routes), (2) what scopes it declares, (3) what rate limit applies, (4) whether the route is unauthenticated by design (a reviewer's explicit check). PRs that add unauthenticated routes carry a justification in the PR description.
- **CI.** A boot test asserts the security subsystem starts cleanly with valid issuer configuration and degraded-starts (with the documented warning) when issuer configuration is missing. A unit test asserts that a token from an unconfigured issuer is rejected with `401` and the expected `error_code`. A unit test asserts that a request exceeding a route's rate limit produces a `429` problem-details body with `Retry-After` set. An integration test asserts that an authenticated route responds to a dev bypass token in a non-production configuration and rejects it in production.
- **Static analysis.** Bandit (per `code-quality-tooling.md`) catches common security anti-patterns; the import contract (per `import-governance.md`) catches feature code reaching into `app/clients/` outside the adapter boundary. Neither is a substitute for code review on the security subsystem.
- **Periodic audit.** The list of allowed issuers, the CORS allow-list, and the rate-limit table are reviewed quarterly (or on every release if the cadence demands it). Stale entries are removed.

## Source References

1. RFC 6749 — The OAuth 2.0 Authorization Framework
   - URL: <https://www.rfc-editor.org/rfc/rfc6749.html>
   - Accessed: 2026-05-08
   - Relevance: Defines the OAuth 2.0 framework, including the access-token concept and the space-separated scope-string format. Grounds the scope claim acceptance and the scope-based authorization model.

2. RFC 6750 — The OAuth 2.0 Authorization Framework: Bearer Token Usage
   - URL: <https://www.rfc-editor.org/rfc/rfc6750.html>
   - Accessed: 2026-05-08
   - Relevance: Defines the `Authorization: Bearer <token>` header format and the `WWW-Authenticate: Bearer` challenge response. Grounds the token-presentation rule and the `WWW-Authenticate` header on `401` responses.

3. RFC 7519 — JSON Web Token (JWT)
   - URL: <https://www.rfc-editor.org/rfc/rfc7519.html>
   - Accessed: 2026-05-08
   - Relevance: Defines the JWT structure (header, payload, signature), the standard registered claims (`iss`, `aud`, `exp`, `nbf`, `iat`, `jti`, `sub`), and the validation rules. Grounds the validated-claim list and the rejection criteria.

4. RFC 7517 — JSON Web Key (JWK)
   - URL: <https://www.rfc-editor.org/rfc/rfc7517.html>
   - Accessed: 2026-05-08
   - Relevance: Defines the JWK format and the JWKS (JWK Set) endpoint convention. Grounds the multi-issuer JWKS-fetch pattern: each allowed issuer hosts a JWKS endpoint; the application fetches and caches keys per issuer.

5. OWASP Secure Headers Project
   - URL: <https://owasp.org/www-project-secure-headers/>
   - Accessed: 2026-05-08
   - Relevance: Documents the canonical list of security response headers (`Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`, `Cache-Control`, `Permissions-Policy`) and recommended values. Grounds the security-headers table and the rule that headers stripping server identification are deferred to the network perimeter.

6. OWASP API Security Top 10 — 2023
   - URL: <https://owasp.org/API-Security/editions/2023/en/0x11-t10/>
   - Accessed: 2026-05-08
   - Relevance: Names the highest-impact API security risks (Broken Object Level Authorization, Broken Authentication, Broken Object Property Level Authorization, Unrestricted Resource Consumption, Broken Function Level Authorization, etc.). Grounds the prioritization: authentication, authorization, and rate-limiting are first-tier concerns; this record addresses each.

7. SlowAPI — Documentation
   - URL: <https://slowapi.readthedocs.io/>
   - Accessed: 2026-05-08
   - Relevance: Documents SlowAPI as the rate-limiting library for Starlette and FastAPI: the `Limiter(key_func=…)` setup, registration on `app.state`, the `@limiter.limit("…")` decorator, and the `RateLimitExceeded` exception handled by a registered handler. Grounds the rate-limiter selection and the exception-to-`429` mapping.

8. RFC 9457 — Problem Details for HTTP APIs
   - URL: <https://www.rfc-editor.org/rfc/rfc9457.html>
   - Accessed: 2026-05-08
   - Relevance: Defines the `application/problem+json` body shape used for all error responses. Cited here to ground the rule that 401, 403, and 429 responses follow the application-wide problem-details mapping established by `api-design-error-mapping.md`.

## Change Log

- 2026-05-08: Created. Selects JWT bearer authentication with multi-issuer JWKS validation (RS256/ES256, with `iss` / `aud` / `exp` / `nbf` / `iat` validated against `SecuritySettings.allowed_issuers`); FastAPI `Security()` dependency (`get_current_user`) as the single validation seam with scope authorization via `SecurityScopes` (accepting both RFC 6749 space-separated and array scope-claim formats); SlowAPI for application-layer rate limiting (per-IP default, per-principal for authenticated routes, in-memory or Redis-backed storage), with `RateLimitExceeded` translated to `429` problem-details per `api-design-error-mapping.md`; explicit-origin CORS allow-list (no wildcard with credentials, validated at boot); OWASP-recommended response headers (`Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`, `Cache-Control`, `Permissions-Policy`) set by a single ASGI middleware. Establishes the `401` / `403` / `429` mapping to problem-details with `urn:problem:unauthorized` / `urn:problem:forbidden` / `urn:problem:rate-limited` `type` URIs. Pins the dev-bypass-token mechanism with two guards (settings-level and dependency-level) and audit logging on every use. Names the deliberate non-fail-fast deviation for missing issuer configuration: the security subsystem degrades to "unauthenticated routes work; authenticated routes return 401" rather than blocking startup. Webhook authentication is delegated to per-platform records; secrets storage and rotation are operations concerns; canonical `User` value type and per-transport identity propagation are owned by `identity-resolution.md`.
