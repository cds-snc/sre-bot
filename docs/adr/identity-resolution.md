---
title: "Identity Resolution"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [security, api]
constrained_by: [api-security.md, transport-slack.md, layered-architecture.md, infrastructure-service-classification.md, dependency-injection.md, type-boundaries.md, data-redaction-policy.md, logging-observability.md, operation-result-pattern.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Identity Resolution

## Context and Problem Statement

Several inbound paths admit work into the application: HTTP requests authenticated by JWT Bearer tokens; Slack interactivity events delivered over a pre-authenticated channel; webhook deliveries signed by upstream senders; SQS messages produced by an earlier intent on this application; background jobs that have no human caller at all. Each of these arrives with a different shape of evidence about *who* the actor is — a JWT payload's claims, a Slack `user_id` and team context, a webhook signature plus an embedded actor field, or nothing.

The problem this record addresses: **what is the canonical representation of "the actor on whose behalf this work runs," and how is that representation produced from each inbound path?** The answer determines:

1. Whether feature code can ask one question — "who is the user on this request?" — and get a consistent value-typed answer regardless of which transport the work arrived on.
2. Whether identity resolution is a centralized cross-transport orchestrator (with all the coupling that implies) or a per-transport responsibility that each transport owns.
3. Whether the canonical type is enriched with platform-specific context that handlers come to depend on, defeating transport substitutability.
4. Whether identity resolution is permitted to perform external I/O (look up profile data from a platform API) and, if so, how that I/O composes with the application's outcome envelope.
5. How the actor is bound to log context, redacted in observability output, and deduplicated across processes when the same person interacts on multiple transports.

**Constraints:**

- The application is a multi-transport system ([multi-transport-architecture.md](multi-transport-architecture.md)). Inbound paths are per-platform first-class adapters; there is no unified Platform Protocol. Identity resolution must compose with that posture.
- HTTP authentication is JWT Bearer with multi-issuer JWKS, validated by a single `get_current_user` FastAPI `Security()` dependency ([api-security.md](api-security.md)). The canonical User type is what that dependency returns.
- Service-layer outcomes use the closed five-status envelope ([operation-result-pattern.md](operation-result-pattern.md)). Identity resolution that performs external I/O returns through that envelope; resolution that is a pure transformation does not.
- Type contracts at module boundaries are vendor-neutral ([type-boundaries.md](type-boundaries.md)); the canonical User type is application-owned, not a re-export of any vendor SDK type.
- Feature handlers receive User as a typed parameter at handler step 1 ([feature-handler-standard.md](feature-handler-standard.md)). Their bodies depend on the type, not on its derivation path.
- Sensitive fields (token bodies, signatures) carried alongside identity are redacted at egress ([data-redaction-policy.md](data-redaction-policy.md)).
- Log records carry the principal's identity through structured-context binding ([logging-observability.md](logging-observability.md), [cross-channel-correlation.md](cross-channel-correlation.md)).

**Non-goals:**

- This record does not redefine the JWT validation contract (issuer allowlist, audience checks, signing algorithms, JWKS rotation). That is owned by [api-security.md](api-security.md).
- This record does not pick the per-platform handler dispatcher mechanics (Slack Bolt, Microsoft 365 Agents SDK). Each platform-transport record owns its own dispatcher.
- This record does not specify *authorization* — what an authenticated user is permitted to do. That is governed by the SecurityScopes mechanism in [api-security.md](api-security.md) and per-feature authorization rules.
- This record does not introduce cross-transport identity deduplication ("the Slack user `alice@example.com` is the same person as the JWT subject `alice@example.com`"). That is a feature-layer concern, not an infrastructure rule.
- This record does not own the storage of credentials, tokens, sessions, or refresh state. Credentials belong with their owning service per [configuration-ownership.md](configuration-ownership.md).

## Considered Options

**Option 1 — Canonical `User` value type, per-transport resolution, no orchestrator.** Define a single Pydantic value type used by every feature. Each inbound transport (HTTP, Slack, webhook, SQS, system) owns the rules that produce a `User` from its own evidence. JWT extraction is a pure helper; Slack resolution is an external-call returning `OperationResult[User]`; webhook actor extraction is inline at the middleware; SQS messages carry `(feature, intent, correlation_id)` and consumers re-establish identity through the originating intent's record; system identity is a constant. No "IdentityService" class; no central resolver.

**Option 2 — Centralized `IdentityService` orchestrator.** A single DI-injected service exposes `resolve_from_jwt`, `resolve_from_slack`, `resolve_from_webhook`, etc. Every transport calls into it. The service is a Protocol; concrete implementations vary by environment.

**Option 3 — Vendor-typed identity at the boundary.** Pass through the platform's user object (Slack `User`, JWT payload dict, etc.) all the way to feature code. Each feature handles each shape.

**Option 4 — Cross-transport identity deduplication at infrastructure.** A central identity store maps every observed transport identity (Slack user_id, JWT sub, webhook actor) to a single global User row, persisted across requests.

## Decision Outcome

**Chosen: Option 1 — canonical `User` value type, per-transport resolution, no orchestrator.**

This is the only option that gives feature code one stable type to depend on without introducing a service that exists only to call one of N independent extraction paths. Centralized orchestration (Option 2) coupled every transport's evolution to a shared Protocol whose only purpose was *not* to share logic. Vendor-typed identity (Option 3) defeats the point of multi-transport substitutability. Cross-transport deduplication at infrastructure (Option 4) imposes a global identity store the application does not need; features that want to correlate users across transports do so inside their own domain, where they have the context to decide what "same person" means.

### The canonical `User` type

`User` is a Pydantic value type defined in `app/infrastructure/security/models.py`. It is the *only* identity type that crosses into feature code.

```python
class AuthPrincipalSource(StrEnum):
    API_JWT = "api_jwt"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SYSTEM = "system"


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str            # canonical identity key — the actor's primary email
    email: str              # primary email (equal to user_id by current convention)
    display_name: str       # human-readable name; "System" for system identity
    source: AuthPrincipalSource
    platform_id: str | None = None     # transport-specific id (Slack user_id, JWT sub) — log/debug only
    permissions: list[str] = []        # source-resolved scopes/roles
    metadata: dict[str, str] = {}      # source-specific context; log-only
```

Rules on the type:

- **Frozen.** A `User` instance is immutable once produced. Code that wants a modified view constructs a new instance.
- **`user_id` is the identity key.** It is the actor's primary email. Cross-cutting concerns (authorization decisions, audit logs, idempotency keys when a user is part of the key) use `user_id`, not `platform_id`.
- **`platform_id` is debug-only.** Feature business logic does not branch on it; it exists for log correlation and operator forensics. A handler that needs the Slack user_id to make a Slack-specific call uses the platform's own context (the handler's transport-bound dispatcher provides it), not `User.platform_id`.
- **`metadata` is debug-only.** Same rule. A handler that wants a metadata field is a code-review signal that the business rule is escaping the canonical type.
- **`permissions` is the resolved set,** not the raw claim string. Source-specific normalization (RFC 6749 space-separated string vs. JSON array; Slack roles vs. scopes) happens at resolution time, not at consumption time.

### Resolution rules — one per transport

#### HTTP with JWT Bearer

The `get_current_user` FastAPI `Security()` dependency ([api-security.md](api-security.md)) is the single seam. Inside it, JWT validation produces a verified payload; a private pure helper transforms the payload to a `User`:

```python
def _user_from_jwt_payload(payload: Mapping[str, Any]) -> User:
    return User(
        user_id=payload["email"],
        email=payload["email"],
        display_name=payload.get("name", payload["email"]),
        source=AuthPrincipalSource.API_JWT,
        platform_id=payload["sub"],
        permissions=_normalize_scopes(payload.get("scope")),
        metadata={"iss": payload["iss"], "aud": payload["aud"]},
    )
```

Rules:

- The transformation is **pure** (no I/O, no DB read, no platform API call). JWT signature verification has already happened upstream (in `get_current_user`); the transformation is a dict-to-object mapping.
- The helper is **private** to `app/infrastructure/security/`. It is not a DI-injected service. It is not a Protocol. There is no `IdentityService`; the function is the contract.
- The helper does not raise. JWT validation owns its own error path (returns 401 problem-details per [api-design-error-mapping.md](api-design-error-mapping.md)). By the time the payload reaches this helper, the JWT is verified.
- `permissions` is normalized from whichever scope-claim format the JWT carried (RFC 6749 space-separated string or RFC 8693 array). Downstream code sees the array form.

#### Slack interactivity

Slack events arrive over the platform's authenticated channel ([transport-slack.md](transport-slack.md)). The Slack inbound payload carries the Slack `user_id`; the canonical `email` is not in the payload and must be fetched from Slack's API. This is a Path-B, platform-bound capability of the Slack platform provider:

```python
class SlackPlatformProvider:
    async def resolve_user(self, user_id: str, team_id: str | None = None) -> OperationResult[User]: ...
```

Rules:

- Resolution returns `OperationResult[User]` because it performs an external API call (`users.info`). The closed five-status envelope is the contract.
- Resolution lives on `SlackPlatformProvider` (Category C of [infrastructure-service-classification.md](infrastructure-service-classification.md)) — a concrete platform provider class, not a shared Protocol. Other platforms have their own resolution method on their own provider.
- The handler's first step is to call `resolve_user`; the second step branches on the envelope. A `permanent_error` (e.g., the Slack profile lacks an email) terminates the handler with a user-facing error. A `transient_error` (Slack API unavailable) is surfaced for retry.
- Resolved `User`s may be cached **within a single request scope** (one resolution call per inbound event) but are **not cached across requests**. A profile change in Slack must be observable on the next interaction.
- `User.platform_id = <Slack user_id>`; `User.metadata = {"team_id": ..., "is_admin": ...}` (debug fields only).

#### Webhook deliveries

Webhook senders (GitHub, AWS EventBridge, etc.) sign their payloads. The signature is verified in middleware (per the upstream's spec); on success, the actor is extracted from the verified payload. There is no resolution chain — each webhook transport owns its own actor extraction inline:

```python
async def github_webhook_middleware(request, call_next):
    payload = await _verify_signature(request)
    actor = User(
        user_id=payload["sender"]["email"],
        email=payload["sender"]["email"],
        display_name=payload["sender"]["login"],
        source=AuthPrincipalSource.WEBHOOK,
        platform_id=str(payload["sender"]["id"]),
        metadata={"webhook_source": "github"},
    )
    request.state.user = actor
    ...
```

Rules:

- No shared resolution service. Each webhook middleware extracts its own actor.
- `source = WEBHOOK` for all of them; `metadata.webhook_source` distinguishes which upstream.
- Signature verification is owned by the middleware; this record does not specify per-platform signing schemes.
- A webhook whose payload does not carry an actor (e.g., an unauthenticated probe) lands `source = WEBHOOK` with a synthetic `user_id = "anonymous@webhook.<source>"` — explicit, not absent.

#### SQS message consumers

A consumer of an SQS message has access to `(feature, intent, correlation_id)` ([handler-idempotency.md](handler-idempotency.md), [message-queuing.md](message-queuing.md)). The originating intent's user — captured at the time the entity was first written — is read from the entity record, not from the message:

```python
async def consume(message: QueueMessage) -> OperationResult[None]:
    entity = await entity_repo.get(message.correlation_id)
    user = entity.requested_by   # User stored at creation
    ...
```

Rules:

- The message itself does not carry a serialized `User`. Identity context lives with the durable entity, not in the queue.
- A consumer that runs without a domain entity (a notification fan-out, an audit job) uses **system identity** (see below).

#### Background jobs and other system actions

Work that has no human principal — scheduled jobs, post-write notifications, reconciliation runs — uses a constant **system identity** constructed inline at the entry point:

```python
SYSTEM_USER = User(
    user_id="system@app",
    email="system@app",
    display_name="System",
    source=AuthPrincipalSource.SYSTEM,
)
```

Rules:

- One module-level constant exposed from `app/infrastructure/security/`. No service, no DI, no per-job re-construction.
- Audit logs distinguish system from human actors via `source = SYSTEM`.
- A handler that mutates state on behalf of a system action attributes the change to the system identity, never silently to "no user."

### Where the User type lives, and how it is exposed

```text
app/infrastructure/security/
    __init__.py           # public surface: User, AuthPrincipalSource, SYSTEM_USER, get_current_user
    models.py             # User and AuthPrincipalSource definitions
    current_user.py       # get_current_user dependency; _user_from_jwt_payload private helper
    jwks.py               # JWKS manager (separate concern; api-security.md owns)
    settings.py           # security settings
```

Feature code imports through one path: `from app.infrastructure.security import User`. The DI dependency alias for the authenticated principal is `CurrentUserDep = Annotated[User, Security(get_current_user)]`, exported from the security module and consumed by route signatures. There is no `app/infrastructure/identity/` package; identity is a property of the security module.

### Logging context binding

Handlers that have an identity to bind do so at handler entry, using `structlog`'s `contextvars` integration ([logging-observability.md](logging-observability.md)):

```python
structlog.contextvars.bind_contextvars(
    user_id=user.user_id,
    auth_source=user.source.value,
)
```

Every log record produced inside the handler's call chain inherits these fields. Binding is opt-in per handler — not every handler binds (a healthcheck has no user); when it binds, the field names are fixed (`user_id`, `auth_source`) so dashboards do not need to handle synonyms.

`User.email` and `User.user_id` (currently the same value: an email) are **not** redacted by [data-redaction-policy.md](data-redaction-policy.md)'s deny list. Email is not a secret in this application's threat model; it is a stable identifier. Sensitive fields (raw JWT tokens, raw signatures) are not on the User type in the first place; they are stripped at the validation seam before the User is constructed.

### What this record does not change

- The JWT validation contract (issuers, audiences, algorithms) remains owned by [api-security.md](api-security.md).
- The Slack platform provider's identity resolution lives on the provider per [transport-slack.md](transport-slack.md); this record names the type it returns and the envelope it returns through, not the resolution mechanics.
- Per-feature authorization (which roles can do what) is feature-layer business logic.
- Cross-transport identity correlation, when a feature wants it, is a feature-layer concern with feature-owned storage.

## Consequences

**Positive:**

- Feature handlers depend on one type. Adding a new transport adds one resolution path; it does not change handler signatures or the type's shape.
- The application has no "identity service" with no consumers. The pure JWT helper is six lines; the Slack resolution is on the provider that owns the Slack API anyway; the webhook actor is at the place that already verifies the webhook signature.
- The `OperationResult[User]` envelope at the Slack boundary composes with the rest of the application's error model; failures are observable, not hidden.
- The User type is value-shaped and immutable; passing one across a boundary or storing one with an entity is safe.

**Tradeoffs accepted:**

- Resolution logic for each transport lives close to that transport rather than in one shared module. Acceptable: the shared module would have been a switch statement keyed on transport, which is not abstraction.
- The application does not detect "the same person on Slack and on HTTP" automatically. Acceptable: the email-as-identity-key convention means features that *want* to detect it can compare `user_id` strings; an infrastructure layer that did this for everyone would be wrong for features that have stricter or looser equivalence rules.
- A future transport that needs identity resolution must add a path here; there is no Protocol that auto-includes new transports. Acceptable: identity is part of the transport's contract, not an afterthought; review at transport introduction is the right gate.

**Risks and mitigations:**

- **A Slack profile lacks an email field** (rare but possible). `resolve_user` returns `permanent_error`; the handler emits a user-facing failure. *Mitigation:* the failure message is actionable ("the Slack workspace must permit email visibility for this app"), not a generic 500.
- **A handler reads `User.platform_id` and branches on it.** This couples business logic to the transport. *Mitigation:* code review forbids `platform_id` consumption in feature code; the field is documented as debug-only on the type.
- **A webhook payload's actor field is missing or unverified.** A user is constructed against attacker-controlled input. *Mitigation:* webhook signature verification gates actor extraction; an unsigned payload reaches no actor extraction code path.
- **JWT scope normalization differs from a feature's expectation** (e.g., feature checks `read:items`, JWT carries `read items`). *Mitigation:* normalization is centralized in `_normalize_scopes`; tests assert it handles both formats.

## Confirmation

Compliance is verified by:

- **Code review.** No `User` type definition outside `app/infrastructure/security/models.py`. No `IdentityService` class. No DI registration of an identity resolver. No `platform_id` consumption in feature business logic.
- **Static analysis.** An import-rule check forbids `from app.infrastructure.identity` (the now-deleted package). A check confirms feature code imports `User` from `app.infrastructure.security`.
- **Tests.** Unit tests assert: JWT helper produces correct `User` for both space-separated and array scope formats. Slack resolver returns `OperationResult.permanent_error()` when the profile lacks an email. The webhook middleware's actor extraction is signature-gated. The system constant has the expected immutable value.
- **Boot test.** No `IdentityService` registration in the DI composition root; route signatures use `CurrentUserDep` consistently across HTTP routes.

## Source References

1. RFC 7519 — JSON Web Token (JWT)
   - URL: <https://www.rfc-editor.org/rfc/rfc7519>
   - Accessed: 2026-05-08
   - Relevance: Defines the JWT claim set (`sub`, `iss`, `aud`, `email`, etc.) consumed by `_user_from_jwt_payload`. Grounds the rule that JWT-to-User is a pure dict-to-object transformation given a verified payload.

2. RFC 6749 — The OAuth 2.0 Authorization Framework, §3.3 "Access Token Scope"
   - URL: <https://www.rfc-editor.org/rfc/rfc6749#section-3.3>
   - Accessed: 2026-05-08
   - Relevance: Defines the space-separated scope-string format. Grounds the `_normalize_scopes` helper's accepting both this form and the JSON array form (which some IdPs emit).

3. Slack Web API — `users.info`
   - URL: <https://api.slack.com/methods/users.info>
   - Accessed: 2026-05-08
   - Relevance: Documents the canonical Slack endpoint used by `SlackPlatformProvider.resolve_user` to obtain the user's email and profile. Grounds the rule that Slack identity resolution is an external call returning `OperationResult[User]`.

4. FastAPI — Security Dependencies and `Security()`
   - URL: <https://fastapi.tiangolo.com/advanced/security/>
   - Accessed: 2026-05-08
   - Relevance: Documents `Security()` as the dependency-injection entry point for authenticated principals and `SecurityScopes` for scope-checked dependencies. Grounds the choice of `get_current_user` as the single seam for HTTP/JWT identity entering feature code.

5. Pydantic — Models
   - URL: <https://docs.pydantic.dev/latest/concepts/models/>
   - Accessed: 2026-05-08
   - Relevance: Documents the `BaseModel` and `model_config = ConfigDict(frozen=True)` posture used to make `User` an immutable value type that can safely cross boundaries and be stored on entities.

6. OWASP API Security Top 10 (2023) — API3:2023 Broken Object Property Level Authorization
   - URL: <https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/>
   - Accessed: 2026-05-08
   - Relevance: Establishes the principle that authorization decisions on object properties must be explicit, not implicit in object shape. Grounds the rule that `User.permissions` is the resolved-and-normalized set, not a passthrough of the JWT scope claim.

7. Python — `enum.StrEnum`
   - URL: <https://docs.python.org/3/library/enum.html#enum.StrEnum>
   - Accessed: 2026-05-08
   - Relevance: Documents `StrEnum` as the canonical pattern for string-valued enums whose values appear in serialized contexts (logs, audit records). Grounds the choice of `AuthPrincipalSource` as a `StrEnum` whose `.value` is the field bound to log context (`auth_source`).

## Change Log

- 2026-05-08: Created. Establishes a single Pydantic value type `User` in `app/infrastructure/security/models.py` as the canonical identity representation across all transports. Specifies per-transport resolution rules: JWT extraction as a pure private helper, Slack resolution on `SlackPlatformProvider` returning `OperationResult[User]`, webhook actor extraction inline at signature-verifying middleware, SQS consumers reading user from the durable entity, system actions using a module-level constant. Names `user_id = email` as the identity key and confines `platform_id` and `metadata` to debug-only consumption. Defines log-context binding via `structlog.contextvars` with stable field names. Defers authorization to api-security.md, transport-specific signature verification to per-transport records, and cross-transport identity correlation to feature-layer concerns.
