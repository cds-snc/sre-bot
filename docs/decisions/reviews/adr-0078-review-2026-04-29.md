# ADR Challenge and Content Review Template

**Purpose:** Standardized artifact for Step 9.5 (Canonical ADR Challenge and Content Review Gate) execution. Used to validate newly authored replacement ADRs (Phase A-E) for content soundness, assumption correctness, and platform-reality alignment before cascade rewrites proceed.

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0078: Platform Services Architecture |
| **Reviewer Name & Title** | AI Architecture Reviewer (Copilot), SRE Team |
| **Secondary Reviewers** | None |
| **Review Date** | 2026-04-29 |
| **Revalidation Due** | 2027-04-29 |
| **Gate Outcome** | ✅ **PASS** |
| **Outcome Rationale** | All corrections from initial review (REVISE) have been applied: (1) `ITurnContext<T>` (C#/.NET) replaced with `TurnContext` (Python SDK) throughout ADR-0078 and companion ADR-0059; (2) Source reference URLs updated for Slack Bolt and Teams Bot Framework; (3) Alternatives Considered and Source References list numbering fixed; (4) ADR-0059 already had ADR-0048 in `related_records` (no change needed). All architectural decisions and assumptions are sound. |

---

## 2. Evidence Gathering & Convention Validation

**Requirement:** Before challenging assumptions, identify and search authoritative sources that govern the domain covered by this ADR. Document findings to establish whether the ADR aligns with or deliberately deviates from widely accepted best practices.

### 2.A Language & Framework Standards

**Applicable Standards (check all that apply):**

- ✅ Python Enhancement Proposals (PEP 484 — type hints)
- ⚪ FastAPI Official Documentation
- ⚪ Pydantic V2 Documentation
- ⚪ Pydantic Settings V2
- ✅ Pluggy Documentation & Best Practices (<https://pluggy.readthedocs.io/>)
- ✅ Python Typing Module Official Docs
- ⚪ Structlog Documentation
- ⚪ Starlette Documentation
- ✅ Other: Slack Bolt Python SDK (<https://docs.slack.dev/tools/bolt-python/>), Microsoft Bot Framework Python SDK (<https://learn.microsoft.com/en-us/python/api/botbuilder-core/>)

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|---|---|---|---|---|
| PEP 484 — Type Hints | "type hints Protocol typing" | `Protocol` enables structural subtyping for interface contracts. Generic type parameters enable typed abstract containers. | ✅ Aligned | N/A — ADR correctly identifies that a unified Protocol would lose platform-specific type information. |
| Pluggy hookspec/hookimpl | "pluggy hookspec hookimpl registration" | Pluggy supports typed hookspec parameters. Each hookspec can have independently typed signatures. Per-hook parameter types are preserved. | ✅ Aligned | N/A — Per-platform hookspecs with concrete types is a valid pluggy usage pattern. |
| Slack Bolt Python — Commands | "Slack Bolt command handler ack say respond" | Command handlers use kwargs injection: `def handler(ack, respond, command)`. Actions use `def handler(ack, say, body, client)`. Events use `def handler(event, say)`. All require `ack()` call. Functional middleware model confirmed. | ✅ Aligned | N/A |
| Slack Bolt Python — Actions | "Slack Bolt action handler listener arguments" | Action listeners receive kwargs like `ack`, `body`, `say`, `respond`, `action`, `client`. Kwargs injection pattern — not class-based. | ✅ Aligned | N/A |
| Teams Bot Framework Python SDK — TurnContext | "TurnContext Python botbuilder on_message_activity" | Python SDK uses `TurnContext` class (NOT `ITurnContext<T>`). `ITurnContext<T>` is the C#/.NET generic interface. Python method: `async def on_message_activity(self, turn_context: TurnContext)`. Class-based subclassing of `TeamsActivityHandler`. | ⚠️ Deviation | ADR cites `ITurnContext<T>` which is the C#/.NET type. The Python SDK equivalent is plain `TurnContext` — no generics, no `I` prefix. The asymmetry argument remains valid but the specific type name is incorrect for Python. **Correction required.** |
| Teams Bot Framework — Activity Handler | "TeamsActivityHandler Python on_teams_members_added" | Python `TeamsActivityHandler` provides `on_message_activity`, `on_conversation_update_activity`, `on_teams_channel_created`, etc. Class-based override model confirmed. | ✅ Aligned | N/A |

---

### 2.B Infrastructure & Operational Standards

**Applicable Standards (check all that apply):**

- ✅ Twelve-Factor App Methodology (<https://12factor.net/>)
- ⚪ CNCF / Cloud-Native Best Practices
- ⚪ AWS Well-Architected Framework
- ⚪ Structured Logging Standards
- ⚪ OWASP Security Best Practices
- ✅ External Provider Specs (Slack Bolt Python SDK, Teams Bot Framework Python SDK)
- ⚪ Other

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|---|---|---|---|---|
| Twelve-Factor: III. Config | "store config in the environment" | Config that varies between deploys should be stored in environment variables. Platform enablement via env vars (`SLACK_ENABLED`) aligns with Factor III. | ✅ Aligned | N/A |
| Twelve-Factor: IV. Backing Services | "treat backing services as attached resources" | Each distinct backing service is an attached resource, accessed via config. Platform services as independently-configurable attached resources aligns. | ✅ Aligned | N/A |
| Slack Bolt Python Docs — URL Accuracy | Navigated to `https://tools.slack.dev/bolt-python/` | URL redirects to `https://docs.slack.dev/tools/bolt-python/`. The cited URL works via redirect but the canonical URL has changed. | ⚠️ Deviation | Source Reference 5 cites `https://tools.slack.dev/bolt-python/`. The canonical URL is now `https://docs.slack.dev/tools/bolt-python/`. **Minor correction — update URL.** |
| Teams Bot Framework Docs — URL Accuracy | Navigated to `https://learn.microsoft.com/en-us/microsoftteams/platform/bots/bot-basics` | URL redirects to `/bots/bot-concepts`. Page title is "Understand bot concepts". Content matches ADR claims. | ⚠️ Deviation | Source Reference 6 cites `bot-basics` in the URL path. The canonical path is now `/bots/bot-concepts`. **Minor correction — update URL.** |

---

### 2.C Cross-Cutting Design Patterns

**Applicable Standards (check all that apply):**

- ⚪ Event-Driven Architecture Patterns
- ⚪ CQRS
- ⚪ Eventual Consistency Patterns
- ✅ Dependency Injection Best Practices
- ⚪ Circuit Breaker & Resilience Patterns
- ⚪ Observability & Logging Patterns
- ⚪ Idempotency Patterns
- ✅ Other: Rule of Three / Premature Abstraction (Martin Fowler, Don Roberts)

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|---|---|---|---|---|
| Rule of Three (Don Roberts via Fowler's Refactoring) | "Rule of Three refactoring abstraction" | "The first time you do something, you just do it. The second time you do something similar, you wince at the duplication, but you do the duplicate thing anyway. The third time you do something similar, you refactor." Applicable to abstraction decisions — don't create an abstraction until you have three concrete instances proving a shared pattern. | ✅ Aligned | N/A — With 2 platforms in production (Slack active, Teams experimental), abstraction is correctly identified as premature. |
| Mark Seemann — Composition Root | "composition root dependency injection" | Service construction belongs in the composition root (lifespan), not scattered across consumers. | ✅ Aligned | N/A — ADR-0078 Standard 4 O2 mandates construction in lifespan or infrastructure provider functions. |
| Interface Segregation Principle (SOLID) | "ISP no client should depend on methods it does not use" | Clients should not be forced to depend on interfaces they don't use. A unified InteractionProvider would force features to depend on methods for platforms they don't support. | ✅ Aligned | N/A — Per-platform concrete services avoid ISP violations. |

---

### 2.D Validation Summary

**Total Standards Checked:** 12
**Aligned with Best Practice:** 9
**Deliberate Deviations:** 3 (all minor — URL staleness and Python vs C# type name)

**High-Level Finding:**

- 🟡 **Mostly Grounded:** All architectural standards checked and aligned; 3 minor factual corrections needed (type name, 2 URLs). No unexplained deviations from best practices.

**Deviation Summary:**

1. **`ITurnContext<T>` citation** — ADR uses the C#/.NET generic interface name. The Python Bot Framework SDK uses plain `TurnContext` (no generics, no `I` prefix). The architectural argument (class-based vs. functional) is unaffected. **Fix: replace `ITurnContext<T>` with `TurnContext` throughout.**
2. **Slack Bolt URL** — `https://tools.slack.dev/bolt-python/` now redirects to `https://docs.slack.dev/tools/bolt-python/`. **Fix: update Source Reference 5.**
3. **Teams Bot Framework URL** — `bot-basics` in the URL path now redirects to `bot-concepts`. **Fix: update Source Reference 6.**

---

## 3. Assumptions Challenged

### Assumption 3.1: Platform interaction models are fundamentally incompatible at the handler signature level

- **Stated Norm:** "Slack Bolt uses functional middleware with `ack()`, `say()`, and `command` parameters; Teams Bot Framework uses class-based `TeamsActivityHandler` with `ITurnContext<T>`."
- **Underlying Assumption:** The two platforms' handler registration and handler execution patterns are so different that no single typed Python Protocol can faithfully represent both without type erasure.
- **Challenge:** Could an adapter layer normalize both models into a shared Protocol? For example, a Protocol with methods like `register_command(name: str, handler: CommandHandler)` where `CommandHandler` is a Protocol with an `execute(context: UnifiedContext)` method?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** Yes — an adapter layer is technically feasible. However, the `UnifiedContext` type would need to carry platform-specific data (Slack's `ack()` callable, Teams' `TurnContext.send_activity()` method), requiring either union types, `Any` fields, or platform-specific accessors — all of which reintroduce the coupling the abstraction was trying to eliminate. The Slack handler _must_ call `ack()` within 3 seconds (Slack API requirement) — this is a platform-native constraint that cannot be abstracted away.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The fundamental asymmetry is confirmed by authoritative documentation. Slack Bolt uses Python kwargs injection (`def handler(ack, say, command)`) while Teams uses class-based method overrides (`async def on_message_activity(self, turn_context: TurnContext)`). These are genuinely different paradigms. A unified Protocol would add indirection without enabling meaningful platform-neutral handler code.

### Assumption 3.2: A unified Protocol would require `Callable[..., Any]` type erasure

- **Stated Norm:** "A unified Protocol would require `Callable[..., Any]` for handler signatures — erasing all type safety."
- **Underlying Assumption:** There is no way to define a unified handler registration interface that preserves platform-specific type information.
- **Challenge:** The specific claim about `Callable[..., Any]` is slightly imprecise. The deeper issue is that a unified _registration_ interface would need to accept handlers with incompatible signatures. Could we use `@overload` or generic type parameters to maintain some type safety?
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial — `@overload` could technically distinguish platform-specific registration methods on a single Protocol. But this would result in a Protocol with per-platform overloads, which is functionally equivalent to having separate per-platform types (the ADR's chosen approach) with extra indirection. The net effect is the same: handlers remain platform-specific.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The specific mechanism described (`Callable[..., Any]`) is one way the problem manifests, but it's slightly reductive. The core issue is that platform handler _behavior_ requires platform-native constructs (Slack's `ack()` timeout, Teams' `TurnContext` state management). Even if you avoid `Callable[..., Any]` via overloads, you haven't achieved meaningful abstraction — you've just added a wrapper. The ADR's conclusion is correct even if the specific type-erasure mechanism could be described more precisely.

### Assumption 3.3: Rule of Three applies — abstract only after three implementations

- **Stated Norm:** "The Rule of Three applies — abstract only after three concrete implementations prove a shared pattern."
- **Underlying Assumption:** Two platforms (Slack active, Teams experimental) are insufficient to justify abstraction, and a third platform would be needed to validate a shared pattern.
- **Challenge:** The Rule of Three is a guideline, not a law. If two platforms clearly share a common pattern, early abstraction could reduce future migration cost. Discord is listed as a stub — should its potential be considered?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — Discord exists only as a stub with no production implementation and no committed timeline. The two active platforms (Slack and Teams) have fundamentally different interaction models (kwargs-injected functions vs. class-based handlers), so they do NOT share a common handler pattern. The Rule of Three is correctly applied here because even with only two platforms, the evidence shows asymmetry rather than a shared pattern.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The Rule of Three is well-applied. Even if we had three platforms, the question would be whether they share enough pattern similarity to justify abstraction. Slack Bolt (Python kwargs injection) and Teams Bot Framework (class-based activity handlers) demonstrate that platform SDKs diverge in fundamental ways. A third platform would likely introduce yet another paradigm.

### Assumption 3.4: Settings-driven availability eliminates provider discovery

- **Stated Norm:** "Whether a platform is available is determined entirely by settings. There is no 'provider discovery' pattern."
- **Underlying Assumption:** Explicit configuration (`SLACK_ENABLED=true`) is more predictable and simpler than dynamic discovery for a small number of platforms (2-3).
- **Challenge:** Explicit per-platform wiring in the lifespan becomes verbose as platforms are added. Does the lifespan need to grow with `if settings.slack.enabled: ... if settings.teams.enabled: ... if settings.discord.enabled: ...` blocks?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — with 2-3 platforms, explicit wiring is a handful of conditional blocks. Twelve-Factor Factor III supports env-var-driven configuration. The ADR acknowledges the scaling risk (5+ platforms) and provides a mitigation path. The current platform count does not justify discovery overhead.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Configuration-driven platform availability aligns with Twelve-Factor principles and is simpler to debug than automatic discovery at current scale.

### Assumption 3.5: Features never check platform availability — hookspec firing implies platform readiness

- **Stated Norm:** "Features never check whether a platform is enabled. If the hookspec fires, the platform is available."
- **Underlying Assumption:** The hookspec-based registration model provides a clean inversion where infrastructure controls when features are notified of platform availability.
- **Challenge:** What about features that need platform-specific resources prepared before hookspec registration? For example, a feature that pre-loads Slack Block Kit templates or Teams Adaptive Card schemas.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — resource preparation can happen lazily within the hookimpl handler itself, or in the feature's `startup_warmup` hookimpl. The hookspec model doesn't preclude preparation; it just ensures features don't make platform-availability checks themselves. The existing `startup_warmup` hookimpl pattern (visible in lifespan logs: `access_sync_settings_loaded`, `access_sync_providers_warmed`) provides a clean preparation phase.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The hookspec inversion is well-designed. Features that need preparation can use `startup_warmup` for general initialization and platform-specific hookimpls for platform-specific setup.

### Assumption 3.6: Category C classification is correct for platform services

- **Stated Norm:** "Platform services are Category C infrastructure implementation details (ADR-0077). They are not abstracted behind a Protocol because there is exactly one implementation per platform."
- **Underlying Assumption:** Each platform service wraps exactly one SDK and has exactly one implementation, so there is no substitution need that would justify a Protocol contract.
- **Challenge:** Platform services are consumed by multiple features (access sync, incident management, etc.). Category A is for "abstract backing services" consumed by multiple features. Does multi-feature consumption argue for Category A?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — ADR-0077 Category A requires _swappable implementations_ behind a Protocol (e.g., `DirectoryProvider` can be Google or Mock). Each platform service has exactly one real implementation (`SlackPlatformProvider` wraps Slack Bolt, period). Multi-feature consumption alone doesn't elevate to Category A — the distinguishing factor is whether swappability is required. It is not.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Category C is correctly applied. The fact that `SlackPlatformProvider` is consumed by multiple features is similar to how a specific database client might be used by multiple services — it's still an implementation detail, not a swappable abstraction. ADR-0077 has already been updated to remove `PlatformService` from Category A with explicit cross-reference to ADR-0078.

---

## 4. Failure Modes Identified

All assumptions scored High confidence. The following failure modes are documented for completeness.

### Failure Mode 4.1: Rename Coupling Cascade (from SlackPlatformProvider → SlackService)

- **If Assumption Fails:** N/A — this is an acknowledged planned migration cost, not an assumption failure.
- **Platform Impact:**
  - Incident management workflow: Low — mechanical rename, no behavioral change.
  - Access synchronization workflow: Low — all hookimpls update parameter names, no logic change.
  - Access request workflow: Low — same mechanical update.
  - Multi-provider integrations: Low — import paths change but behavior is unchanged.
- **Probability Estimate:** High (this is a planned change per Implementation Guidance step 2)
- **Mitigation or Acceptance:** Accepted. Mechanical refactoring is IDE-assisted. The ADR explicitly acknowledges this in Tradeoffs Accepted. A single PR can atomically rename all references.

### Failure Mode 4.2: Dual Access Pattern Creates Developer Confusion (hookspec inbound vs. direct import outbound)

- **If Assumption Fails:** A developer incorrectly imports `SlackPlatformProvider` directly for inbound handler registration (bypassing hookspec injection), creating a hard dependency that doesn't respect platform-availability gating.
- **Platform Impact:**
  - Incident management workflow: Low — incident features currently use hookspec pattern correctly.
  - Access synchronization workflow: Low — `access/sync/interactions/slack.py` demonstrates correct pattern.
  - Access request workflow: None — access requests are currently HTTP-only.
  - Multi-provider integrations: Medium — new features might misunderstand the dual pattern.
- **Probability Estimate:** Low — the pattern is well-documented in both ADR-0078 (F3) and ADR-0059 (N2), and the reference implementation in `access/sync` provides a working example.
- **Mitigation or Acceptance:** Accepted. ADR-0059 Standard 3 K4 requires hookspec-based registration. Outbound import (F3/N2) is the only exception. Code review should catch incorrect direct imports for inbound registration.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|---|---|---|---|
| ADR-0078 O4 permits "simpler provider patterns" for infrastructure-internal services; ADR-0056 Standard 4 mandates three-file DI ceremony as "canonical". | ADR-0078, ADR-0056 | 🟢 Low | ✅ Resolved → ADR-0078 O4 explicitly creates a scoped exception for Category C services accessed via hookspec injection rather than `Annotated[..., Depends()]`. ADR-0056 Standard 5 already permits non-cached registry lookups for platform providers. No contradiction — ADR-0078 narrows the applicability of ADR-0056 Standard 4 for this specific service category. |
| ADR-0078 Standard 3 F2 references hookspec parameter types as concrete (`SlackPlatformProvider`) while the ADR's own Target Naming proposes renaming to `SlackService`. Both ADR-0078 and ADR-0059 Standard 3 use current names in hookspec examples. | ADR-0078, ADR-0059 | 🟢 Low | ✅ Resolved → The ADR explicitly separates current naming from target naming, and Implementation Guidance step 2 addresses the rename as a future task. Both ADRs are internally consistent about current state vs. future state. |
| ADR-0078 `constrained_by` includes ADR-0048 but ADR-0059 does not include ADR-0048 in `constrained_by`. ADR-0059 references ADR-0048 indirectly through ADR-0056 Standard 3 (centralized providers per ADR-0048 B2). | ADR-0078, ADR-0059 | 🟢 Low | ⚪ Unresolved → ADR-0059 should either add ADR-0048 to `constrained_by` or to `related_records`. This is a metadata completeness issue, not an architectural contradiction. Non-blocking. |

### Supersession Ambiguities

- **ADRs this one supersedes:** ADR-0025 (Interaction Providers Concept)
- **Inheritance Status:** ✅ All inherited constraints acknowledged.
  - ADR-0025's HTTP-First principle is preserved (migrated to ADR-0059 Standard 1).
  - ADR-0025's platform-specific handler structure is preserved (migrated to ADR-0059 Standard 2).
  - ADR-0025's unified `InteractionProvider` Protocol is explicitly rejected with rationale.
- **Gaps Identified:** None. ADR-0025 already has `superseded_by: [ADR-0078]`. Bidirectional supersession links are present and correct per ADR-0044 requirements.

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Secondary Domain Owners:** N/A (infrastructure-internal scope)
- **Plugin/Startup Registration:** Hookspecs defined in `app/infrastructure/hookspecs/features.py`. Registration is startup-driven via pluggy per ADR-0046. Clearly identified.
- **Config Owner:** Platform settings in `app/infrastructure/configuration/integrations/` per ADR-0055 dissolution model. Per-platform singleton providers.
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation Matrix

### Scenario 6.1: Incident Management Workflow

**Context:** Emergency response requires Slack notifications to incident channels, team paging, and status updates. Platform availability is critical during incidents.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|---|---|---|---|---|
| Platform availability during incidents | Standard 2: Settings-driven availability; platform skipped if disabled. | Incident management requires Slack to be available. If `SLACK_ENABLED=false`, incident notifications cannot be sent. | ✅ No | Incident deployments will always have `SLACK_ENABLED=true`. This is an operational configuration concern, not an architectural gap. |
| Outbound notification from incident features | Standard 3 F3: Features may import platform service directly for outbound messaging. | Incident features send Slack messages to channels. Direct import of `SlackPlatformProvider` is the current pattern. | ✅ No | ADR explicitly permits direct import for outbound messaging (F3). |
| Handler registration timing | Standard 3: Hookspec fires during lifespan; handlers registered before transport starts. | Incident handlers must be registered before any incoming Slack messages arrive. | ✅ No | ADR-0046 lifecycle invariant (transport starts after registration) ensures this ordering. |

**Validation Summary:** ✅ Fully aligned

---

### Scenario 6.2: Access Synchronization Workflow

**Context:** Automated sync from identity providers (AWS IAM Identity Center, Google Workspace) triggered via Slack commands or HTTP API. Must handle platform-specific handler registration and outbound status notifications.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|---|---|---|---|---|
| Slack command registration | Standard 3: Features register via hookspec injection (`register_slack_commands`). | Access sync registers `/sre access sync user` and `/sre access sync status` commands via hookimpl in `__init__.py`. | ✅ No | The existing `app/packages/access/sync/__init__.py` hookimpl pattern matches ADR-0078 Standard 3 exactly. This is the reference implementation cited in the ADR. |
| HTTP-first testing surface | Companion ADR-0059 Standard 1: HTTP endpoints are primary test surface. | Access sync has `interactions/http.py` with FastAPI routes. | ✅ No | Governed by ADR-0059, not ADR-0078. Cross-reference is clear. |
| Platform service construction | Standard 2: Settings-driven, credential-checked platform construction in lifespan. | `SlackPlatformProvider` is constructed in lifespan when `SLACK_ENABLED=true`. | ✅ No | Matches lifespan logs: `slack_provider_initialized enabled=True`. |
| Category C classification for platform services | Standard 1 S2: Platform services are Category C. No Protocol. | Access sync's `interactions/slack.py` receives concrete `SlackPlatformProvider`. No abstract Protocol. | ✅ No | Pattern matches. Feature does not construct or configure the platform service. |

**Validation Summary:** ✅ Fully aligned

---

### Scenario 6.3: Access Request Workflow

**Context:** User requests access to a resource/role; admin approves; system provisions. Currently HTTP-only with Slack support planned.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|---|---|---|---|---|
| Platform-agnostic feature operation | Standard 3 F1: Features that don't implement a hookimpl run on HTTP + background jobs only. | Access requests are currently `enabled=False` and HTTP-only. No Slack hookimpl exists. | ✅ No | The ADR explicitly supports features that operate without any platform hookimpl. When access requests add Slack support, they'll add a hookimpl — no other feature code changes. |
| Future Slack support path | Standard 3: Add hookimpl to receive `SlackPlatformProvider` and register handlers. | When access requests enable Slack commands, they'll follow the same pattern as access sync. | ✅ No | Clear migration path via hookimpl addition. |

**Validation Summary:** ✅ Fully aligned

---

### Scenario 6.4: Multi-Provider Integration (Slack/Teams/AWS/GWS/GitHub)

**Context:** Operations that span platform services and backing services — e.g., access sync triggered via Slack, executing against AWS IAM Identity Center, reading from Google Workspace directory.

| Aspect | ADR Requirement | Integration Reality | Gap? | Notes |
|---|---|---|---|---|
| Independent platform configuration | Standard 2 A1-A3: Each platform independently configured via settings. | A deployment may run Slack + AWS without Teams. Each platform's settings are independent singletons. | ✅ No | Settings dissolution (ADR-0055) ensures platform settings don't cross-depend. |
| Platform service independence | Standard 1 S4: Features do not construct platform services. | Access sync receives `SlackPlatformProvider` via hookspec; constructs AWS Identity Center adapter via its own providers. Platform service and backing service construction are independent concerns. | ✅ No | Clean separation: infrastructure constructs platform services; features construct their own domain adapters. |
| Cross-platform identity correlation | Non-goal (deferred). | Currently only Slack is in production for interaction. Teams is experimental. No cross-platform user identity mapping needed yet. | ✅ No | Correctly deferred per Platform Services Assessment. Will need a dedicated ADR when Teams is actively used by a feature. |

**Validation Summary:** ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Concrete Types vs. Abstraction Flexibility

- **Chosen:** Concrete per-platform services (`SlackPlatformProvider`, `TeamsPlatformProvider`) without a unifying Protocol.
- **Rejected:** Unified `InteractionProvider` Protocol enabling platform-neutral feature code.
- **Rationale:** Platform interaction models are fundamentally asymmetric. A unified Protocol would erase type safety (confirmed by SDK documentation review). The Rule of Three is not satisfied.
- **Risk Accepted:** Feature hookimpls are mechanically coupled to concrete type names. Any rename requires updating all consumer hookimpls.
- **Contingency:** If a third platform proves a shared pattern exists, introduce a Protocol at that point. The current architecture does not preclude future abstraction.

### Tradeoff 7.2: Per-Platform Hookspecs vs. Unified Registration Hook

- **Chosen:** Separate hookspec methods per platform (`register_slack_commands`, `register_teams_commands`).
- **Rejected:** Single `register_commands(platform: str, provider: InteractionProvider)` hookspec.
- **Rationale:** Per-platform hookspecs preserve concrete parameter types. A unified hook would require type erasure or runtime type checking.
- **Risk Accepted:** Each new platform adds a hookspec method + hookimpl per feature. This is O(platforms × features) integration surface.
- **Contingency:** At 5+ platforms, consider hookspec consolidation with platform-typed parameters using `@overload` or generic dispatch.

### Tradeoff 7.3: Dual Access Pattern (Hookspec Inbound / Direct Import Outbound)

- **Chosen:** Hookspec injection for inbound handler registration; direct import for outbound messaging.
- **Rejected:** Hookspec-only access (would require additional hookspec surface for outbound); DI-only access (would require full DI ceremony for Category C services).
- **Rationale:** Hookspec registration provides clean platform-availability gating for inbound handlers. Outbound messaging is a simpler use case where direct import is pragmatic and avoids unnecessary hookspec/DI ceremony.
- **Risk Accepted:** Two access patterns for the same service type may confuse developers unfamiliar with the rationale.
- **Contingency:** Document the distinction clearly (done in ADR-0078 F3 and ADR-0059 N2). Code review catches incorrect direct imports for inbound registration.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|---|---|---|---|---|
| Fix `ITurnContext<T>` → `TurnContext` | ✅ Yes | ADR Author | 2026-05-06 | ✅ **DONE.** Replaced all references to `ITurnContext<T>` with `TurnContext` in ADR-0078 and ADR-0059. |
| Update Slack Bolt URL | ❌ No | ADR Author | 2026-05-06 | ✅ **DONE.** Updated to `https://docs.slack.dev/tools/bolt-python/` in ADR-0078 and ADR-0059. |
| Update Teams Bot Framework URL | ❌ No | ADR Author | 2026-05-06 | ✅ **DONE.** Updated to `https://learn.microsoft.com/en-us/microsoftteams/platform/bots/bot-concepts` in ADR-0078 and ADR-0059. |
| Fix Alternatives Considered numbering | ❌ No | ADR Author | 2026-05-06 | ✅ **DONE.** Fixed Alternatives Considered and Source References sequential numbering in ADR-0078. |
| Consider adding ADR-0048 to ADR-0059 metadata | ❌ No | ADR Author | 2026-05-13 | ✅ **DONE.** ADR-0059 already had ADR-0048 in `related_records` — no change needed. |

**Blocking Actions Must Resolve Before Step 10 Proceeds:** All blocking actions resolved. The `ITurnContext<T>` → `TurnContext` correction has been applied to ADR-0078 and ADR-0059.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

✅ **PASS** → ADR-0078 accepted; proceed to Step 10 (cascade rewrites)

**If REVISE, Provide Primary Blockers:**

1. ~~**`ITurnContext<T>` is the C#/.NET Bot Framework generic interface, not the Python SDK type.**~~ **RESOLVED.** Replaced with `TurnContext` throughout ADR-0078 and ADR-0059.

**Non-Blocking Items (fixed during revision):**

1. ~~Source Reference URL updates~~ **RESOLVED.** Slack and Teams docs URLs updated.
2. ~~Alternatives Considered list numbering fix~~ **RESOLVED.** Sequential numbering applied.
3. ~~ADR-0059 metadata completeness~~ **RESOLVED.** ADR-0048 already present in `related_records`.

**Revision Deadline:** 2026-05-06

---

## 10. Reviewer Sign-Off

By signing off below, the reviewer confirms:

- All sections of this template have been completed
- Evidence gathering (Section 2) has been completed; authoritative standards searched and documented
- Contradictions have been audited and dispositioned
- Scenarios have been validated against operational reality
- Assumptions are defensible with documented evidence and grounded in official best practices
- Deliberate deviations from standards have explicit rationale
- Gate outcome reflects professional-grade readiness for production platform governance

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | AI Architecture Reviewer (GitHub Copilot) |
| **Reviewer Title** | Automated Architecture Review Agent |
| **Organization/Team** | SRE Team |
| **Sign-Off Date** | 2026-04-29 |
| **Email** | N/A (automated reviewer) |

---

## 11. Review Artifacts Reference

**This Review Record Should Be Attached To:**

- PR or issue that delivers the revised ADR (if revisions were required)
- Internal decision tracker or ADR review calendar
- Audit trail for governance compliance verification

**This Review Template Was Completed Per:**

- ADR-0044 (Governance and Operating Model) § Step 9.5
- Revalidation Cycle: [One-time gate review] → [Then annual review_state cycle]
