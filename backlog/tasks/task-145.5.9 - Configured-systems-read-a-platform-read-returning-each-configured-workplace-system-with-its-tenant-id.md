---
id: TASK-145.5.9
title: >-
  Configured-systems read: a platform read returning each configured workplace
  system with its tenant id
status: To Do
assignee: []
created_date: '2026-10-19 15:25'
updated_date: '2026-10-19 15:33'
labels:
  - incident
  - platform
dependencies:
  - TASK-145.5.3
references:
  - decisions/workplace-systems.md
  - decisions/configuration.md
  - decisions/dependency-injection.md
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 399000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 7 of Stack K (handoff doc-13), split out of TASK-145.5.5 (human, 2026-10-19). No behaviour change: nothing consumes the read until TASK-145.5.10 and the TASK-145.5.5 cutover.

THIS SLICE
- decisions/workplace-systems.md rule 3: a small platform read that returns each configured WorkplaceSystem (contracts/workplace/, TASK-145.5.3) with its tenant id. Its Protocol and value type live in contracts/workplace/; its implementation is host code in app/server/ (human, 2026-10-19: infrastructure/ is hosting only) and is built from the vendor slices: Slack when SLACK_TEAM_ID is set (app/integrations/slack/settings.py); Google when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set, with GOOGLE_WORKSPACE_CUSTOMER_ID as the tenant. The my_customer alias is never a tenant (TASK-145.5.3): with it, Google is not configured.
- Registered as a core service in app/server/services.py (CORE_SERVICES), with a fake in tests/fixtures/service_registry.py.
- No feature module imports a vendor settings slice; features reach tenant ids only through this read.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The configured-systems Protocol ConfiguredSystems (one read, tenants() returning a read-only Mapping[WorkplaceSystem, str]) lives in contracts/workplace/; its immutable implementation and the settings-to-tenants builder live in app/server/configured_systems.py; it is registered under the Protocol in CORE_SERVICES and built once at phase 2
- [ ] #2 The read returns Slack with the stripped SLACK_TEAM_ID when it is set and Google with the stripped customer id when the service-account key file is set; an unset or blank Slack id, an unset key file, a blank Google id or the my_customer alias leaves that system out (tested for each, including the reader's own guard when a slice is built without validation)
- [ ] #3 The test service registry provides a fake configured-systems read (Slack only by default, overridable per test)
- [ ] #4 No feature module imports a vendor settings slice; lint-imports passes with no new ignore entry and app/pyproject.toml is unchanged
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
DECISIONS
D1 Shape: contracts/workplace/configured_systems.py holds `class ConfiguredSystems(Protocol)` with one method `tenants(self) -> Mapping[WorkplaceSystem, str]`. No separate ConfiguredSystem dataclass: a mapping is the value the three consumers need (145.5.10 passes it straight to RecordIncidentStore; 145.5.5 uses `.get(SLACK)` / `in`; 145.7 uses `len == 1` and `.get(policy_system)`). A dataclass would force each consumer to rebuild the mapping. Re-exported from contracts/workplace/__init__.py.
D2 Implementation (human, 2026-10-19): server/configured_systems.py, host code (plugin-architecture.md: infrastructure/ is hosting only, framework services are host code in server/; workplace-systems.md Checks: no infrastructure package serves a workplace concern). No pyproject change. `StaticConfiguredSystems(tenants: Mapping[...])` copies into a MappingProxyType (immutable; ordered by insertion = SLACK, GOOGLE). `read_configured_systems(slack: SlackSettings, google: GoogleWorkspaceSettings) -> StaticConfiguredSystems` is a pure function over the two narrow slices (no lru_cache, no env access).
D3 Layering: server/ may import integrations and infrastructure, so server.configured_systems -> integrations.slack.settings and infrastructure.configuration.integrations.google are allowed with no new ignore entry. Feature code never sees either slice: (b) and (e) already forbid it. (k) is unaffected (the module imports neither records nor coordination). Shape (human, 2026-10-19): the Mapping of D1, matching RecordIncidentStore's tenants argument and rule 3's one tenant per system.
D4 When: server/services.py adds `CoreService(ConfiguredSystems, _build_configured_systems)` to CORE_SERVICES (47-50); the builder calls read_configured_systems(get_slack_settings(), get_google_workspace_settings()). Those singletons are already validated at boot (lifespan.py:248-249) before initialize_core_services (lifespan.py:262), and _once() (services.py:~57) builds the instance once per registry. No network I/O.
D5 Rules (unchanged validation, reader mirrors it):
 - Slack: TEAM_ID is None (the settings validator turns "" into None; whitespace-only fails boot) -> out. Set -> `TEAM_ID.strip()`; reader also drops a blank result (guard, tested via model_construct). SLACK_ENABLED is irrelevant: tenant entry = enabled (configuration.md, workplace-systems rule 3). Slack-set-but-transport-off is still a configured system.
 - Google: key file falsy -> out (same truthiness as the validator at google.py:~63). Else id = GOOGLE_WORKSPACE_CUSTOMER_ID.strip(); blank or == alias -> out (validator already fails boot, so this is defense in depth). To avoid a second "my_customer" literal, google.py gains a module constant GOOGLE_CUSTOMER_ID_ALIAS used by the field default, the validator and the reader.
D6 Log: one `configured_systems_built` info event with `systems=[names]` (never ids or key-file contents) so an operator sees at boot which systems the instance works with.
D7 Fake: build_fake_service_registry(*, configured_tenants: Mapping[WorkplaceSystem, str] | None = None) registers StaticConfiguredSystems; default {SLACK: "T-FAKE-SLACK"}. The same pure class serves as the fake; there is no second implementation to drift.

STEPS (TDD: tests first, each red then green)
1. contracts/workplace/configured_systems.py (new, Protocol) + contracts/workplace/__init__.py export. [AC1]
2. infrastructure/configuration/integrations/google.py: add GOOGLE_CUSTOMER_ID_ALIAS, use at the field default and the validator (behaviour identical). [AC2, enabling]
3. server/configured_systems.py (new): StaticConfiguredSystems, read_configured_systems, the log event. [AC1, AC2]
4. server/services.py: import, `_build_configured_systems`, CORE_SERVICES entry. [AC1]
5. tests/fixtures/service_registry.py: register the fake with the optional override. [AC3]
6. Gates: ruff; mypy on touched files; `uv run lint-imports` (no ignore entry, pyproject.toml unchanged); pytest tests --ignore=tests/smoke. [AC4, AC5]

TEST MATRIX (layered tree)
tests/unit/server/test_server_configured_systems_read.py [AC2]: both set -> {SLACK:T, GOOGLE:C} in that order; neither set -> empty; Slack only; Google only; Slack id unset, "" env -> out; Slack id padded " T1 " -> "T1"; model_construct Slack TEAM_ID "  " -> out; key file unset + real id -> Google out; key file set + id "my_customer" (model_construct) -> out; key file set + blank id (model_construct) -> out; key file set + padded id -> stripped; SLACK_ENABLED false with id set -> Slack in; result is read-only (assignment raises TypeError) and not affected by later mutation of the input mapping; log event carries system names only (capture_logs).
tests/unit/contracts/workplace/test_contracts_workplace_configured_systems_protocol.py [AC1]: StaticConfiguredSystems is accepted where ConfiguredSystems is typed (typed assignment; mypy is the check) and tenants() returns the mapping consumers read.
tests/unit/server/test_server_services_registration.py (edit in place, line 44 set assertion adds ConfiguredSystems) [AC1]; new tests/unit/server/test_server_services_configured_systems_resolve.py: resolves under the Protocol, is a StaticConfiguredSystems, same instance across two containers of one registry, different across registries; env with Slack id + Google key/real id gives both; an invalid slice never reaches here (boot validation covered by the existing test_lifespan_vendor_slice_validation.py) [AC1, AC2].
tests/unit/server/test_server_services_fixture.py (edit in place) [AC3]: fixture registry resolves the fake with the Slack default; the override replaces it; a fresh registry per call.
Regression: tests/integration/server/test_lifespan_core_services.py and test_lifespan_vendor_slice_validation.py unchanged and green. [AC5]
AC4 evidence: lint-imports output plus `rg "integrations.slack.settings|configuration.integrations.google" app/features app/packages` showing no new hit.

TRACEABILITY
AC1 <- steps 1,3,4 <- protocol test, registration test, resolve test.
AC2 <- steps 2,3 <- read_settings tests.
AC3 <- step 5 <- fixture test.
AC4 <- step 6 (no pyproject edit) <- lint-imports, rg.
AC5 <- step 6.
Every step maps to an AC; step 2 is enabling.

ASSUMPTIONS (verify)
A1 Importing integrations.slack.settings from server.configured_systems causes no import cycle (integrations/slack/__init__ pulls bootstrap -> client). Verify: `cd app && uv run python -I -c "import server.configured_systems"` and the reverse-order import of server.services.
A2 Resolving ConfiguredSystems in tests that build the real registry (test_server_services_registration, lifespan core-service tests) needs only env defaults. Verify by running tests/unit/server and tests/integration/server.
A3 Stripping the stored id is safe (opaque ids never carry edge whitespace). Verify nobody stores the unstripped value: rg SLACK_TEAM_ID / TEAM_ID under app/ (only settings and tests today).
A4 The two SlackSettings classes (infrastructure/configuration/integrations/slack.py legacy vs integrations/slack/settings.py) are distinct; this plan reads only the latter, as the task states.

BLAST RADIUS / ROLLBACK
Additive: no consumer yet. Failure mode is boot failure if the builder raises (it cannot beyond settings construction, already done at lifespan 248-249) or an import cycle (A1). One git revert restores the prior state; no data, env var or manifest change, no ordering constraint.

SIZE
Production files: 5 (configured_systems.py new, contracts __init__, workplace_systems.py new, google.py, server/services.py). LOC about 100 with docstrings, about 55 without. Tests/fixtures excluded: about 5 new/edited test files. One subsystem family (platform read), no mechanical refactor beyond a constant extraction. Verdict: passes the single-PR gate (<400 LOC, <10 files).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-19 15:33
---
Plan approved (human, 2026-10-19) with two decisions: the implementation is host code in app/server/configured_systems.py, not app/infrastructure/ (plugin-architecture.md hosting-only rule, workplace-systems.md Checks); the read is tenants() -> Mapping[WorkplaceSystem, str]. Tenant ids are stripped on read; google.py gains GOOGLE_CUSTOMER_ID_ALIAS.
---
<!-- COMMENTS:END -->
