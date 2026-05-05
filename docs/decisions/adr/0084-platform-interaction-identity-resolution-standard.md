---
adr_id: ADR-0084
title: "Platform Interaction Identity Resolution Standard"
status: Draft
decision_type: Domain Standard
tier: Tier-3
primary_domain: Security
secondary_domains:
 - Dependency and Composition
 - Transport and API
owners:
 - SRE Team
date_created: 2026-05-05
last_updated: 2026-05-05
last_reviewed: 2026-05-05
next_review_due: 2026-09-01
constrained_by:
 - ADR-0044
 - ADR-0050
 - ADR-0054
 - ADR-0061
 - ADR-0065
 - ADR-0077
 - ADR-0078
impacts:
 - ADR-0059
 - ADR-0067
supersedes: []
superseded_by: []
review_state: draft
related_records:
 - ADR-0046
 - ADR-0048
 - ADR-0076
related_packages:
 - app/infrastructure/platforms/providers
 - app/infrastructure/security
---

# Platform Interaction Identity Resolution Standard

> **Status: DRAFT** — This record captures the generic contract that all platform interaction providers must satisfy when resolving a platform user identifier to a canonical `User`. It is not yet accepted. Open questions are marked with `[OPEN]`. Slack implementation notes in ADR-0067 S8 are the concrete reference; this standard will unify the generic rule before Teams or any additional platform is implemented.

---

## Context

- Problem statement: The SRE Bot receives interactions from platform surfaces (Slack, Teams, potentially others) where the acting user is identified by a platform-native identifier — a Slack `user_id`, a Teams `activity.from_property.id`, etc. Business logic must operate against a canonical `User` (ADR-0061 Standard 1). The gap is: no record defines the generic contract that all platform providers must satisfy when performing this resolution. ADR-0061 explicitly excludes platform-specific resolution from its scope. ADR-0078 defines platform services as Category C but does not specify what identity resolution must look like. ADR-0067 S8 specifies Slack's implementation, but that is a Tier-4 per-platform rule. When Teams or another platform is implemented, there is currently no Tier-3 standard to constrain the design.

  A secondary concern: `AuthPrincipalSource` (defined in `infrastructure/security/models.py` per ADR-0061) currently has values `API_JWT`, `SLACK`, `WEBHOOK`, `SYSTEM`. Adding a new platform requires adding a new enum value. No record currently governs what adding that value entails — what contract the new platform must satisfy before the value can be used in production code.

- Business/operational drivers:
  - Prevent divergence: without a generic standard, each platform provider will independently invent its identity resolution contract, making audit, error handling, and testing inconsistent.
  - Governance hook for new platforms: adding `AuthPrincipalSource.TEAMS` (or any future value) must be gated on satisfying this standard, not merely on the enum value being compilable.
  - Correctness: platform-native identity objects (Slack `User` dicts, Teams `ChannelAccount`, etc.) must not cross the feature boundary — only the canonical `User` may. Without a standard, there is no rule preventing this.

- Constraints:
  - ADR-0050 Standard 1 (integration boundary mandate): Any call to an external platform API to resolve user details (e.g., Slack `users.info`, Teams Graph API `/users/{id}`) is an external service boundary crossing and must produce `OperationResult`. The initial identifier extraction from the interaction payload is a pure read from a trusted, already-authenticated data structure and does not require `OperationResult` wrapping.
  - ADR-0061 Standard 1: The output of platform identity resolution must be a canonical `User` as defined there — including `user_id` as the canonical email address.
  - ADR-0054: Resolution events and failures must emit structured logs with correlation context. No tokens, IDs-that-are-PII, or platform credentials in log payloads.
  - ADR-0077 Standard 1: Platform providers are Category C. This standard does not promote them to Category A. The generic resolution contract defined here is a Category C obligation, not a Protocol interface.
  - ADR-0078 Standard 1: Each platform has its own concrete provider type. This standard does not introduce a unified `InteractionProvider` Protocol.

- Non-goals:
  - This record does not define per-platform field mappings (e.g., which `TurnContext.activity` property is the canonical user identifier for Teams). Those are Tier-4 concerns in each platform's Integration Decision ADR.
  - This record does not define trust basis verification mechanics (e.g., how the Slack Socket Mode tunnel is authenticated, how the Bot Framework validates the Bot Connector JWT). Trust basis is documented per platform in Tier-4 ADRs; this record only requires that the trust basis be documented there.
  - This record does not govern HTTP/JWT identity resolution. That is ADR-0061 Standard 3.
  - This record does not define what feature handlers do after receiving a `User`. That is ADR-0059's scope.

---

## Decision

### Standard 1: Platform Identity Resolution Contract

Every platform provider that handles authenticated interactions — where a feature handler may need to act on behalf of an identified user — must expose a resolution method satisfying this contract:

**Inputs:**
- A platform user identifier (`str`): the platform-native identifier extracted from the authenticated interaction payload (e.g., Slack `user_id`, Teams `activity.from_property.id`). The provider is responsible for this extraction before calling the resolution logic.
- `[OPEN]` Whether `team_id` / workspace-scoping context is a required input or an optional parameter is platform-dependent. This standard requires that the method signature be documented in the platform's Tier-4 ADR, and that any scoping input needed for uniqueness be present.

**Output:**
- `OperationResult[User]` — because resolution requires a call to an external platform API (e.g., `users.info`, Graph API) to obtain the canonical email address. This is an external service boundary per ADR-0050 Standard 1. Resolution must not return a bare `User` that silently suppresses API errors.

**Output constraints:**
- On success: the returned `User` must satisfy ADR-0061 Standard 1. Specifically:
  - `user_id` must be the canonical email address. If the platform profile has no email, resolution must fail (see failure semantics below).
  - `source` must be set to the appropriate `AuthPrincipalSource` enum value (see Standard 2).
  - `platform_id` must be set to the platform-native identifier (for audit and debugging).
- On failure: return `OperationResult` with `PERMANENT_ERROR` (profile has no email, user not found) or `TRANSIENT_ERROR` (platform API unavailable, rate-limited). Do not raise exceptions for API-level failures — raise only for programmer errors (e.g., `None` passed as user_id).

**Prohibition:** Platform-native user objects (Slack profile dicts, Teams `ChannelAccount`, etc.) must not be returned from the resolution method or passed across the feature boundary. The canonical `User` is the only identity representation that may cross the infrastructure → feature boundary (ADR-0048 Boundary 2).

### Standard 2: AuthPrincipalSource Governance

`AuthPrincipalSource` (in `infrastructure/security/models.py`) is the enumeration of all interaction surfaces that can produce an authenticated principal. Adding a new value is gated on:

1. A Tier-4 Integration Decision ADR for the platform that documents:
   - The trust basis for accepting the platform identifier from the interaction payload (what prevents injection of an arbitrary identifier by a malicious payload).
   - The external API used to resolve the platform identifier to a canonical email.
   - Failure semantics: what happens if the API is unavailable or the user has no email.
   - Caching rules: whether and how resolution results may be cached (scope, TTL, invalidation).
2. An amendment to this record (ADR-0084) listing the new enum value and the Tier-4 ADR that governs it.

**Current enum values and governing records:**

| Value | Platform | Governing Record |
|-------|----------|-----------------|
| `API_JWT` | HTTP API (JWT bearer) | ADR-0061 Standard 3 |
| `SLACK` | Slack Socket Mode | ADR-0067 Standard 8 |
| `WEBHOOK` | Inbound webhook | ADR-0061 Standard 2 (inline extraction) |
| `SYSTEM` | Background/system jobs | ADR-0061 Standard 2 (inline constant) |
| `TEAMS` | Teams Bot Framework | `[OPEN]` — Tier-4 ADR not yet authored. `TeamsPlatformProvider` predates this governance framework (non-compliant stub). |

### Standard 3: Trust Basis Annotation Requirement

Every platform provider that performs interaction identity resolution must document its trust basis in its Tier-4 ADR. The trust basis answers: *what authentication mechanism prevents a malicious actor from injecting an arbitrary user identifier into the interaction payload?*

Examples of acceptable trust basis documentation:
- "Trust is established at the Socket Mode connection level via `SLACK_APP_TOKEN`. Individual event messages are not HMAC-signed; the user identifier is trusted because it arrives over the authenticated tunnel." (ADR-0067 S2, S5-R2.)
- "Trust is established by the Bot Framework service, which validates the Bot Connector JWT before forwarding the activity to the application."

A platform provider with no documented trust basis may not be used in production feature handlers.

### Standard 4: Logging Requirements

Every platform identity resolution attempt must emit a structured log entry (ADR-0054):

- On success: `level=DEBUG`, `event="platform_identity_resolved"`, fields: `platform`, `platform_id` (the platform-native id — only if non-PII per platform assessment), `resolution_source` (which external API was called), `correlation_id`.
- On failure: `level=WARNING`, `event="platform_identity_resolution_failed"`, fields: `platform`, `error_code`, `operation_result_status`, `correlation_id`. Must not log the raw platform identifier or any token material.

### Standard 5: Non-Compliant State (Pre-Governance)

`TeamsPlatformProvider` (`app/infrastructure/platforms/providers/teams.py`) is a non-compliant stub that predates this governance framework. It does not yet implement a resolution method satisfying Standard 1. This is accepted as a known gap. Before any feature handler uses Teams identity in production:

1. A Tier-4 ADR for Teams platform integration must be authored.
2. `AuthPrincipalSource.TEAMS` must be added to the enum (amendment to this record, Standard 2).
3. `TeamsPlatformProvider.resolve_user()` must be implemented to satisfy Standard 1.
4. The non-compliant annotation on `TeamsPlatformProvider` must be removed.

---

## Alternatives Considered

1. Absorb this standard into ADR-0061:
   - Pros: fewer records.
   - Cons: ADR-0061 explicitly scopes to HTTP/JWT transport and external integration client classification. Platform interaction resolution is a distinct domain concern. Mixing them would require ADR-0061 to import Platform concepts it currently correctly excludes.
   - Why not chosen: Correct tier separation; ADR-0061's non-goal boundary is well-reasoned.

2. Absorb this standard into ADR-0078:
   - Pros: ADR-0078 already governs platform services architecture.
   - Cons: ADR-0078 is Tier-2 (cross-cutting standard for platform service patterns). Identity resolution is a domain-specific concern within the security domain. Putting it in a Tier-2 architecture record would mix abstraction levels.
   - Why not chosen: Correct tier placement in security domain at Tier-3.

3. Define a unified `InteractionIdentityResolver` Protocol:
   - Pros: type-safe, mockable.
   - Cons: ADR-0078 Standard 1 explicitly rejects unified Protocols for platform services because platform APIs are fundamentally incompatible at the type level. The resolution contract defined here (Standard 1) is a *behavioral obligation*, not a shared interface — it is enforced by documentation and review, not by Protocol structural subtyping.
   - Why not chosen: Consistent with ADR-0078's rejection of premature abstraction (Rule of Three not yet met: only Slack is implemented).

---

## Consequences

- Positive impacts:
  - Provides a governance gate for adding new `AuthPrincipalSource` values — no new platform can silently bypass the trust-basis and failure-semantics requirements.
  - Establishes a consistent audit footprint for platform identity resolution events across all platforms.
  - Closes the documentation gap between ADR-0061 (HTTP transport) and ADR-0067 S8 (Slack-specific) by capturing the generic constraint that both implementations satisfy.
- Tradeoffs accepted:
  - The `OperationResult[User]` return type requirement (Standard 1) conflicts with the current ADR-0067 S8 R2 signature (`-> User`). ADR-0067 S8 R2 must be corrected when Phase B implements `SlackPlatformProvider.resolve_user()`. This is a known inconsistency that this draft surfaces.
- Open questions (blocking acceptance):
  - `[OPEN-1]` Should the resolution method name be standardized (e.g., `resolve_user`) or left to each provider? Standardizing aids discoverability; leaving it open preserves Category C flexibility. **Leaning toward: standardize the name, allow signature variation for platform-specific scoping parameters.**
  - `[OPEN-2]` Caching: Standard 2 requires per-platform caching rules in the Tier-4 ADR. Should this standard define a default (no cache; per-request only) that platforms must explicitly opt out of? **Leaning toward: yes — default is no cross-request cache; opt-out requires documented rationale in Tier-4 ADR.**
  - `[OPEN-3]` Does `AuthPrincipalSource.TEAMS` need to exist before `TeamsPlatformProvider` can be made compliant, or can the enum value be added speculatively? **Leaning toward: enum value addition is gated on Tier-4 ADR, per Standard 2.**

---

## Compliance and Boundaries

- Platform providers satisfying this standard: `SlackPlatformProvider` (partial — ADR-0067 S8 exists; Standard 1 return type inconsistency pending resolution in Phase B).
- Platform providers not yet satisfying this standard: `TeamsPlatformProvider` (non-compliant stub, per Standard 5).
- Feature packages: consume `User` via `CurrentUserDep` (HTTP) or via the return value of `provider.resolve_user()` (platform transport). They must not consume platform-native identity objects directly.

---

## Amendment Record

*(empty — draft, no amendments yet)*
