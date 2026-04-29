# ADR Challenge and Content Review — ADR-0059

**Purpose:** Step 9.5 (Canonical ADR Challenge and Content Review Gate) execution for ADR-0059: Feature Interaction Boundaries and Platform Integration Standard. This review anchors all judgments on authoritative best practices, not current code implementation.

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0059: Feature Interaction Boundaries and Platform Integration Standard |
| **Reviewer Name & Title** | AI Architecture Reviewer, SRE Team |
| **Secondary Reviewers** | — |
| **Review Date** | 2026-04-29 |
| **Revalidation Due** | 2027-04-29 |
| **Gate Outcome** | ⚪ **REVISE** |
| **Outcome Rationale** | The document is internally contradictory: three of six standards (1-3) are rejected by the 2026-04-29 Platform Services Assessment, yet remain in the body alongside kept standards (4-6). ADR-0078, the primary delegation target for platform service governance, does not exist as a file in the repository — creating a dangling reference in the supersession chain. Standard 6 hookspec examples use rejected types (`InteractionProvider`) and names (`register_slack_interactions`) that diverge from the actual codebase (`SlackPlatformProvider`, `register_slack_commands`). The kept standards (4-5) are architecturally sound and validated by the existing `app/packages/access/sync/interactions/` implementation, but the document cannot pass the gate in its current form. |

---

## 2. Evidence Gathering & Convention Validation

### 2.A Language & Framework Standards

**Applicable Standards:**

- ✅ FastAPI Official Documentation (<https://fastapi.tiangolo.com/>)
- ✅ Pluggy Documentation & Best Practices (<https://pluggy.readthedocs.io/>)
- ✅ Python Typing Module Official Docs
- ✅ Pydantic V2 Documentation (<https://pydantic.dev/docs/validation/latest/get-started/>)

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| FastAPI — Bigger Applications (APIRouter) | "APIRouter include_router sub-applications prefix tags" | FastAPI's `APIRouter` is the canonical mechanism for modular route organization. Routers can be included with custom prefix, tags, dependencies, and responses. The `include_router()` call is composable and non-isolating — routes are cloned into the main app. | ✅ Aligned — Standard 5 `interactions/http.py` uses `APIRouter` for feature-owned route organization | N/A |
| FastAPI — Dependency Injection | "Depends Annotated testing dependency overrides" | FastAPI `Depends()` with `Annotated` type aliases is the framework-native DI mechanism. `app.dependency_overrides` enables test-time substitution. Service dependencies should be resolved through provider functions, not direct imports. | ✅ Aligned — Standard 4 HTTP-first pattern uses DI for service injection into route handlers | N/A |
| Pluggy — Hookspec Registration | "hookspec hookimpl PluginManager register" | Pluggy hookspecs define call signatures; hookimpls provide implementations. Multiple plugins can implement the same hookspec. Registration is explicit via `pm.register()`. Hookimpls can accept fewer arguments than the hookspec (opt-in arguments). The `self` argument is ignored during matching. | ✅ Aligned — Standard 6 uses per-platform hookspecs for interaction registration | N/A |
| Pluggy — Hookspec Naming | "hookspec name matching specname" | Hookspec and hookimpl are matched by function name by default. The `specname` option allows overriding the default name matching. Pluggy validates that hookimpl argument names are a subset of the hookspec's arguments. | ⚠️ Deviation — Standard 6 example uses `register_slack_interactions` but the codebase uses `register_slack_commands`. The ADR should document the actual hookspec names. | ADR body not yet revised to match codebase reality. Deviation is editorial, not architectural. |
| Pydantic V2 — BaseModel at I/O Boundaries | "BaseModel validation HTTP request response" | Pydantic `BaseModel` is designed for data validation at untrusted I/O boundaries (HTTP, webhooks, external payloads). Internal models should use plain dataclasses or similar lightweight types. | ✅ Aligned — Standard 5 correctly places `schemas.py` (Pydantic) at I/O boundaries and `domain.py` (frozen dataclasses) for internal entities | N/A |

---

### 2.B Infrastructure & Operational Standards

**Applicable Standards:**

- ✅ Twelve-Factor App Methodology (<https://12factor.net/>)
- ✅ External Provider Specs — Slack Bolt Python (<https://tools.slack.dev/bolt-python/>)
- ✅ External Provider Specs — Microsoft Teams Bot Framework (<https://learn.microsoft.com/en-us/microsoftteams/platform/bots/bot-basics>)

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Twelve-Factor — Factor IV (Backing Services) | "backing services attached resources substitutable" | "The code for a twelve-factor app makes no distinction between local and third party services. To the app, both are attached resources, accessed via a URL or other locator/credentials stored in the config." Resources should be swappable without code changes. | ✅ Aligned — Standard 4 HTTP-first bridge pattern makes business logic channel-agnostic; platform-specific formatting is isolated in presenters and interaction handlers | N/A |
| Slack Bolt Python — Commands/Actions/Views | "Slack Bolt commands actions views ack pattern middleware" | Slack Bolt requires an explicit `ack()` call within 3 seconds of receiving an interaction. Commands, actions, and view submissions each have distinct handler signatures and response patterns. The `ack()` pattern is unique to Slack's interaction model. | ✅ Aligned — Standard 6's rationale for per-platform hookspecs (not unified) is directly validated. Slack's `ack()` pattern is fundamentally different from Teams' turn context. A unified hookspec would force abstraction leaks. | N/A |
| Microsoft Teams Bot Framework — Activity Handlers | "TeamsActivityHandler turn context OnMessageActivityAsync" | Teams bots use a `TeamsActivityHandler` class with `ITurnContext` passed to each handler. The turn context carries conversation state, activity data, and response methods. Handler signatures are fundamentally different from Slack's functional middleware + `ack()` model. | ✅ Aligned — Validates the per-platform hookspec approach. Slack handlers receive `ack, say, command` parameters; Teams handlers receive `ITurnContext<T>`. A single unified hook would create a leaky abstraction. | N/A |

---

### 2.C Cross-Cutting Design Patterns

**Applicable Standards:**

- ✅ Hexagonal Architecture / Ports and Adapters (Cockburn)
- ✅ Dependency Injection — Constructor Injection
- ✅ Anti-Corruption Layer Pattern

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Hexagonal Architecture (Cockburn) | "ports adapters application core channel-agnostic" | Application core depends on port interfaces (service contracts), not adapter implementations (platform-specific handlers). Adapters translate between external protocols and internal domain operations. Multiple adapters (Slack, Teams, HTTP) can drive the same application core. | ✅ Aligned — Standard 4's HTTP-first bridge pattern is a textbook hexagonal architecture: `interactions/http.py`, `interactions/slack.py`, and `interactions/teams.py` are driving adapters; `service.py` is the application core. Rule B1 ("service.py must never import from interactions/") enforces the dependency direction. | N/A |
| Anti-Corruption Layer Pattern | "anti-corruption layer adapter boundary external system" | When integrating with external systems whose models differ from the internal domain, an anti-corruption layer translates between external and internal representations. This prevents external model pollution. | ✅ Aligned — Standard 5's `presenters.py` and `interactions/` directory act as anti-corruption layers: external platform formats (Block Kit, Adaptive Cards) are kept out of the service layer. `ingress.py` translates inbound platform payloads into domain-neutral invocations. | N/A |
| Dependency Injection — Narrow-Slice Pattern | "constructor injection narrowest dependency slice" | Services should receive only the dependencies they need, not broad dependency containers. This reduces coupling and improves testability. | ✅ Aligned — Standard 4 mandates direct service invocation from handlers (not internal HTTP calls), allowing precise dependency injection at the handler level | N/A |

---

### 2.D Validation Summary

**Total Standards Checked:** 11
**Aligned with Best Practice:** 10
**Deliberate Deviations:** 1 (editorial: hookspec naming mismatch between ADR example and codebase)

**High-Level Finding:**

- 🟡 **Mostly Grounded:** Most standards checked; one editorial deviation requires revision. The architectural patterns (Standards 4-6) are well-grounded. The rejected standards (1-3) are correctly identified as rejected but remain in the document body, creating confusion.

**Deviation Summary:**

- Standard 6 hookspec example names (`register_slack_interactions`, `register_teams_interactions`) do not match the actual codebase (`register_slack_commands`, `register_teams_commands`). The ADR must be revised to use the actual names and concrete parameter types (`SlackPlatformProvider`, `TeamsPlatformProvider`). The deviation is editorial (the ADR body was never updated after the scope revision), not architectural.

---

## 3. Assumptions Challenged

### Assumption 3.1: Per-platform hookspecs are preferable to a unified interaction hook

- **Stated Norm:** "Per-platform hooks are preferred over a single unified hook because platform handler signatures differ in their acknowledgment and response semantics (e.g., Slack `ack()` pattern vs. Teams turn context)." (Standard 6)
- **Underlying Assumption:** Slack and Teams platform semantics are sufficiently different that a unified hookspec would create a leaky abstraction forcing `if platform == "slack"` branches inside handlers.
- **Challenge:** Could a unified hookspec with a sufficiently abstract parameter type (e.g., a `PlatformContext` object) encapsulate these differences? The rejected Standard 1 (`InteractionProvider` Protocol) attempted exactly this.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Slack Bolt requires an explicit `ack()` call within 3 seconds and uses functional middleware (command, say, ack). Teams Bot Framework uses `TeamsActivityHandler` class inheritance with `ITurnContext<T>` carrying conversation state. Discord uses event-based handlers with different acknowledgment semantics. These are genuinely different paradigms, not surface-level API differences. A unified `PlatformContext` would need to expose `ack()`, `turn_context`, and event objects simultaneously — the exact abstraction leak the ADR warns about. The Platform Services Assessment's rejection of Standards 1-3 validates this finding empirically.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The codebase implementation confirms this: `app/infrastructure/hookspecs/features.py` defines separate `register_slack_commands(provider: SlackPlatformProvider)`, `register_teams_commands(provider: TeamsPlatformProvider)`, and `register_discord_commands(provider: DiscordPlatformProvider)` with concrete types. This is the correct pattern.

### Assumption 3.2: HTTP is the correct primary test surface for multi-platform features

- **Stated Norm:** "HTTP-first Bridge Pattern: Business logic is exposed through FastAPI HTTP endpoints (`interactions/http.py`) as the primary testable interface." (Standard 4)
- **Underlying Assumption:** If a feature works via HTTP, it works on all platforms — because all transport paths share the same service invocation through `ingress.py`.
- **Challenge:** Could there be platform-specific failure modes that HTTP tests cannot catch? For example, Slack Block Kit rendering issues, Teams Adaptive Card formatting errors, or platform-specific payload sizes that only manifest through platform-specific handlers.
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial — HTTP tests validate the service logic path (ingress → service → domain result), but they do not validate: (1) presenter output correctness (Block Kit JSON structure, Adaptive Card schema), (2) platform-specific admission logic (Slack signature verification, Teams token validation), (3) platform handler error mapping (Slack `ack()` failure vs. Teams `500` response). However, Standard 4 explicitly states HTTP is the *primary* surface, not the *only* surface: "platform-specific handler tests are supplementary." The architecture correctly separates testable concerns.
- **Confidence (ADR survives challenge):** 🟡 Moderate
- **Reviewer Notes:** The claim is sound but could be strengthened. The ADR should explicitly state that presenter unit tests and platform handler integration tests are expected complements to HTTP route tests. The existing `app/packages/access/sync/interactions/` implementation demonstrates this: `http.py` routes are the primary test surface, but `slack.py` handlers should also have dedicated tests for Block Kit response formatting and `ack()` behavior.

### Assumption 3.3: Feature-side `ingress.py` is the correct location for shared admission logic

- **Stated Norm:** "`ingress.py` contains shared admission logic (feature-enable checks, concurrency guards)." (Standard 5, Rule B3)
- **Underlying Assumption:** Admission logic (feature-gate checks, lock checks, duplicate detection) is feature-specific and belongs in the feature package, not in infrastructure.
- **Challenge:** Could admission patterns (feature-enable checks, concurrency guards) be infrastructure-level concerns that should be provided as reusable middleware or decorators rather than reimplemented in each feature's `ingress.py`?
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial — The `app/packages/access/sync/interactions/ingress.py` implementation shows feature-specific admission: `enqueue_user_sync()` checks sync-specific locks and feature-specific enabled flags. These are not generic "is the feature enabled?" checks — they involve domain-specific state (sync run locks, platform-specific sync configurations). However, the pattern of checking a feature-enabled flag *is* generic and could be shared. The risk is that each feature reimplements similar boilerplate in `ingress.py`.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The ADR's approach is correct. Admission logic is feature-specific because it involves domain state, not just boolean flags. A generic decorator would need to know about each feature's lock semantics, sync states, and preconditions — creating inappropriate coupling. Feature packages own their admission logic; infrastructure provides the primitives (lock service, feature flags) that admission logic uses.

### Assumption 3.4: ADR-0059 correctly supersedes ADR-0018 (Service Wrapper Pattern)

- **Stated Norm:** "ADR-0018 (Service Wrapper Pattern): service wrapper DI guidance is superseded by ADR-0056 + ADR-0077 Protocol contracts. Feature-side interaction patterns are superseded by Standard 4 and Standard 5 here." (Consequences section)
- **Underlying Assumption:** ADR-0059 owns the supersession of ADR-0018, and the feature-side interaction subset is sufficient to justify supersession.
- **Challenge:** ADR-0018 covers general service wrapper DI patterns, not just interaction patterns. The ADR's own text acknowledges that the *DI guidance* portion is superseded by ADR-0056 + ADR-0077, not by ADR-0059. If ADR-0059 only supersedes the interaction-related subset, ADR-0018 is not fully superseded and should remain active with narrowed scope.
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial — ADR-0018's `superseded_by` field is currently an empty array (`[]`), meaning the supersession has not been applied. If ADR-0056 + ADR-0077 together cover the DI ceremony, and ADR-0059 covers the feature-side interaction patterns, the three records jointly supersede ADR-0018. However, placing ADR-0018 in ADR-0059's `supersedes` list implies ADR-0059 alone supersedes it, which is incomplete.
- **Confidence (ADR survives challenge):** 🔴 Low
- **Reviewer Notes:** The supersession of ADR-0018 should either be: (a) moved entirely to ADR-0056/ADR-0077 if they jointly cover all of ADR-0018's scope, or (b) split explicitly — ADR-0059 supersedes the interaction-specific subset, and ADR-0056/ADR-0077 supersede the DI ceremony subset. The current `supersedes: [ADR-0018]` in ADR-0059 is inaccurate. ADR-0018's `superseded_by` has not been updated either, creating a one-sided supersession claim.

### Assumption 3.5: The document is reviewable for acceptance in its current form

- **Stated Norm:** The scope revision notice states: "Standards 1-3 below are REJECTED and will be removed in the revision. Standards 4-6 are kept with modifications. Until the revision is complete, use the 2026-04-29 Platform Services Assessment findings and ADR-0078 as the authoritative position."
- **Underlying Assumption:** Readers can correctly distinguish rejected content from kept content by reading the revision notices.
- **Challenge:** The document contains three rejected standards interleaved with three kept standards. The "Principles Established" section (under Standard 6) opens with "One Protocol, multiple providers: `InteractionProvider` is the single abstraction" — directly contradicting the revision notice. The Compliance and Implementation Guidance sections are marked as stale. A reader who skips the revision notice (at the top of a 400-line document) will implement rejected patterns.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** Yes — The document is internally contradictory. The Principles Established section, Compliance section, and Implementation Guidance section all reference rejected concepts without revision marks. This is not a minor editorial issue — it creates a genuine risk of implementing rejected architecture.
- **Confidence (ADR survives challenge):** 🔴 Low
- **Reviewer Notes:** The document cannot pass the gate in this state. A full body revision is required: remove Standards 1-3 entirely, rewrite Standard 6 with actual hookspec definitions, update Principles Established, and rewrite Compliance and Implementation Guidance to reference only kept standards and concrete platform types.

---

## 4. Failure Modes Identified

### Failure Mode 4.1: Implementing rejected InteractionProvider Protocol from stale ADR text (from Assumption 3.5)

- **If Assumption Fails:** A developer reads the ADR without noting the scope revision notice and implements the rejected InteractionProvider Protocol (Standard 1) or PlatformService facade (Standard 3). This creates infrastructure that must be immediately discarded.
- **Platform Impact:**
  - Incident management workflow: None — no direct impact
  - Access synchronization workflow: Low — wasted effort if sync interaction handlers are built against rejected Protocol
  - Access request workflow: Low — same
  - Multi-provider integrations (Slack, Teams, GWS, AWS, GitHub): Medium — incorrect abstraction layer would need to be unwound
- **Probability Estimate:** Medium (25-35%) — the rejected standards are still prominently displayed in the document
- **Mitigation or Acceptance:** Requires revision. Remove rejected standards from the document body before acceptance. The revision notice is insufficient — developers read code examples, not revision notices.

### Failure Mode 4.2: Missing ADR-0078 blocks commands infrastructure retirement (from Assumption 3.5)

- **If Assumption Fails:** ADR-0059 delegates platform service construction governance to ADR-0078, but ADR-0078 does not exist. ADR-0071 (Commands Settings Retirement, target: 2026-09-30) depends on ADR-0059/0078 for the successor architecture. Without ADR-0078, the commands retirement timeline is at risk.
- **Platform Impact:**
  - Incident management workflow: Low — commands infrastructure is functional
  - Access synchronization workflow: Low — sync uses new hookspec pattern already
  - Access request workflow: Low — request uses new hookspec pattern
  - Multi-provider integrations (Slack, Teams, GWS, AWS, GitHub): Medium — legacy commands infrastructure remains as technical debt blocking cleanup
- **Probability Estimate:** High (60-70%) — ADR-0078 is referenced in multiple records but does not exist
- **Mitigation or Acceptance:** Blocker. ADR-0078 must be authored before or concurrently with ADR-0059 revision. The two records form a mandatory pair: ADR-0059 covers feature-side interaction boundaries, ADR-0078 covers platform service construction governance.

### Failure Mode 4.3: Presenter testing gap causes platform-specific formatting errors (from Assumption 3.2)

- **If Assumption Fails:** HTTP-first testing validates service logic but not presenter output. A Block Kit schema change in Slack API or Adaptive Card schema change in Teams API breaks presentation without any test catching it.
- **Platform Impact:**
  - Incident management workflow: Medium — incident commands display broken formatting to responders
  - Access synchronization workflow: Low — sync status messages may render incorrectly
  - Access request workflow: Medium — approval messages may display incorrectly
  - Multi-provider integrations (Slack, Teams, GWS, AWS, GitHub): Medium — platform-specific rendering breaks are invisible to HTTP tests
- **Probability Estimate:** Medium (20-30%) — platform SDK schema changes are infrequent but impactful
- **Mitigation or Acceptance:** Mitigated. The ADR correctly identifies HTTP as the *primary* surface, with platform-specific tests as supplements. The revision should explicitly recommend presenter unit tests for Block Kit / Adaptive Card output validation. This is a test strategy gap, not an architectural flaw.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| ADR-0059 delegates platform services governance to ADR-0078, but ADR-0078 does not exist. The supersession chain has a dangling reference: ADR-0025 `superseded_by: [ADR-0078]`, yet no ADR-0078 file exists in the repository. | ADR-0059, ADR-0078, ADR-0025 | 🔴 High | ⚪ Unresolved — ADR-0078 must be authored |
| ADR-0059 `supersedes: [ADR-0018, ADR-0028]`, but the Consequences section says ADR-0018's DI guidance is superseded by ADR-0056 + ADR-0077, not by ADR-0059. ADR-0059 only supersedes the interaction-specific subset of ADR-0018. | ADR-0059, ADR-0018, ADR-0056, ADR-0077 | 🟡 Medium | ⚪ Unresolved — Clarify supersession ownership |
| ADR-0059 Standard 6 example shows `register_slack_interactions(self, provider: InteractionProvider)` but the actual hookspec in `app/infrastructure/hookspecs/features.py` defines `register_slack_commands(provider: SlackPlatformProvider)`. Different names, different types, different parameter styles. | ADR-0059, Codebase | 🔴 High | ⚪ Unresolved — ADR-0059 Standard 6 must be rewritten from codebase reality |
| ADR-0059 scope revision notice says platform services are Category C (ADR-0077), but the ADR-0077 challenge review (2026-04-29) confirmed `PlatformService` as Category A (P2 migration priority). The classification may have been revised post-assessment; the relationship needs explicit reconciliation. | ADR-0059, ADR-0077 | 🟡 Medium | ⚪ Unresolved — Clarify whether PlatformService is Category A (ADR-0077 Standard 1) or Category C (ADR-0059 scope revision). ADR-0078 should resolve this. |
| ADR-0059 Standard 5 "Principles Established" section states "One Protocol, multiple providers: `InteractionProvider` is the single abstraction" — directly contradicting the scope revision notice that rejected InteractionProvider. Internal contradiction within the same document. | ADR-0059 (internal) | 🔴 High | ⚪ Unresolved — Principles Established must be rewritten after removing Standards 1-3 |

### Supersession Ambiguities

- **ADRs this one supersedes:** ADR-0018, ADR-0028
- **Inheritance Status:**
  - ADR-0028 (Feature Interaction Layer Isolation): Supersession is clean. Standard 5 directly replaces ADR-0028's directory structure guidance with pluggy-compatible updates. ADR-0028's `superseded_by` field has NOT been updated (`superseded_by: []`).
  - ADR-0018 (Service Wrapper Pattern): Supersession is overscoped. ADR-0059 only covers the interaction-specific subset; the general DI ceremony is ADR-0056/ADR-0077 territory. ADR-0018's `superseded_by` field has NOT been updated (`superseded_by: []`).
- **Gaps Identified:**
  1. Neither ADR-0018 nor ADR-0028 has been updated with `superseded_by: [ADR-0059]`.
  2. ADR-0018 supersession is split across three ADRs (ADR-0056, ADR-0077, ADR-0059) without explicit coordination.
  3. Discord is absent from the ADR despite existing hookspec and stub infrastructure in the codebase.

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Secondary Domain Owners:** N/A
- **Plugin/Startup Registration:** Standard 6 defines per-platform hookspecs; actual implementation in `app/infrastructure/hookspecs/features.py` is correct and uses concrete types. ADR example does not match.
- **Config Owner:** Platform settings are governed by ADR-0055 dissolution model; platform availability is settings-driven (per scope revision notice). ADR-0078 (unwritten) should formalize this.
- **Audit Result:** ⚠️ Needs Clarification — Platform service construction governance is delegated to ADR-0078 which does not exist. The ownership boundary between ADR-0059 (feature-side) and ADR-0078 (platform-side) is defined in principle but not in practice.

---

## 6. Scenario Validation Matrix

### Scenario 6.1: Incident Management Workflow

**Context:** Emergency response requires rapid slash-command invocation, modal/view display, and notification dispatch across Slack and potentially Teams.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Slash command registration (Standard 6) | Per-platform hookspec registration at startup | Incident commands (`/sre incident`) registered via `register_slack_commands` hookimpl | ✅ No | Actual codebase hookspec matches kept Standard 6 direction (concrete types) |
| Service layer channel-agnostic (Standard 4, Rule B1) | `service.py` must never import from `interactions/` | Incident service logic is separate from Slack handler | ✅ No | Hex arch dependency direction maintained |
| HTTP test surface (Standard 4) | HTTP routes are primary test surface | Incident commands have HTTP API endpoints for programmatic access | ✅ No | Enables CI testing without Slack SDK |
| Notification dispatch (Standard 5) | Presenters format responses per-channel | Incident notifications use Block Kit for Slack | ✅ No | Presenter isolation prevents service-layer coupling |

**Validation Summary:**

- ✅ Fully aligned

---

### Scenario 6.2: Access Synchronization Workflow

**Context:** Automated sync from identity providers; users trigger sync via slash command or HTTP API; sync status reported back through same channel.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Feature-side interaction boundary (Standard 5) | `interactions/` directory with `ingress.py`, `http.py`, `slack.py` | `app/packages/access/sync/interactions/` implements exactly this structure with ingress, http, and slack modules | ✅ No | Reference implementation validates Standard 5 |
| Shared admission logic (Standard 5, Rule B3) | `ingress.py` contains feature-enable checks, concurrency guards | `ingress.py` has `enqueue_user_sync()`, `enqueue_platform_sync()` with lock checks and feature-gate checks | ✅ No | Domain-specific admission logic correctly scoped to feature |
| HTTP-first bridge (Standard 4) | All transport paths share same service invocation | Slack handlers call ingress functions, which call service; HTTP routes call same ingress functions | ✅ No | Three paths (HTTP, Slack, Teams) share service invocation |

**Validation Summary:**

- ✅ Fully aligned

---

### Scenario 6.3: Access Request Workflow

**Context:** User requests access via slash command or web UI; admin approves via interactive action (button/menu); system provisions across platforms.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Interactive action registration (Standard 6) | Per-platform hookspec for actions/views | Current hookspecs cover `register_slack_commands` but do not explicitly include action/view registration | ⚠️ Yes | Hookspecs currently cover commands only; interactive actions and views would need hookspec extension or alternative registration |
| Presenter isolation (Standard 5, Rule B4) | Presenters map domain results to channel-specific formats without business logic | Approval messages need Block Kit interactive buttons (Slack) or Adaptive Card actions (Teams) — these are complex enough to warrant dedicated presenter modules | ✅ No | Pattern is correct; complexity is manageable with per-channel presenter files |

**Validation Summary:**

- ⚠️ Aligned with documented exception handling

**Mitigation (if ⚠️):** The current hookspecs cover command registration only. Interactive action and view/modal registration are not yet covered by hookspecs. ADR-0059's scope revision correctly identifies this as future work (phased implementation: commands first, then views/actions/messaging). The access request workflow can continue using the current registration pattern until hookspecs are extended.

---

### Scenario 6.4: Multi-Provider Integration (Slack/Teams/AWS/GWS/GitHub)

**Context:** Features must be deployable across Slack, Teams, and HTTP API without duplicating interaction logic.

| Aspect | ADR Requirement | Integration Reality | Gap? | Notes |
|--------|-----------------|---------------------|------|-------|
| Per-platform hookspec isolation (Standard 6) | Platform-specific hooks avoid abstraction leaks | Codebase has `register_slack_commands`, `register_teams_commands`, `register_discord_commands` — all concrete types | ✅ No | Isolation is correct; each platform handler receives its own provider type |
| HTTP as universal fallback (Standard 4) | HTTP endpoints are platform-independent | HTTP routes work for programmatic API access, webhooks, and platform-neutral testing | ✅ No | All features accessible via HTTP regardless of platform availability |
| New platform addition (Standard 6) | New platforms require hookspec method + provider implementation, no feature code changes | Discord stub exists with hookspec, provider, and formatter — validates the extension model | ✅ No | Discord addition required no changes to existing feature packages |
| Platform availability settings-driven | Per scope revision: platform availability is settings-gated | Platform construction is config-gated in current codebase | ⚠️ Yes | ADR-0078 (unwritten) should formalize settings-driven platform availability. Current implementation is correct but governance is not documented. |

**Validation Summary:**

- ⚠️ Aligned with documented exception handling

**Mitigation (if ⚠️):** Platform availability settings governance is delegated to the unwritten ADR-0078. Current codebase implementation is correct (settings-gated platform construction), but the governance documentation gap must be closed.

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Per-Platform Hookspecs vs. Unified Interaction Hook

- **Chosen:** Separate hookspecs per platform (`register_slack_commands`, `register_teams_commands`, `register_discord_commands`)
- **Rejected:** Single `register_interactions(provider: InteractionProvider)` hookspec (rejected as part of Standards 1-3)
- **Rationale:** Platform handler signatures genuinely differ (Slack `ack()` pattern vs. Teams turn context vs. Discord event handlers). A unified hookspec would force artificial abstraction leaks. The Platform Services Assessment empirically validated this decision.
- **Risk Accepted:** Each new platform adds a hookspec method (O(1) per platform). With 3 platforms currently and no near-term additions beyond Discord, this is manageable.
- **Contingency:** If the number of platforms grows significantly, the hookspec surface can be consolidated per Standard 6's opt-in arguments feature — hookimpls can accept fewer arguments than the hookspec.

### Tradeoff 7.2: HTTP-First Testing vs. Full Platform-Specific Test Coverage

- **Chosen:** HTTP routes as primary test surface; platform-specific tests as supplements
- **Rejected:** Full end-to-end tests through each platform SDK
- **Rationale:** Platform SDK tests require platform credentials, external API access, and complex mock setups. HTTP tests validate the service logic path with minimal infrastructure. The hex arch inversion guarantee (service.py never imports from interactions/) ensures path equivalence.
- **Risk Accepted:** Presenter formatting errors and platform-specific handler issues are not caught by HTTP tests.
- **Contingency:** Presenter unit tests (validating Block Kit / Adaptive Card output structure) and platform handler integration tests provide supplementary coverage.

### Tradeoff 7.3: Feature-Owned Ingress vs. Infrastructure Middleware

- **Chosen:** Each feature package owns its admission logic in `interactions/ingress.py`
- **Rejected:** Centralized infrastructure middleware for feature-enable checks and concurrency guards
- **Rationale:** Admission logic involves domain-specific state (sync locks, platform-specific configurations, feature-specific preconditions). A centralized middleware would need to understand each feature's domain — creating inappropriate coupling.
- **Risk Accepted:** Boilerplate duplication across features (feature-enable check pattern, lock acquisition pattern).
- **Contingency:** If boilerplate becomes excessive, common patterns can be extracted into infrastructure decorators/utilities without centralizing the admission logic itself.

### Tradeoff 7.4: Concrete Platform Types vs. Protocol Abstraction

- **Chosen:** Concrete types (`SlackPlatformProvider`, `TeamsPlatformProvider`) in hookspecs
- **Rejected:** Abstract `InteractionProvider` Protocol (Standards 1-3, rejected)
- **Rationale:** Platform services are Category C infrastructure implementation details (ADR-0077/ADR-0078 direction). No alternative implementation is expected for `SlackPlatformProvider` — there is exactly one Slack. Protocol abstraction would add indirection without enabling meaningful substitution.
- **Risk Accepted:** Feature hookimpls are coupled to concrete platform types. If a platform type is renamed, all features must update.
- **Contingency:** Renaming is a mechanical refactoring operation. The coupling is intentional and appropriate for Category C services.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Author ADR-0078 (Platform Services Architecture) | ✅ Yes | SRE Team | 2026-05-13 | Create the missing ADR-0078 to cover platform service construction governance, settings-driven availability, concrete service types, and startup ordering. Multiple existing records (ADR-0059, ADR-0025, ADR-0071, ADR-0077) depend on it. |
| Perform full body revision of ADR-0059 | ✅ Yes | SRE Team | 2026-05-13 | Remove rejected Standards 1-3 entirely. Rewrite Standard 6 with actual codebase hookspec definitions (concrete types, actual method names). Rewrite Principles Established, Compliance, and Implementation Guidance sections. Remove all stale revision notices. |
| Resolve ADR-0018 supersession ownership | ✅ Yes | SRE Team | 2026-05-13 | Determine whether ADR-0059 alone supersedes ADR-0018, or whether ADR-0056/ADR-0077 jointly own the supersession. Update ADR-0018's `superseded_by` field accordingly. Remove ADR-0018 from ADR-0059's `supersedes` if ADR-0056/ADR-0077 are the primary superseding records. |
| Update ADR-0028 `superseded_by` field | ❌ No | SRE Team | After revision | Set `superseded_by: [ADR-0059]` in ADR-0028 metadata to complete the supersession chain. |
| Add Discord to Standard 5 directory example or explicitly exclude | ❌ No | SRE Team | After revision | The codebase has `register_discord_commands` hookspec and `DiscordPlatformProvider` stub. ADR-0059 should either include `discord.py` in the interactions/ directory example or add an explicit non-goal for Discord. |
| Add presenter testing recommendation to Standard 4/5 | ❌ No | SRE Team | After revision | Explicitly recommend presenter unit tests for Block Kit / Adaptive Card output alongside HTTP route tests. Currently implicit. |
| Reconcile PlatformService Category A vs. Category C classification | ❌ No | SRE Team | After ADR-0078 | ADR-0077 Standard 1 classifies PlatformService as Category A (P2). ADR-0059 scope revision says platform services are Category C. ADR-0078 should resolve this classification definitively. |

**Blocking Actions Must Resolve Before Step 10 Proceeds:** Three blocking actions identified. ADR-0059 body revision and ADR-0078 authoring must complete before cascade work begins. ADR-0018 supersession ownership must be clarified.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

⚪ **REVISE** → ADR-0059 requires authoring revision; return to Step 5-9 author team with feedback

**If REVISE, Provide Primary Blockers:**

1. **ADR-0078 does not exist:** The primary delegation target for platform service construction governance is missing, creating a dangling reference in the supersession chain (ADR-0025 → ADR-0078) and leaving Commands retirement (ADR-0071) unblocked.
2. **Document is internally contradictory:** Three rejected standards (1-3) remain interleaved with three kept standards (4-6). Principles Established, Compliance, and Implementation Guidance sections reference rejected concepts without revision marks. A reader cannot reliably determine which content applies.
3. **Standard 6 hookspec examples are stale and wrong:** Method names (`register_slack_interactions`), parameter types (`InteractionProvider`), and parameter styles (`self`) do not match the actual codebase definitions (`register_slack_commands`, `SlackPlatformProvider`, no `self`). Example code is the most-copied section — it must be accurate.

**Revision Deadline:** 2026-05-13

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | AI Architecture Reviewer |
| **Reviewer Title** | Architecture Review Agent |
| **Organization/Team** | SRE Team |
| **Sign-Off Date** | 2026-04-29 |
| **Email** | N/A (automated review) |

---

## 11. Review Artifacts Reference

**This Review Record Should Be Attached To:**

- ADR-0059 revision PR (when revision is submitted)
- Internal decision tracker / ADR review calendar
- ADR-0078 authoring task (as dependency context)

**This Review Template Was Completed Per:**

- ADR-0044 (Governance and Operating Model) § Step 9.5
- Revalidation Cycle: One-time gate review → then annual review_state cycle
