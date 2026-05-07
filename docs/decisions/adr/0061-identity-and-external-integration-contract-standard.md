---
adr_id: ADR-0061
title: "Identity and External Integration Contract Standard"
status: Accepted
decision_type: Domain Standard
tier: Tier-3
primary_domain: Dependency and Composition
secondary_domains:
 - Security
 - Transport and API
 - Observability and Operations
owners:
 - SRE Team
date_created: 2026-04-29
last_updated: 2026-05-05
last_reviewed: 2026-05-05
next_review_due: 2026-09-01
constrained_by:
 - ADR-0044
 - ADR-0045
 - ADR-0048
 - ADR-0050
 - ADR-0052
 - ADR-0054
 - ADR-0055
 - ADR-0056
 - ADR-0065
 - ADR-0076
 - ADR-0077
impacts:
 - ADR-0062
 - ADR-0064
supersedes:
 - ADR-0023
 - ADR-0024
superseded_by: []
review_state: current
related_records:
 - ADR-0046
 - ADR-0059
 - ADR-0060
 - ADR-0078
related_packages:
 - app/infrastructure/security
 - app/infrastructure/clients
 - app/infrastructure/services
---

# Identity and External Integration Contract Standard

## Context

- Problem statement: The SRE Bot processes requests from multiple authenticated interaction surfaces within the same process: HTTP API (JWT bearer token), Slack commands and interactions (Socket Mode WebSocket or HTTP Events API), inbound webhooks (HMAC-signed payload), and background jobs (no external signal). Business logic — access control decisions, audit trail entries, notification routing — must operate against a single normalized principal type (`User`) regardless of which surface originated the request.

   Each surface carries a structurally incompatible authentication signal: a JWT bearer token in an HTTP `Authorization` header; a Slack `user_id` arriving either over an authenticated Socket Mode tunnel (connection-level trust, not per-message signing) or via HTTP Events API request signature verification; an actor claim extracted from a webhook HMAC signature; or no external signal at all. These are not fallback tiers of a single resolution chain — they are distinct trust contexts that never co-occur in the same request. A unified multi-source orchestrator would incorrectly imply these contexts compose or can be prioritized, and would couple unrelated authentication mechanisms behind a shared interface with no coherent substitution value.

  Two legacy ADRs (ADR-0023, ADR-0024) had partially addressed this domain but predated the current governance model (ADR-0044), the service contract standard (ADR-0077), and the provider composition standard (ADR-0056). Their overlapping guidance needed consolidation under the correct transport-ownership framing.

- Business/operational drivers:
- Ensure all interaction surfaces produce the canonical `User` type — the single internal identity representation for business logic, audit logging, and notification routing.
- Define identity credential lifecycle alignment with ADR-0052 (release-phase binding) — identity provider credentials (Google service account keys, Slack tokens, JWT signing keys) must be bound at release phase, not fetched at runtime.
- Codify the transport-ownership identity resolution model — each transport layer owns its own identity resolution; there is no unified multi-source orchestrator because interaction surfaces are never co-occurring and carry incompatible trust signals.
- Classify external integration clients per ADR-0077 to establish which need Protocol contracts and which are Category C implementation details.
- Constraints:
- ADR-0050 Standard 1 (integration boundary mandate): All external identity lookups (Slack API, JWKS endpoint) must return `OperationResult`. Internal claim extraction from a pre-validated JWT payload is a pure transform and does not require `OperationResult` wrapping.
- ADR-0052 (build-release-run): Identity provider credentials are release-phase configuration, not runtime-fetched secrets.
- ADR-0054 (structured logging): Identity resolution events must emit structured logs with correlation context. No credentials, tokens, or PII in log payloads.
- ADR-0077 Standard 1 (service classification): `JWKSManager` is the sole Category A service in this domain; external integration clients are Category C (implementation details). JWT claim extraction is a private helper, not a service.
- Non-goals:
- This record does not define JWT validation algorithms or JWKS rotation mechanics. Those are security implementation details.
- This record does not define platform-specific user resolution logic (Slack user lookup, Teams identity mapping). The generic contract that all platform providers must satisfy when resolving an interaction payload to a canonical `User` is governed by ADR-0084 (Draft). Per-platform field mappings and trust-basis details are Category C, documented in each platform's Tier-4 Integration Decision (e.g., ADR-0067 S8 for Slack).
- This record does not govern the access control model (roles, permissions, scopes). That is a separate domain.

## Decision

- Chosen approach: Consolidate ADR-0023 and ADR-0024 into a Tier-3 Domain Standard that defines domain-specific rules for identity resolution and external integration contracts, referencing upstream standards for all cross-cutting concerns.
- Why this approach: ADR-0023's canonical User model and transport-ownership model are domain-specific rules that belong at Tier-3. ADR-0024's client facade, provider, and DI patterns are now fully codified in upstream Tier-2 standards (ADR-0050, ADR-0055, ADR-0056, ADR-0077). Consolidation eliminates redundancy and ensures identity-specific rules are governed at the correct tier.

### Standard 1: Canonical Identity Model

The identity domain defines a canonical `User` model in `infrastructure/security/models.py` that normalizes platform-specific user representations into a single internal type:

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str` | Canonical unique identifier — the user's primary email address. All downstream services use this as the identity key. |
| `email` | `str` | User's email address (same as `user_id` in current implementation; preserved for explicit semantics). |
| `display_name` | `str` | Human-readable display name. |
| `source` | `AuthPrincipalSource` enum | Authentication transport that produced this principal: `API_JWT`, `SLACK`, `WEBHOOK`, `SYSTEM`. |
| `platform_id` | `str \| None` | Platform-specific user identifier (Slack user ID, JWT `sub` claim, etc.). Available for logging and debugging; must not be used for business logic decisions (ADR-0050 Standard 5 — provider agnosticism). |
| `permissions` | `list[str]` | Resolved permissions/scopes for the current session. Source depends on the identity provider (JWT scopes, platform-resolved roles). |
| `metadata` | `dict[str, Any]` | Source-specific metadata (Slack team ID, JWT claims, etc.). Available for logging only; must not drive business logic. |

The `User` model is a Pydantic `BaseModel` because it crosses the HTTP I/O boundary (returned by `get_current_user` dependency, serialized in audit logs). This is correct per ADR-0065 P4 type boundary rules.

Feature code depends on the base `User` type only. No platform-specific subclasses cross the feature boundary.

### Standard 2: Identity Resolution Ownership by Transport Layer

> **Amendment 2026-05-05:** The original multi-source priority model (JWT > Platform > Webhook > System) was incorrect. These are distinct transport contexts that never co-occur in the same request; a unified priority-ordering model implies a composite that does not exist. Replaced with a transport-ownership model grounded in the architectural conversation that surfaced this gap during Protocol contract implementation.

Each request context has exactly one identity source, determined by the transport layer that received the request. **Transport layers own their identity resolution; there is no unified multi-source orchestrator.** `IdentityService` is scoped to HTTP-authenticated requests only.

**Transport-to-resolution mapping:**

| Transport | Identity Source | Resolution Mechanism | Owner |
|-----------|----------------|---------------------|-------|
| HTTP (JWT-authenticated endpoints) | Verified JWT payload | `_build_user_from_jwt_payload(payload)` — private helper in `infrastructure/security/current_user.py`; no DI needed | `infrastructure/security/current_user.py` |
| Slack command/interaction | Slack `user_id` from Bolt event payload (trust basis depends on mode: Socket Mode uses authenticated WebSocket connection via `SLACK_APP_TOKEN`; HTTP mode uses request-signature verification via `SLACK_SIGNING_SECRET`) | `SlackPlatformProvider` resolves via Slack `users.info` API | Platform layer (Category C per ADR-0078, ADR-0067 Standard 8) |
| Inbound webhooks | Webhook actor claim from signed payload | Inline extraction in webhook middleware — returns minimal `User(source=WEBHOOK)` | Webhook middleware layer |
| Background/system jobs | No external signal | Inline constant: `User(source=SYSTEM, ...)` | Inline at each call site |

**Rules:**

1. A request context carries exactly one identity source. Fallthrough between sources is not permitted.
2. JWT claim extraction (`_build_user_from_jwt_payload`) must not accept platform-specific identifiers (Slack user IDs, Teams user principals) as input. Its single concern is: given a verified JWT payload, produce a canonical `User`.
3. Platform transport layers (Slack, Teams) resolve their own user identity using the platform provider (ADR-0078 Category C). The result must be a canonical `User` with the platform `source` enum value (`AuthPrincipalSource.SLACK`, etc.).
4. Webhook and system identity are not routed through any shared service. They are inline operations at their respective transport layers.
5. **Resolution failure semantics**: Each transport layer handles its own failure semantics. For JWT resolution: if `_build_user_from_jwt_payload` receives a malformed payload (missing `sub`/`email`), raise an exception caught by `get_current_user`, which maps to HTTP 401. Log the failure with structured context (source, error, correlation_id) per ADR-0054. No credentials or tokens in log payloads.

### Standard 3: JWT Claim Extraction

JWT claim extraction is a **private, pure helper function** in `infrastructure/security/current_user.py` — not a DI-injected service, not a Protocol, not a provider:

```python
def _build_user_from_jwt_payload(payload: dict) -> User:
    """Extract canonical User from a verified JWT payload. Pure function, no I/O."""
    return User(
        user_id=payload.get("sub", "unknown"),
        email=payload.get("email", "unknown"),
        display_name=payload.get("name", payload.get("sub", "unknown")),
        source=AuthPrincipalSource.API_JWT,
        platform_id=payload.get("sub", "unknown"),
        permissions=payload.get("permissions", []),
        metadata={"jwt_iss": payload.get("iss", "")},
    )
```

**Rationale:** This function performs 6 dict lookups and one constructor call. Zero external I/O. Zero branching based on external state. It is called in exactly one place — `get_current_user()` in `infrastructure/security/current_user.py`. No feature package has ever consumed it directly. Wrapping it in a Protocol-backed DI service would introduce ceremony with no substitution value — it meets neither ADR-0077 Category A criterion (no backing service, no feature-package consumer).

**`JWKSManager` is the only Category A service in this domain** — it wraps the JWKS endpoint (Google IDP via Backstage), performs real I/O (JWKS fetch and key material rotation), and is correctly injected into `get_current_user` via `Depends(get_jwks_manager)`.

**Domain boundary:**

- HTTP caller identity (JWT) — determined by `_build_user_from_jwt_payload` inside `get_current_user`
- Platform transport identity (Slack, Teams) — governed by the respective platform provider (ADR-0078 Category C, ADR-0067 Standard 8)
- IDP (source of truth for groups/users) — governed by `DirectoryProvider` Protocol (Category A, complete)
- Access sync (IDP → third-party targets) — governed by the access package

### Standard 4: External Integration Client Classification

External integration clients are classified per ADR-0077 Standard 1:

| Service | Category | Protocol Required | Delegation Tier | Rationale |
|---------|----------|-------------------|-----------------|-----------|
| `IdentityService` | **A** (Contract Required) | Yes — P1 priority | Tier 1 (JWKS endpoint / IDP — currently Google Workspace via Backstage) | Feature-facing; abstracts HTTP caller identity resolution from JWT payload; IDP provider may change. |
| `SlackPlatformProvider` (user lookup) | **C** (Implementation Detail) | No — Category C per ADR-0078 | Tier 1 (Slack Web API) | Slack user ID → canonical `User` resolution. Owned by platform layer, not `IdentityService`. Governed by ADR-0067 Standard 6. |
| `IdentityResolver` | **C** (Implementation Detail) | No | N/A | Internal to `JWTIdentityService`; not consumed directly by features. |
| Slack Client (slack_sdk) | **C** (Implementation Detail) | No | N/A | Platform-specific SDK wrapper; consumed by `SlackService` (ADR-0078 Category C). |
| Google Workspace Clients | **C** (Implementation Detail) | No | N/A | Provider-specific API facades; consumed via `DirectoryProvider` Protocol (Category A, complete). |
| AWS Clients (identity store, organizations, SSO) | **C** (Implementation Detail) | No | N/A | Provider-specific API facades; consumed by access sync adapters. Domain-specific operations documented as Category C exceptions per ADR-0077 Standard 3. |
| GitHub Client | **C** (Implementation Detail) | No | N/A | Provider-specific API facade. |
| GC Notify Client | **C** (Implementation Detail) | No | N/A | `NotificationService` wraps this; `NotificationService` is Category A P2 (ADR-0077). |

**Rule**: Feature packages must consume Category A services (e.g., `DirectoryProvider`, `StorageService`) via the injection boundary (ADR-0048 Boundary 2). Direct import of Category C clients from feature code is prohibited unless documented as a Category C exception (ADR-0077 Standard 3).

### Standard 5: Credential Lifecycle Binding

Identity provider credentials follow ADR-0052 (build-release-run):

1. **Release-phase binding**: All credentials (Slack tokens, Google service account key paths, JWT signing keys, JWKS endpoint URLs) are environment variables or mounted files bound at the ECS task definition level. They must not be fetched from SSM, Secrets Manager, or other runtime sources during application startup (ADR-0068 migration target).
2. **Credential rotation**: JWKS endpoints are the exception — they are runtime-refreshed because key rotation is an inherent part of the OIDC protocol. The `JWKSManager` (current implementation) correctly caches and refreshes JWKS keys at runtime. This is not a violation of ADR-0052 because the JWKS endpoint URL is release-phase bound; only the key material is runtime-refreshed.
3. **Credential safety**: No credentials, tokens, or key material in structured log payloads (ADR-0054). No credentials in error responses (ADR-0060 Standard 3). Credentials must not appear in `OperationResult.message` or `error_code` fields.

## Alternatives Considered

1. Maintain separate ADR-0023 and ADR-0024:
   - Pros: Existing records cover identity and integration separately.
   - Cons: ADR-0024's patterns (facade, provider, DI alias, OperationResult) are now fully codified in ADR-0050, ADR-0055, ADR-0056, ADR-0077. Keeping ADR-0024 creates duplicate authority.
   - Why not chosen: Consolidation removes redundancy and elevates domain-specific rules.
2. Split into three ADRs: Identity, Integration Client Pattern, Credential Management:
   - Pros: Finer granularity.
   - Cons: Integration client pattern is already ADR-0056 + ADR-0077. Credential management is a subset of ADR-0052 + ADR-0055. Only identity resolution has enough domain-specific content for a standalone record. One Tier-3 record is simpler.
   - Why not chosen: Over-fragmentation creates governance overhead.
3. Promote to Tier-2 Standard:
   - Pros: Higher authority.
   - Cons: Identity resolution is a domain-specific concern, not a cross-cutting standard. ADR-0051 taxonomy places domain standards at Tier-3.
   - Why not chosen: Correct tier classification per ADR-0051.

## Consequences

- Positive impacts:
- Single authoritative domain standard for identity and external integration, replacing two overlapping legacy ADRs.
- Transport-ownership model correctly distributes identity resolution to its transport owners rather than concentrating it in a single service.
- External integration client classification prevents unnecessary Protocol proliferation for Category C clients.
- Credential lifecycle binding aligns with Twelve-Factor release-phase principles.
- Tradeoffs accepted:
- The canonical `User` model uses Pydantic `BaseModel` (I/O boundary type), which is slightly heavier than `@dataclass(frozen=True)` for a model that also serves as an internal data carrier. This is acceptable because `User` crosses the HTTP boundary via `get_current_user` and is serialized in audit events.
- Risks introduced: None identified.

## Compliance and Boundaries

- Package/infrastructure boundary impact: `User` and `AuthPrincipalSource` are defined in `infrastructure/security/models.py`. Feature packages consume the authenticated principal via `CurrentUserDep` (`Annotated[User, Security(get_current_user)]`) through the injection boundary (ADR-0048 B2). External integration clients are infrastructure-owned and follow the same boundary rules.
- Type boundary impact: `User` model is Pydantic `BaseModel` (I/O boundary). `AuthPrincipalSource` is a `str` enum (value type). `_build_user_from_jwt_payload` is a private module function. `JWKSManager` is the only Category A service; it has no DI alias exposed to feature packages directly. These follow ADR-0065 type boundary rules.
- Startup/plugin registration impact: JWKS client warmup is part of the security initialization phase (current implementation compliant). No import-time side effects (ADR-0048 B4).
- Service contract impact: Standard 3 documents that `_build_user_from_jwt_payload` is a private helper, not a service. Standard 4 classifies all external integration clients per ADR-0077 Standard 1. `JWKSManager` is the sole Category A service in this domain.
- Managed service delegation impact: `JWKSManager` is Tier 1 (managed service wrapper) — it wraps the JWKS endpoint of the IDP (Google Workspace via Backstage). Domain boundary: HTTP caller identity (JWT) is in `security/current_user.py`; platform identity (Slack, Teams) is owned by the platform layer (ADR-0067 S8, ADR-0078); IDP concerns are governed by `DirectoryProvider`; access sync concerns are governed by the access package.

## Codebase Audit (2026-04-29, updated 2026-05-05)

### Current Violations

None. The `infrastructure/identity/` package is being dissolved (Phase B). On the active `feat/infra-identity-settings` branch, the following work is pending:

| Pending Change | Target Location | Standard |
|----------------|----------------|----------|
| Delete `infrastructure/identity/` package (all files) | — | Standard 1, 3 |
| Create `infrastructure/security/models.py` with `User`, `AuthPrincipalSource` | `infrastructure/security/` | Standard 1 |
| Remove `IdentityServiceDep`, `get_identity_service()` | `infrastructure/services/` | Standard 3 |
| Amend `get_current_user()` — remove `identity_service` param; add `_build_user_from_jwt_payload` | `infrastructure/security/current_user.py` | Standard 3 |

### Compliant Patterns (Reference)

| Location | Pattern | Notes |
|----------|---------|-------|
| `app/infrastructure/security/current_user.py` | `get_current_user()` resolves identity from JWT/dev-bypass; returns `User`. | Compliant with Standard 2 (single-source resolution per request). |
| `app/infrastructure/security/jwks.py` | `JWKSManager` with `@lru_cache` warmup and runtime refresh. | Compliant with Standard 5 (JWKS key refresh is not a release-phase violation). |
| `app/infrastructure/directory/` | `DirectoryProvider` Protocol with `GoogleWorkspaceDirectoryProvider` implementation. | Reference pattern for ADR-0077 Standard 2 (Category A with Protocol contract). |

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:
- OWASP Authentication Cheat Sheet (<https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html>) — canonical identity model guidance.
- RFC 7519 JSON Web Token (<https://www.rfc-editor.org/rfc/rfc7519>) — JWT claims and identity extraction.
- PEP 544 Protocols: Structural subtyping (<https://peps.python.org/pep-0544/>) — Protocol contract pattern.
- Twelve-Factor App Factor III: Config (<https://12factor.net/config>) — credential lifecycle binding.
- Clean Architecture (Robert C. Martin) — dependency inversion for identity services.
- Hexagonal Architecture (Alistair Cockburn) — port/adapter pattern for external integration.
- Alignment summary:
- Standard 1 (canonical User model) aligns with OWASP's recommendation for normalized user representation across authentication sources.
- Standard 3 (JWT claim extraction as private helper) aligns with PEP 544's narrow-interface principle and the Single Responsibility Principle — claim extraction has one reason to change (JWT payload structure).
- Standard 5 (credential lifecycle) aligns with Twelve-Factor Factor III and OWASP's credential management guidance.
- Intentional deviations:
- The `User` model uses email as `user_id` rather than an opaque identifier. This is appropriate for the current organizational context (single-tenant, internal tooling) but would need revision for a multi-tenant or public-facing service.

## Freshness Review

- Revalidation date: 2026-05-05
- Is record older than 120 days: No
- Validation summary: Consolidates ADR-0023 and ADR-0024 into one Tier-3 Domain Standard with transport-ownership identity model, external client classification, and credential lifecycle rules. `infrastructure/identity/` dissolved; `User` and `AuthPrincipalSource` relocated to `infrastructure/security/models.py`.
- Follow-up actions:
- Execute Phase B (code corrections on `feat/infra-identity-settings`): delete `infrastructure/identity/`, create `infrastructure/security/models.py`, amend `get_current_user()`, update all import paths.

## Source References

1. Source title: OWASP Authentication Cheat Sheet
   - URL: <https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html>
   - Publisher/maintainer: OWASP Foundation
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Canonical identity model and credential management guidance.
2. Source title: RFC 7519 - JSON Web Token (JWT)
   - URL: <https://www.rfc-editor.org/rfc/rfc7519>
   - Publisher/maintainer: IETF
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: JWT claims extraction for identity resolution; Standard 2 source mapping.
3. Source title: Twelve-Factor App - Factor III (Config)
   - URL: <https://12factor.net/config>
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Credential lifecycle binding; release-phase configuration.
4. Source title: ADR-0077 - Infrastructure Service Contract Standard
   - URL: docs/decisions/adr/0077-infrastructure-service-contract-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Category A classification criteria; `JWKSManager` as sole Category A service in this domain.

## Amendment Record

- 2026-04-30: Added delegation tier declaration and domain boundary clarification. `JWKSManager` governs JWKS endpoint interaction; IDP source of truth governed by `DirectoryProvider`; access sync governed by access package.
- 2026-05-05: Transport-ownership model replaces multi-source priority model. `infrastructure/identity/` dissolved: `User` and `AuthPrincipalSource` (renamed from `IdentitySource`) relocated to `infrastructure/security/models.py`; JWT claim extraction inlined as `_build_user_from_jwt_payload` private helper; `IdentityService` DI service and `IdentityResolver` class deleted. Standards renumbered: S3 → JWT Claim Extraction (private helper); S4 → External Integration Client Classification (was S5); S5 → Credential Lifecycle Binding (was S6). Standard 4 (IdentitySettings dissolution) removed — no service to configure.
