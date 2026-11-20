---
id: TASK-188
title: CONVERSATION_NAME_ATTEMPTS becomes a typed incident setting
status: In Progress
assignee: []
created_date: '2026-11-18T21:26:00Z'
updated_date: '2026-11-20T13:57:00Z'
labels:
  - incident
dependencies:
  - TASK-145.9.1
ordinal: 530000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
core/domain.py:549 holds CONVERSATION_NAME_ATTEMPTS = 5 as a plain constant. The rule recorded with TASK-145.9.1 (decisions/configuration.md, human 2026-11-18): plain constants are avoided unless the value must never change; a candidate-count bound is tunable, so it becomes a typed setting with default 5 on the incident settings slice, read at call time. Single small PR from main; no behaviour change at the default.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The conversation-name candidate bound is a typed setting with default 5 in config/base.toml, read at call time; the constant is deleted
- [x] #2 ruff, mypy, lint-imports, make check-settings-key-ownership and the targeted tests pass
- [x] #3 decisions/incident-management.md and decisions/configuration.md name [incident_core] conversation_name_attempts (default 5) instead of a fixed five attempts
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded on main 3d7264fc (2026-11-20). Branch task-188-conversation-name-attempts from an up-to-date main. Small single PR (one subsystem: features/incident core + response wiring; ~6 production files, ~40 production LOC); size gate not tripped.

Decision (owning slice): [incident_core] conversation_name_attempts, int, default 5, ge=1.
- The bound belongs to the naming policy every caller shares, not to one caller: declare (response/service/conversation.py ensure_conversation, TASK-145.7.9) and the later attach-a-conversation path (TASK-165.5, coordinated incidents, decisions/incident-management.md:36 "attaching a conversation later ... reuses it") both consume incident_conversation_names. [incident_core] is the slice every incident subdomain already reads (common/settings.py; response reads it in plugin.py:54, legacy_upgrade_job.py:37, entrypoints/scope.py:21), so no second owner appears when TASK-165.5 lands.
- Program-scope check (2026-11-20): no ADR gap. incident-management.md:36 places the naming policy, its five candidates included, in core/domain.py, so the count belongs to core; configuration.md:55 puts a bound on the owning slice and configuration.md:167 moves a value once to its end-state owner; incident-management.md:87 and configuration.md:81 put a slice read by two or more subdomains in common/settings.py, where IncidentCoreSettings already lives. Precedents on [incident_core]: timeline_update_attempts (TASK-145.9.1), full_read_max_items (TASK-145.5.7, read by response's upgrade job), new_incident_system (read by response/plugin.py). The key stays correct whether the loop stays in response/ or moves to core/ (see the TASK-165.5 note).
- Domain purity: feature-packages.md:36 and its 2026-11-06 line (domain.py holds pure rules), testing.md:20 (unit tests are pure logic); precedent DeclarePolicy.from_settings (TASK-145.7.9) carries [incident_response] values into the service. The production caller of declare_policy arrives with TASK-165.2 (HTTP route, doc-16 L9a).
- Rejected: [incident_response]. It fits today's only caller (DeclarePolicy is built from it), but TASK-165.5 would then read another subdomain's key or duplicate it.
- Domain stays settings-free (decisions/configuration.md: a test sets values through the slice; core/domain.py imports no settings today): the count is an argument, read at call time by the provider that builds the declare policy.

Steps
1. features/incident/common/settings.py: add IncidentCoreSettings.conversation_name_attempts: int = Field(default=5, ge=1, description="Most candidate names one incident's conversation is tried under: the first, then -2 onward; a name proven another's moves to the next."); add it to the class docstring key list.
2. config/base.toml [incident_core]: conversation_name_attempts = 5 with a one-line comment.
3. features/incident/core/domain.py: delete CONVERSATION_NAME_ATTEMPTS and its docstring; incident_conversation_names(title, opened_on, *, production, attempts: int) returns attempts names, ValueError when attempts < 1; ConversationName.__post_init__ refuses attempt < 1 only (the upper bound is the caller's count, no longer a module constant); docstrings updated.
4. features/incident/core/api.py: drop CONVERSATION_NAME_ATTEMPTS from the import and __all__.
5. features/incident/response/service/declare.py: DeclarePolicy gains conversation_name_attempts: int; from_settings(settings, *, production, conversation_name_attempts) passes it (or from_settings takes the core slice; pick the narrower int at implementation); _Run.conversation passes attempts=self._policy.conversation_name_attempts.
6. features/incident/response/providers.py declare_policy: reads get_incident_core_settings().conversation_name_attempts at call time.
7. decisions/incident-management.md:36 "returns five ConversationName values ... attempts 1 to 5" -> "returns [incident_core] conversation_name_attempts values (default 5)"; Changes line. decisions/configuration.md Decision paragraph: name the second bound ([incident_core] conversation_name_attempts, TASK-188); Changes line. features/incident/response/README.md if it names five attempts (check at implementation).
8. Tests (TDD, failing first), then the gates.

Test matrix
- tests/unit/features/incident/common/test_incident_common_settings_load.py: default is 5 (happy); a configured value is read (override via monkeypatched env INCIDENT_CORE__CONVERSATION_NAME_ATTEMPTS); 0 fails boot naming conversation_name_attempts (boundary/failure); key list fixture gains the key.
- tests/unit/features/incident/core/test_incident_core_conversation_names.py: N names in attempt order for attempts=N (replaces the ==5 pin); attempts=1 gives one unsuffixed name (boundary); attempts=0 raises ValueError (failure); ConversationName(attempt=0) refused, attempt=6 accepted (bound moved to the caller).
- tests/unit/features/incident/core/test_incident_core_conversation_slack_names.py:65: compares with the passed count instead of the constant.
- tests/unit/features/incident/core/test_incident_core_api_surface.py: CONVERSATION_NAME_ATTEMPTS leaves the expected surface.
- tests/unit/features/incident/response/test_incident_response_declare_run.py: POLICY gains conversation_name_attempts=5; a policy with 2 and every name another's claims exactly 2 names and ends CONVERSATION_NAME_TAKEN (bound honoured end to end).
- provider read at call time: a test that a changed [incident_core] value reaches declare_policy() without a restart (settings cache cleared through the existing fixture), in the declare-run file or test_incident_response_providers_build.py if one exists.

AC traceability: AC#1 -> steps 1-6, tests settings_load/conversation_names/declare_run/provider; AC#2 -> gates; AC#3 -> step 7.

Gates: ruff and targeted tests during TDD; make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams; then full mypy, then full pytest (tests --ignore=tests/smoke), once each, sequential.

Assumptions / doubts
- declare_policy (providers.py:76) has no production caller yet (the rebuilt declare entrypoint is a later Stack L/M row), so the declare path is dark: no behaviour change in production at any value. Verify: rg declare_policy at implementation.
- No legacy (app/modules) code builds conversation names from the constant (rg found none). slack_conversation_label (core/adapters/slack.py:333) builds attempt 1 only and is unaffected.
- No environment file sets the key; default 5 equals today's constant.

Blast radius and rollback: merging deploys a new [incident_core] key with the current value; a bad value fails boot by validation (ge=1) naming the key, not at first declare. No terraform/IAM/SSM/env-name change, so no deploy-checks run. One git revert restores the constant.
Domain-model evolution gate: not applicable (no entity shape change; ConversationName keeps its fields, only its upper-bound check moves to the caller).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-20: plan approved (human): OQ1 [incident_core] conversation_name_attempts default 5, ge=1; OQ2 domain stays settings-free, the count passed as an argument and read by providers.declare_policy at call time. Out of scope, recorded elsewhere: closing an incident (TASK-189), the conversation loop's placement for coordination/ (TASK-165.5 note).

2026-11-20: Implemented (TDD) on task-188-conversation-name-attempts from main 3d7264fc, as approved. [incident_core] conversation_name_attempts (int, default 5, ge=1) in common/settings.py and config/base.toml; CONVERSATION_NAME_ATTEMPTS deleted from core/domain.py and core/api.py; incident_conversation_names takes attempts (ValueError below 1); ConversationName refuses attempt < 1 only; DeclarePolicy carries conversation_name_attempts, from_settings takes it, providers.declare_policy reads it from the core slice at each call; incident-management.md:36 and configuration.md (Decision paragraph) name the key, a Changes line in each. Tests: settings default, override, below-one rejected, base.toml table; names for a given count, a single attempt, count below one refused, attempt 6 valid; declare stops at a policy bound of 2 with CONVERSATION_NAME_TAKEN and no third name created; provider reads the bound at call time (new test_incident_response_declare_policy_build.py). Gates: ruff OK; ruff format on the touched files; contracts 15 kept; key ownership OK; package shape OK (3 baselined); test seams OK (47/12 baselined); mypy 40 errors in 13 files, the baseline, none in touched files; pytest 7926 passed. Dark: declare_policy has no production caller until TASK-165.2; no terraform/IAM/SSM/env-name change, no deploy-checks.
<!-- SECTION:NOTES:END -->
