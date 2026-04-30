---
adr_id: ADR-0061
title: "Identity and External Integration Contract Standard"
status: Draft
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
last_updated: 2026-04-30
last_reviewed: 2026-04-30
next_review_due: 2026-08-27
constrained_by:
 - ADR-0044
 - ADR-0045
 - ADR-0048
 - ADR-0050
 - ADR-0052
 - ADR-0054
 - ADR-0055
 - ADR-0056
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
 - app/infrastructure/identity
 - app/infrastructure/security
 - app/infrastructure/clients
 - app/infrastructure/services
---

# Identity and External Integration Contract Standard

## Context

- Problem statement: Two legacy ADRs defined overlapping guidance for identity resolution and external service integration. ADR-0023 (Identity Resolution Across Platforms, Tier-2) defined a canonical `User` model and multi-source `IdentityResolver` (Slack, JWT, webhook, system). ADR-0024 (External Service Integration, Tier-2) defined the client facade pattern with constructor-injected settings, `@lru_cache` providers, `Annotated[..., Depends(...)]` aliases, and mandatory `OperationResult` returns. These two records were authored before the ADR governance model (ADR-0044), the service contract standard (ADR-0077), and the provider composition standard (ADR-0056) existed. Their content is now partially superseded by multiple canonical standards, and the remaining domain-specific rules need consolidation into one Tier-3 Domain Standard.

  The codebase audit reveals concrete violations: `IdentityService` is a Category A service (ADR-0077) that lacks a Protocol contract; feature code depends on the concrete `IdentityService` class, not a Protocol type. The `IdentityService` constructor accepts the full `Settings` object instead of a narrow identity-specific settings slice (ADR-0055 Standard 1, ADR-0056 Standard 1 violations). External integration client facades generally comply with the `OperationResult` pattern (ADR-0050) but lack Protocol contracts where backing-service substitution is architecturally relevant.

- Business/operational drivers:
- Consolidate identity resolution and external integration domain rules into one Tier-3 standard, referencing upstream Tier-1 and Tier-2 standards for cross-cutting concerns (DI, providers, settings, OperationResult).
- Establish the Protocol contract requirement for `IdentityService` as mandated by ADR-0077 Standard 1 (Category A, P1 migration priority).
- Define identity credential lifecycle alignment with ADR-0052 (release-phase binding) — identity provider credentials (Google service account keys, Slack tokens, JWT signing keys) must be bound at release phase, not fetched at runtime.
- Codify the multi-source identity resolution model with clear source-priority and conflict-resolution semantics.
- Classify external integration clients per ADR-0077 to establish which need Protocol contracts and which are Category C implementation details.
- Constraints:
- ADR-0045 Principle 6 (Protocol-driven service contracts): `IdentityService` must expose a Protocol type since it is consumed by feature packages across the injection boundary.
- ADR-0048 Boundary 2 (single injection surface): Features must consume identity services through `Annotated[Protocol, Depends(provider)]`, not by importing concrete `IdentityService`.
- ADR-0048 Boundary 7 (Protocol contract surface): Feature packages depend on Protocol types, not concrete implementations.
- ADR-0050 Standard 1 (integration boundary mandate): All external identity lookups (Slack API, JWT validation, directory queries) must return `OperationResult`.
- ADR-0052 (build-release-run): Identity provider credentials are release-phase configuration, not runtime-fetched secrets.
- ADR-0054 (structured logging): Identity resolution events must emit structured logs with correlation context. No credentials, tokens, or PII in log payloads.
- ADR-0055 Standard 1 (independent singleton): Identity settings must have their own `BaseSettings` class and `@lru_cache` provider, not share the root Settings object.
- ADR-0056 Standard 1 (narrow-slice injection): `IdentityService` must receive only its identity-specific settings, not the full `Settings` aggregator.
- ADR-0076 Standard 2 (configuration via injection): Identity infrastructure must not directly import sibling configuration; settings flow via constructor.
- ADR-0077 Standard 1 (service classification): `IdentityService` is Category A (P1 priority); external integration clients are Category C (implementation details).
- Non-goals:
- This record does not define the `IdentityService` Protocol interface (method signatures, return types). That is an implementation detail governed by ADR-0077 Standard 2 (Protocol contract pattern).
- This record does not define JWT validation algorithms or JWKS rotation mechanics. Those are security implementation details.
- This record does not define platform-specific user resolution logic (Slack user lookup, Teams identity mapping). Platform-specific resolution is a Category C implementation detail per ADR-0077.
- This record does not govern the access control model (roles, permissions, scopes). That is a separate domain.

## Decision

- Chosen approach: Consolidate ADR-0023 and ADR-0024 into a Tier-3 Domain Standard that defines domain-specific rules for identity resolution and external integration contracts, referencing upstream standards for all cross-cutting concerns.
- Why this approach: ADR-0023's canonical User model and multi-source resolution are domain-specific rules that belong at Tier-3. ADR-0024's client facade, provider, and DI patterns are now fully codified in upstream Tier-2 standards (ADR-0050, ADR-0055, ADR-0056, ADR-0077). Consolidation eliminates redundancy and ensures identity-specific rules are governed at the correct tier.

### Standard 1: Canonical Identity Model

The identity domain must define a canonical `User` model that normalizes platform-specific user representations into a single internal type:

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str` | Canonical unique identifier — the user's primary email address. All downstream services use this as the identity key. |
| `email` | `str` | User's email address (same as `user_id` in current implementation; preserved for explicit semantics). |
| `display_name` | `str` | Human-readable display name. |
| `source` | `IdentitySource` enum | Origin of the identity resolution: `SLACK`, `API_JWT`, `WEBHOOK`, `SYSTEM`. |
| `platform_id` | `str \| None` | Platform-specific user identifier (Slack user ID, JWT `sub` claim, etc.). Available for logging and debugging; must not be used for business logic decisions (ADR-0050 Standard 5 — provider agnosticism). |
| `permissions` | `list[str]` | Resolved permissions/scopes for the current session. Source depends on the identity provider (JWT scopes, platform-resolved roles). |
| `metadata` | `dict[str, Any]` | Source-specific metadata (Slack team ID, JWT claims, etc.). Available for logging only; must not drive business logic. |

The `User` model is a Pydantic `BaseModel` because it crosses the HTTP I/O boundary (returned by `get_current_user` dependency, serialized in audit logs). This is correct per ADR-0040 type boundary rules.

Platform-specific extensions (e.g., `SlackUser` with `slack_user_id`, `slack_team_id`) are permitted as subclasses within the identity infrastructure package. Feature code must depend on the base `User` type, not platform-specific subclasses.

### Standard 2: Multi-Source Resolution Contract

The identity resolution service must support multiple identity sources with deterministic resolution:

1. **Source priority**: When the same request carries multiple identity signals (e.g., JWT + Slack context), the resolution order is:
   - JWT (highest priority — explicitly authenticated API caller).
   - Platform-specific (Slack user ID, Teams user principal) — used for platform command/interaction handlers.
   - Webhook payload identity — used for inbound webhook processing.
   - System identity — synthetic user for background jobs and scheduled tasks.

2. **Resolution failure semantics**: If identity resolution fails for the primary source:
   - Return `OperationResult.unauthorized()` with error_code `IDENTITY_RESOLUTION_FAILED`.
   - Do not fall through to secondary sources. Each request context has exactly one expected identity source.
   - Log the failure with structured context (source, error, correlation_id) per ADR-0054. No credentials or tokens in log payloads.

3. **Conflict handling**: A single request must not resolve to multiple identities. If a conflict is detected (e.g., JWT sub ≠ Slack user email), the resolution must fail with `PERMANENT_ERROR` and error_code `IDENTITY_CONFLICT`.

### Standard 3: IdentityService Protocol Contract

`IdentityService` is classified as **Category A, P1 migration priority** per ADR-0077 Standard 1. The Protocol contract migration must follow ADR-0077 Standard 5 (migration path):

1. **Create Protocol**: Define `IdentityServiceProtocol` in `app/infrastructure/identity/protocol.py` with `@runtime_checkable`. The Protocol defines the public interface consumed by feature packages.
2. **Rename implementation**: The current `IdentityService` class becomes the concrete implementation (e.g., `DefaultIdentityService` or retains its name with Protocol as the public contract).
3. **Update provider return type**: `get_identity_service()` return annotation becomes `IdentityServiceProtocol`.
4. **Update dependency alias**: `IdentityServiceDep = Annotated[IdentityServiceProtocol, Depends(get_identity_service)]`.
5. **Verify**: `mypy` confirms all feature code depends on the Protocol, not the concrete class.

All Protocol methods that perform external lookups (Slack API, directory queries) must return `OperationResult[User]` per ADR-0050 Standard 1. Methods that perform only local computation (JWT parsing without external validation) may return the result directly.

**Delegation tier declaration (ADR-0045 P7):** `IdentityService` is classified as **Tier 1 (managed service wrappers)** in the ADR-0077 Category A delegation tier table. The identity resolution backends all delegate to managed external service APIs:

- **JWT / JWKS validation** — delegates to managed JWKS endpoints for signature verification. `JWKSManager` creates a `PyJWKClient` per configured issuer; key material is runtime-refreshed per Standard 6; the endpoint URL is release-phase bound per ADR-0052. The identity provider (IDP) that issues JWTs is a managed service (e.g., Google, Cognito, Entra ID).
- **Slack API** — resolves platform user identity via the Slack Web API. Platform-specific resolution is Category C per ADR-0078, but the managed API call is the backing service.
- **Webhook payload** — extracts identity claims from inbound webhook payloads signed by managed external services.

The `IdentityService` itself contains proportional coordination logic (multi-source resolution priority, conflict handling per Standard 2) that orchestrates across these managed service backends. This orchestration layer is domain-specific glue, not a separate infrastructure concern — it does not implement identity provider functionality, it resolves callers by delegating to managed APIs. No Tier 3 justification is required.

**Domain boundary clarification:** `IdentityService` (this standard) governs **interaction identity resolution** — determining *who is calling* from an HTTP request or collaboration platform interaction. It does NOT govern:

- **IDP (source of truth)** — the canonical user/group directory is governed by the `DirectoryProvider` Protocol (Category A, complete). The IDP is currently Google Workspace; a switch to Entra ID or another provider would be a `DirectoryProvider` implementation change, not an `IdentityService` change.
- **Access sync (IDP → third-party targets)** — syncing identities from the IDP into downstream systems (e.g., AWS Identity Store, GitHub) is an access-domain concern governed by the access package. AWS Identity Store is a *sync target* that receives identities pushed from the IDP — it is not an identity provider and is not part of IdentityService's resolution path.

If a future identity source requires custom resolution logic with no managed API backend, it must document a Tier 3 justification per ADR-0045 P7 and be flagged for future delegation.

### Standard 4: Identity Settings Dissolution

The `IdentityService` must receive a narrow identity-specific settings slice, not the full `Settings` aggregator:

1. **Define `IdentitySettings`** as an independent `BaseSettings` class in `app/infrastructure/configuration/infrastructure/identity.py` (or within the identity package if migrated to `app/packages/`).
2. **Provider**: `get_identity_settings()` with `@lru_cache(maxsize=1)` in the appropriate provider module.
3. **Constructor injection**: `IdentityService.__init__(self, settings: IdentitySettings, ...)` — never `settings: Settings`.
4. **Fields**: Only the settings consumed by identity resolution (e.g., JWKS configuration, dev bypass token, identity source configuration). Settings for specific identity providers (Slack tokens, Google service account keys) are received via their own provider-specific settings (ADR-0055 Standard 3).

This standard implements ADR-0055 Standard 1 and ADR-0056 Standard 1 for the identity domain.

### Standard 5: External Integration Client Classification

External integration clients are classified per ADR-0077 Standard 1:

| Service | Category | Protocol Required | Delegation Tier | Rationale |
|---------|----------|-------------------|-----------------|-----------|
| `IdentityService` | **A** (Contract Required) | Yes — P1 priority | Tier 1 (managed service wrappers — JWT/JWKS endpoints, Slack API) | Feature-facing; abstracts multi-source identity resolution; backing implementation may change. |
| `IdentityResolver` | **C** (Implementation Detail) | No | N/A | Internal to `IdentityService`; not consumed directly by features. |
| Slack Client (slack_sdk) | **C** (Implementation Detail) | No | N/A | Platform-specific SDK wrapper; consumed by `SlackService` (ADR-0078 Category C). |
| Google Workspace Clients | **C** (Implementation Detail) | No | N/A | Provider-specific API facades; consumed via `DirectoryProvider` Protocol (Category A, complete). |
| AWS Clients (identity store, organizations, SSO) | **C** (Implementation Detail) | No | N/A | Provider-specific API facades; consumed by access sync adapters. Domain-specific operations documented as Category C exceptions per ADR-0077 Standard 3. |
| GitHub Client | **C** (Implementation Detail) | No | N/A | Provider-specific API facade. |
| GC Notify Client | **C** (Implementation Detail) | No | N/A | `NotificationService` wraps this; `NotificationService` is Category A P2 (ADR-0077). |

**Rule**: Feature packages must consume Category A services (e.g., `IdentityServiceProtocol`, `DirectoryProvider`, `StorageService`) via the injection boundary (ADR-0048 Boundary 2). Direct import of Category C clients from feature code is prohibited unless documented as a Category C exception (ADR-0077 Standard 3).

### Standard 6: Credential Lifecycle Binding

Identity provider credentials follow ADR-0052 (build-release-run):

1. **Release-phase binding**: All credentials (Slack tokens, Google service account key paths, JWT signing keys, JWKS endpoint URLs) are environment variables or mounted files bound at the ECS task definition level. They must not be fetched from SSM, Secrets Manager, or other runtime sources during application startup (ADR-0068 migration target).
2. **Credential rotation**: JWKS endpoints are the exception — they are runtime-refreshed because key rotation is an inherent part of the OIDC protocol. The `JWKSManager` (current implementation) correctly caches and refreshes JWKS keys at runtime. This is not a violation of ADR-0052 because the JWKS endpoint URL is release-phase bound; only the key material is runtime-refreshed.
3. **Credential safety**: No credentials, tokens, or key material in structured log payloads (ADR-0054). No credentials in error responses (ADR-0060 Standard 3). Credentials must not appear in `OperationResult.message` or `error_code` fields.

## Alternatives Considered

1. Maintain separate ADR-0023 and ADR-0024:
   - Pros: Existing records cover identity and integration separately.
   - Cons: ADR-0024's patterns (facade, provider, DI alias, OperationResult) are now fully codified in ADR-0050, ADR-0055, ADR-0056, ADR-0077. Keeping ADR-0024 creates duplicate authority. ADR-0023's identity model needs Protocol contract alignment per ADR-0077.
   - Why not chosen: Consolidation removes redundancy and elevates domain-specific rules.
2. Split into three ADRs: Identity, Integration Client Pattern, Credential Management:
   - Pros: Finer granularity.
   - Cons: Integration client pattern is already ADR-0056 + ADR-0077. Credential management is a subset of ADR-0052 + ADR-0055. Only identity resolution has enough domain-specific content for a standalone record. One Tier-3 record is simpler.
   - Why not chosen: Over-fragmentation creates governance overhead.
3. Promote to Tier-2 Standard:
   - Pros: Higher authority.
   - Cons: Identity resolution is a domain-specific concern, not a cross-cutting standard. ADR-0051 taxonomy places domain standards at Tier-3.
   - Why not chosen: Correct tier classification per ADR-0051.
4. Defer until IdentityService Protocol migration is complete:
   - Pros: Could write the standard against the migrated state.
   - Cons: The standard defines the target state that the migration aims toward. Writing it first provides a clear migration target. Migration actions are independently deployable per ADR-0077 Standard 5.
   - Why not chosen: Standards should be authored before implementation, not after.

## Consequences

- Positive impacts:
- Single authoritative domain standard for identity and external integration, replacing two overlapping legacy ADRs.
- Protocol contract requirement for `IdentityService` is now explicitly mandated with migration priority.
- Settings dissolution target for identity is clear — `IdentitySettings` with narrow-slice injection.
- External integration client classification prevents unnecessary Protocol proliferation for Category C clients.
- Credential lifecycle binding aligns with Twelve-Factor release-phase principles.
- Tradeoffs accepted:
- The canonical `User` model uses Pydantic `BaseModel` (I/O boundary type), which is slightly heavier than `@dataclass(frozen=True)` for a model that also serves as an internal data carrier. This is acceptable because `User` crosses the HTTP boundary via `get_current_user` and is serialized in audit events.
- The `SlackUser` subclass pattern creates a platform-specific extension at the identity infrastructure level. This is acceptable as an internal implementation detail (Category C) as long as feature code depends only on the base `User` type.
- Risks introduced:
- Protocol contract migration for `IdentityService` may surface interface inconsistencies between the current concrete class and what a clean Protocol would define. Mitigation: migrate the Protocol to match the existing interface first; refine in a subsequent iteration.
- Settings dissolution for identity requires identifying all consumers of `Settings` within the identity package. Mitigation: the codebase audit (ADR-0055) has already identified the violations.
- Mitigations:
- ADR-0077 Standard 5 defines the independently deployable migration path for Protocol contracts.
- ADR-0055 Standard 4 provides transitional posture for settings that are mid-dissolution.

## Compliance and Boundaries

- Package/infrastructure boundary impact: `IdentityService` is infrastructure-owned (`app/infrastructure/identity/`). Feature packages consume it via Protocol (Standard 3) through the injection boundary (ADR-0048 B2). External integration clients are infrastructure-owned and follow the same boundary rules.
- Type boundary impact: `User` model is Pydantic `BaseModel` (I/O boundary). `IdentityServiceProtocol` is a `Protocol` class (service contract). `IdentitySettings` is Pydantic `BaseSettings` (configuration boundary). These follow ADR-0040 type boundary rules.
- Startup/plugin registration impact: Identity service initialization happens during lifespan startup (ADR-0046 phase ordering). JWKS client warmup is part of the security initialization phase (current implementation compliant). No import-time side effects (ADR-0048 B4).
- Settings partitioning impact: Standard 4 mandates `IdentitySettings` extraction from the monolithic `Settings` aggregator. This is a specific instance of ADR-0055 Standard 1.
- DI alias ceremony impact: Standard 3 mandates updating the DI alias to use Protocol type. This follows ADR-0056 Standard 4.
- Service contract impact: Standard 3 mandates Protocol contract per ADR-0077 Standard 2. Standard 5 classifies all external integration clients per ADR-0077 Standard 1.
- Managed service delegation impact: Standard 3 delegation tier declaration implements ADR-0045 P7 at the identity domain level. `IdentityService` is Tier 1 (managed service wrappers) — identity resolution delegates to managed APIs (JWT/JWKS endpoints, Slack API, webhook payloads from managed services). No Tier 3 justification is required. Standard 5 classification table includes delegation tier for the Category A service; Category C services are marked N/A (delegation tiers apply only to Category A). Domain boundary is explicitly declared: `IdentityService` governs interaction identity resolution only; IDP concerns are governed by `DirectoryProvider`; access sync concerns are governed by the access package. If a future identity source requires custom resolution logic, it must document a Tier 3 justification and be flagged for future delegation.

## Codebase Audit (2026-04-29)

### Current Violations

| Location | Violation | Standard |
|----------|-----------|----------|
| `app/infrastructure/identity/service.py` | `IdentityService` has no Protocol contract; features depend on concrete class. | Standard 3 (ADR-0077 Category A P1) |
| `app/infrastructure/services/providers.py` | `get_identity_service()` passes full `Settings` to `IdentityService`. | Standard 4 (ADR-0055 S1, ADR-0056 S1) |
| `app/infrastructure/services/dependencies.py` | `IdentityServiceDep` type alias uses concrete `IdentityService`, not Protocol. | Standard 3 |
| `app/infrastructure/identity/models.py` | `SlackUser(User)` subclass — permitted as Category C, but feature code must not depend on it. | Standard 1 (verify no feature-level `SlackUser` imports) |

### Compliant Patterns (Reference)

| Location | Pattern | Notes |
|----------|---------|-------|
| `app/infrastructure/security/current_user.py` | `get_current_user()` resolves identity from JWT/dev-bypass; returns `User`. | Compliant with Standard 2 (single-source resolution per request). |
| `app/infrastructure/security/jwks.py` | `JWKSManager` with `@lru_cache` warmup and runtime refresh. | Compliant with Standard 6 (JWKS key refresh is not a release-phase violation). |
| `app/infrastructure/directory/` | `DirectoryProvider` Protocol with `GoogleWorkspaceDirectoryProvider` implementation. | Reference pattern for Standard 3 (Category A with Protocol contract). |

### Migration Priority

| Migration | Priority | Blocking |
|-----------|----------|----------|
| `IdentityServiceProtocol` creation | P1 (ADR-0077) | Blocks Standard 3 compliance |
| `IdentitySettings` extraction | P1 | Blocks Standard 4 compliance; depends on ADR-0055 Phase 1 |
| Provider return type update | P1 | Follows Protocol creation |
| DI alias update | P1 | Follows provider update |
| Feature import audit (SlackUser) | P2 | Independent |

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
- Standard 3 (Protocol contract) aligns with PEP 544 and the Hexagonal Architecture port pattern — the Protocol is the port; the concrete IdentityService is the adapter.
- Standard 6 (credential lifecycle) aligns with Twelve-Factor Factor III and OWASP's credential management guidance.
- Intentional deviations:
- The `User` model uses email as `user_id` rather than an opaque identifier. This is appropriate for the current organizational context (single-tenant, internal tooling) but would need revision for a multi-tenant or public-facing service.
- `SlackUser` subclass uses inheritance rather than composition. This is accepted as a Category C implementation detail that does not cross the feature boundary.

## Freshness Review

- Record age at review time (days): 1
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Consolidates ADR-0023 and ADR-0024 into one Tier-3 Domain Standard with Protocol contract mandate, settings dissolution target, external client classification, and credential lifecycle rules. All upstream constraint references verified against current accepted ADRs.
- Follow-up actions:
- Mark ADR-0023 and ADR-0024 as superseded with `superseded_by: [ADR-0061]`.
- Execute P1 migrations: IdentityServiceProtocol, IdentitySettings extraction, provider/DI alias updates.
- Audit feature code for `SlackUser` imports.

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
   - Relevance summary: JWT claims extraction for identity resolution; Standard 2 source priority.
3. Source title: PEP 544 - Protocols: Structural subtyping
   - URL: <https://peps.python.org/pep-0544/>
   - Publisher/maintainer: Python Software Foundation
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Protocol contract pattern for IdentityServiceProtocol.
4. Source title: Twelve-Factor App - Factor III (Config)
   - URL: <https://12factor.net/config>
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Credential lifecycle binding; release-phase configuration.
5. Source title: ADR-0077 - Infrastructure Service Contract Standard
   - URL: docs/decisions/adr/0077-infrastructure-service-contract-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Category A classification and Protocol contract pattern for IdentityService.
6. Source title: ADR-0023, ADR-0024 (Legacy)
   - URL: docs/decisions/adr/
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Superseded legacy records whose domain-specific content is consolidated here.

## Amendment Record

- 2026-04-30: Delegation tier declaration amendment. Added delegation tier declaration to Standard 3 (IdentityService Protocol Contract) per ADR-0045 P7 (Managed Service Delegation Hierarchy). IdentityService is Tier 1 (managed service wrappers — JWT/JWKS endpoints, Slack API). Added explicit domain boundary clarification: IdentityService governs interaction identity resolution only; IDP (source of truth) is governed by DirectoryProvider; access sync (IDP → third-party targets) is governed by the access package. AWS Identity Store is a sync target, not part of IdentityService's resolution path. Added Delegation Tier column to Standard 5 classification table. Added managed service delegation impact to Compliance section. See managed-services-delegation-adr-review-tracker-2026-04-30.md Item #22.
