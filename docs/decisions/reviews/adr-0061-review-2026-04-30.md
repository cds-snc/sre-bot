# ADR Challenge and Content Review — ADR-0061

**Purpose:** Full challenge review of ADR-0061: Identity and External Integration Contract Standard. Evaluates the complete document (6 standards, compliance, codebase audit, revalidation) for content soundness, assumption correctness, and cross-ADR consistency.

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0061: Identity and External Integration Contract Standard |
| **Reviewer Name & Title** | Architecture Review (AI-assisted), SRE Team |
| **Secondary Reviewers** | — |
| **Review Date** | 2026-04-30 |
| **Revalidation Due** | 2026-08-28 |
| **Gate Outcome** | ✅ **PASS** |
| **Outcome Rationale** | All 6 standards are grounded in codebase evidence, upstream ADR constraints, and authoritative best practices. The ADR correctly consolidates ADR-0023 and ADR-0024 into a single Tier-3 Domain Standard. Codebase audit accurately identifies 4 violations and 3 compliant patterns. No contradictions with upstream ADRs detected. Domain boundary clarification (interaction identity vs. IDP vs. access sync) is accurate and necessary. |

---

## 2. Evidence Gathering & Convention Validation

### 2.A Language & Framework Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| PEP 544 — Protocols: Structural subtyping | Protocol contract pattern for IdentityService | `@runtime_checkable` Protocol enables structural subtyping without inheritance. Standard 3 mandates Protocol creation following this pattern. | ✅ Aligned | — |
| FastAPI Dependency Injection | `Annotated[..., Depends()]` pattern for identity | FastAPI's `Depends()` mechanism combined with `Annotated` type aliases is the standard DI surface. Standard 3 step 4 correctly prescribes this. | ✅ Aligned | — |
| Pydantic V2 BaseModel | User model at I/O boundary | Pydantic BaseModel is appropriate for models that cross HTTP boundaries. Standard 1's `User` model is returned by `get_current_user` and serialized in audit logs. | ✅ Aligned | — |
| Pydantic BaseSettings | IdentitySettings extraction | BaseSettings with `@lru_cache` singleton is the canonical settings pattern. Standard 4 follows ADR-0055/0056. | ✅ Aligned | — |

### 2.B Infrastructure & Operational Standards

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| OWASP Authentication Cheat Sheet | Canonical identity model guidance | OWASP recommends normalized user representation with source tracking across authentication mechanisms. Standard 1's `User` model with `source` enum aligns. | ✅ Aligned | — |
| RFC 7519 — JWT | JWT claims extraction for identity resolution | RFC 7519 defines `sub`, `email`, `name` as standard claims. Standard 2 source priority correctly places JWT highest. | ✅ Aligned | — |
| Twelve-Factor Factor III — Config | Credential lifecycle binding | Credentials must be environment configuration, not runtime-fetched. Standard 6 correctly mandates release-phase binding with documented JWKS exception. | ✅ Aligned | — |
| ADR-0045 P7 — Managed Service Delegation | Delegation tier for IdentityService | P7 mandates highest applicable tier. IdentityService delegates to managed APIs (JWT/JWKS, Slack). Tier 1 classification is correct. | ✅ Aligned | — |
| ADR-0077 Standard 1 — Category A | IdentityService classification | Category A P1 priority confirmed. Protocol contract required. Delegation tier declaration required. | ✅ Aligned | — |
| ADR-0050 — OperationResult | External lookup return types | All external lookups must return `OperationResult`. Standard 3 correctly mandates `OperationResult[User]` for external methods. | ✅ Aligned | — |
| ADR-0055 Standard 1 — Independent singleton | IdentitySettings extraction | Each infrastructure concern must have its own BaseSettings class. Standard 4 correctly mandates `IdentitySettings`. | ✅ Aligned | — |
| ADR-0056 Standard 1 — Narrow-slice injection | Constructor injection | Services receive narrowest settings slice. Standard 4 correctly prohibits full `Settings` aggregator. | ✅ Aligned | — |

### 2.C Cross-Cutting Design Patterns

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Hexagonal Architecture — Ports and Adapters | IdentityServiceProtocol as port | Protocol is the port; concrete IdentityService is the adapter. Standard 3 follows this pattern. DirectoryProvider is the reference implementation. | ✅ Aligned | — |
| Clean Architecture — Dependency Inversion | Feature code → Protocol, not concrete | Standard 5 Rule correctly mandates features consume Category A via injection boundary. Codebase confirms feature packages import `User` only, not `IdentityService`. | ✅ Aligned | — |

### 2.D Validation Summary

**Total Standards Checked:** 12
**Aligned with Best Practice:** 12
**Deliberate Deviations:** 0

**High-Level Finding:** 🟢 **Fully Grounded** — All standards checked; no unresolved deviations.

---

## 3. Assumptions Challenged

### Assumption 3.1: Consolidating ADR-0023 and ADR-0024 is the correct decomposition

- **Stated Norm:** "Consolidate ADR-0023 and ADR-0024 into a Tier-3 Domain Standard."
- **Underlying Assumption:** The domain-specific rules in both legacy ADRs belong together, and the cross-cutting rules from ADR-0024 are already codified elsewhere.
- **Challenge:** Could the two domains be different enough to warrant separate ADRs?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — ADR-0024's client facade, provider, DI alias, and OperationResult patterns are fully codified in ADR-0050, ADR-0055, ADR-0056, ADR-0077. Only ADR-0023's identity-specific content (canonical User model, multi-source resolution) remains domain-specific. External integration client classification is a natural extension of identity service classification.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The Alternatives section (Option 2) explicitly considers three-ADR split and rejects it with sound rationale.

### Assumption 3.2: Email as user_id is appropriate

- **Stated Norm:** Standard 1 defines `user_id` as "the user's primary email address."
- **Underlying Assumption:** Single-tenant internal tooling context makes email a stable unique identifier.
- **Challenge:** Email addresses can change; opaque IDs are more stable for multi-tenant or public-facing services.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — The ADR explicitly acknowledges this as an intentional deviation in Revalidation: "would need revision for a multi-tenant or public-facing service." The current deployment context (single-tenant, internal SRE tooling) validates email as user_id.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The deviation is documented and scoped. Acceptable for current context.

### Assumption 3.3: IdentityService is correctly classified as Tier 1

- **Stated Norm:** "IdentityService is classified as Tier 1 (managed service wrappers)."
- **Underlying Assumption:** The orchestration logic (multi-source resolution, conflict handling) is proportional glue, not a separate infrastructure concern requiring Tier 3 classification.
- **Challenge:** Could the resolution orchestration constitute custom infrastructure?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Codebase verification confirms: `service.py` is a thin facade delegating to `resolver.py`, which dispatches to managed API backends (Slack API, JWT/JWKS endpoints, webhook payloads). The resolution logic is routing/coordination — it does not implement identity provider functionality.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Delegation tier amendment review (PASS) already validated this classification.

### Assumption 3.4: Single-source resolution (no fallthrough) is correct

- **Stated Norm:** Standard 2 Rule 2: "Do not fall through to secondary sources. Each request context has exactly one expected identity source."
- **Underlying Assumption:** Each request type has a deterministic, known identity source. Fallthrough creates ambiguity.
- **Challenge:** Could a legitimate scenario require fallthrough (e.g., JWT missing but Slack context available)?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Codebase confirms each endpoint has exactly one identity mechanism: API routes use JWT via `get_current_user`, Slack handlers use `resolve_from_slack`, webhook endpoints use `resolve_from_webhook`. No endpoint mixes sources. Fallthrough would indicate a misconfigured endpoint, not a valid identity resolution strategy.
- **Confidence (ADR survives challenge):** 🟢 High

### Assumption 3.5: JWKS runtime refresh is not an ADR-0052 violation

- **Stated Norm:** Standard 6 Rule 2: "JWKS endpoints are the exception — they are runtime-refreshed because key rotation is an inherent part of the OIDC protocol."
- **Underlying Assumption:** The JWKS endpoint URL is release-phase bound; only key material is runtime-refreshed.
- **Challenge:** Could this create a precedent for other services to claim runtime-refresh exceptions?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — JWKS key rotation is inherent to the OIDC/OAuth2 protocol (RFC 7517). The `PyJWKClient` in `jwks.py` takes the endpoint URL at construction time (release-phase bound) and caches/refreshes keys transparently. This is materially different from fetching credentials from a secret store at runtime.
- **Confidence (ADR survives challenge):** 🟢 High

### Assumption 3.6: Domain boundary (interaction identity vs. IDP vs. access sync) is correctly drawn

- **Stated Norm:** Standard 3 domain boundary clarification separates IdentityService (interaction identity), DirectoryProvider (IDP), and access package (sync).
- **Underlying Assumption:** These three concerns have distinct governance, distinct Protocol contracts, and distinct evolution paths.
- **Challenge:** Could future requirements blur these boundaries?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Codebase confirms:
  - `IdentityService` in `app/infrastructure/identity/` resolves *who is calling* from HTTP/Slack/webhook contexts
  - `DirectoryProvider` Protocol in `app/infrastructure/directory/` queries the IDP (Google Workspace) for user/group data
  - Access sync in `app/packages/access/` pushes identities from IDP → targets (AWS Identity Store, GitHub)
  - These are three distinct code locations with distinct consumers and distinct evolution triggers (e.g., switching IDP doesn't affect IdentityService)
- **Confidence (ADR survives challenge):** 🟢 High

---

## 4. Failure Modes Identified

### Failure Mode 4.1: Protocol migration surfaces interface inconsistencies

- **If Assumption Fails:** The `IdentityServiceProtocol` methods may not cleanly match the current concrete `IdentityService` interface (e.g., `resolver` property exposure, constructor dependencies).
- **Platform Impact:**
  - Incident management workflow: None
  - Access synchronization workflow: None
  - Access request workflow: None
  - Multi-provider integrations: Low (temporary type errors during migration)
- **Probability Estimate:** Low — the concrete class has a clean public interface (4 resolve methods)
- **Mitigation or Acceptance:** ADR-0077 Standard 5 defines independently deployable migration steps. Standard 3 prescribes the exact sequence: create Protocol → rename implementation → update provider → update DI alias → verify with mypy.

### Failure Mode 4.2: IdentitySettings extraction scope unclear

- **If Assumption Fails:** It's unclear which settings belong in `IdentitySettings` vs. existing settings partitions (e.g., `server.ISSUER_CONFIG` is JWKS-related but lives in ServerSettings).
- **Platform Impact:**
  - Incident management workflow: None
  - Access synchronization workflow: None
  - Access request workflow: None
  - Multi-provider integrations: None
- **Probability Estimate:** Low — Standard 4 provides clear guidance ("Only the settings consumed by identity resolution")
- **Mitigation or Acceptance:** Standard 4 defers provider-specific settings to their own partitions (ADR-0055 Standard 3). The boundary question is which settings move from `ServerSettings` to `IdentitySettings` — this is a dissolution implementation detail, not an architectural ambiguity.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| None identified | — | — | — |

All upstream constraint references verified:

- ADR-0045 P6 (Protocol contracts): ✅ Standard 3 implements
- ADR-0048 B2 (single injection surface): ✅ Standard 3 step 4 implements
- ADR-0048 B7 (Protocol contract surface): ✅ Standard 5 Rule implements
- ADR-0050 S1 (OperationResult): ✅ Standard 3 mandates
- ADR-0052 (build-release-run): ✅ Standard 6 implements
- ADR-0054 (structured logging): ✅ Standard 2 Rule 2 references
- ADR-0055 S1 (independent singleton): ✅ Standard 4 implements
- ADR-0056 S1 (narrow-slice injection): ✅ Standard 4 implements
- ADR-0076 S2 (configuration via injection): ✅ Standard 4 implements
- ADR-0077 S1 (service classification): ✅ Standard 5 implements

### Supersession Ambiguities

- **ADRs this one supersedes:** ADR-0023 (Identity Resolution), ADR-0024 (External Service Integration)
- **Inheritance Status:** ✅ All inherited concerns acknowledged. ADR-0023's canonical User model → Standard 1. ADR-0023's multi-source resolution → Standard 2. ADR-0024's client facade patterns → deferred to upstream Tier-2 standards. ADR-0024's OperationResult mandate → deferred to ADR-0050.
- **Gaps Identified:** None

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Secondary Domain Owners:** None
- **Plugin/Startup Registration:** Identity service initialization in lifespan startup (ADR-0046 Phase 2). JWKS warmup in security initialization.
- **Config Owner:** `IdentitySettings` (target state); currently embedded in root `Settings`
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation Matrix

### Scenario 6.1: API Request (JWT Authentication)

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Identity resolution | Standard 2: JWT is highest priority source | `get_current_user()` validates JWT via JWKS, calls `resolve_from_jwt()` | ✅ No | Single-source, no fallthrough |
| Return type | Standard 3: `OperationResult[User]` for external lookups | JWT parsing is local computation (no external call); JWKS key fetch is cached | ✅ No | Local computation may return directly per Standard 3 |
| Credential binding | Standard 6: JWKS endpoint URL is release-phase | `PyJWKClient` receives URL at construction; keys runtime-refreshed | ✅ No | JWKS exception documented and justified |

**Validation Summary:** ✅ Fully aligned

### Scenario 6.2: Slack Command Handler

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Identity resolution | Standard 2: Platform-specific (Slack user ID) | `resolve_from_slack()` calls Slack `users_info` API | ✅ No | Managed API delegation (Tier 1) |
| User model | Standard 1: Returns `User` (base type) | `resolve_from_slack()` returns `SlackUser` internally but typed as `User` at Protocol boundary | ✅ No | Feature code sees `User` only |
| Failure handling | Standard 2 Rule 2: `IDENTITY_RESOLUTION_FAILED` on failure | Slack API errors return failure result | ✅ No | No fallthrough to JWT or other source |

**Validation Summary:** ✅ Fully aligned

### Scenario 6.3: Webhook Processing

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Identity resolution | Standard 2: Webhook payload identity | `resolve_from_webhook()` extracts identity from signed payload | ✅ No | Webhook source is managed service |
| Conflict handling | Standard 2 Rule 3: Single identity per request | Each webhook has one identity source embedded in payload | ✅ No | No multi-source conflict possible |

**Validation Summary:** ✅ Fully aligned

### Scenario 6.4: Background Job (System Identity)

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Identity resolution | Standard 2: System identity for background jobs | `resolve_system_identity()` returns synthetic system user | ✅ No | No external call needed |
| Audit trail | Standard 1: `source: SYSTEM` in User model | `IdentitySource.SYSTEM` enum value correctly identifies synthetic users | ✅ No | Audit logs distinguish system vs. human actions |

**Validation Summary:** ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Pydantic BaseModel for User (heavier than dataclass)

- **Chosen:** Pydantic `BaseModel` for `User`
- **Rejected:** `@dataclass(frozen=True)` (lighter, internal-only type)
- **Rationale:** `User` crosses the HTTP boundary via `get_current_user` dependency and is serialized in audit events. I/O boundary types use Pydantic per ADR-0040.
- **Risk Accepted:** Slightly heavier serialization overhead for internal use cases where User doesn't cross HTTP boundary.
- **Contingency:** If performance-critical internal paths emerge, a `@dataclass(frozen=True)` `InternalUser` can be introduced as a separate internal type.

### Tradeoff 7.2: Single Tier-3 ADR vs. separate domain ADRs

- **Chosen:** Consolidate identity + external integration into one ADR
- **Rejected:** Three separate ADRs (identity, integration client pattern, credential management)
- **Rationale:** Integration client pattern is already ADR-0056 + ADR-0077. Credential management is a subset of ADR-0052 + ADR-0055. Only identity resolution has enough domain-specific content.
- **Risk Accepted:** Slightly broad scope for a single Tier-3 record.
- **Contingency:** If the external integration client classification table grows significantly, it can be extracted to a separate ADR.

### Tradeoff 7.3: SlackUser inheritance vs. composition

- **Chosen:** `SlackUser(User)` — inheritance subclass
- **Rejected:** Composition (separate `SlackContext` alongside `User`)
- **Rationale:** Category C implementation detail confined to infrastructure. Feature code never sees `SlackUser`.
- **Risk Accepted:** Inheritance coupling at the infrastructure level.
- **Contingency:** If platform-specific extensions proliferate, refactor to composition pattern.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Create `IdentityServiceProtocol` | ❌ No | SRE Team | After acceptance | Standard 3 P1 migration. Define Protocol in `app/infrastructure/identity/protocol.py`. |
| Extract `IdentitySettings` | ❌ No | SRE Team | After ADR-0055 Phase 1 | Standard 4. Partition settings from root `Settings` aggregator. |
| Update `IdentityServiceDep` alias | ❌ No | SRE Team | After Protocol creation | Standard 3 step 4. `Annotated[IdentityServiceProtocol, Depends(...)]`. |
| Mark ADR-0023, ADR-0024 Superseded | ❌ No | SRE Team | Wave 4 gate | Move to `adr/superseded/` with `superseded_by: [ADR-0061]`. |
| Audit `SlackUser` feature imports | ❌ No | SRE Team | P2 | Standard 1 — verify no feature-level `SlackUser` imports. Current audit: clean. |

**No blocking actions.** All follow-ups are post-acceptance implementation items.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

✅ **PASS** → ADR-0061 is professionally sound and ready for acceptance.

**Summary:**

- 6 standards grounded in 12 authoritative sources with zero deviations
- 6 assumptions challenged, all at 🟢 High confidence
- 2 failure modes identified, both Low probability with documented mitigations
- Zero cross-ADR contradictions
- 4 workflow scenarios validated, all fully aligned
- Codebase audit accurately identifies current violations and compliant patterns
- Domain boundary clarification (interaction identity / IDP / access sync) is evidence-backed

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | Architecture Review (AI-assisted) |
| **Reviewer Title** | SRE Architecture Review |
| **Organization/Team** | SRE Team |
| **Sign-Off Date** | 2026-04-30 |
