---
id: TASK-145.5.3
title: >-
  Incident vocabulary, record and references in common/ and core/domain.py, with
  the incident core settings and the platform tenant ids
status: Done
assignee: []
created_date: '2026-10-14 23:09'
updated_date: '2026-10-15 17:30'
labels:
  - incident
  - features
dependencies:
  - TASK-153
references:
  - decisions/incident-management.md
  - decisions/workplace-systems.md
  - decisions/people-and-accounts.md
  - decisions/feature-packages.md
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 389000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 4 of Stack K (handoff doc-13). Implements against the vendor enablement ADR text from TASK-153, committed earlier on the same layer. Additive types and settings plus the boot-time validation of the vendor slices; no I/O and no consumer yet.

THIS SLICE
- contracts/workplace/: the closed WorkplaceSystem enum (slack, google). It is platform vocabulary, not incident vocabulary: the configured-systems read (workplace-systems.md rule 3, built by TASK-145.5.5) returns it and platform code cannot import a feature (human, 2026-10-15).
- common/vocabulary.py: IncidentStatus (Open, In Progress, Ready to be Reviewed, Reviewed, Closed; every status except Closed counts as open), Severity (levels 0 to 4, wide because teams use different scales), the five role names, StatusUpdateStage moved from core/domain.py (core/api.py keeps exporting it). common/ imports no adapter, store or provider module; import-linter contract (i) gains common below core.
- core/domain.py, frozen dataclasses: Incident (title, product, severity, security flag, declarer, status, declared, detection, impact start, impact end, the five roles) and the typed references (conversation, report, video call, postmortem meeting, external case, source alert), each with system, tenant, vendor id and the vendor link; TimelineEntry as its own record. Times are timezone-aware. The system is checked strictly at construction (cloud-portability.md contract 4).
- Tenant ids (workplace-systems.md rules 3 and 4, configuration.md vendor enablement, people-and-accounts.md:45,85): a tenant is the vendor's real identifier, never an invented label or an API alias. Writers take it from the event payload (Slack team_id, Teams tenantId) from TASK-145.7 on. For mapping legacy items, which carry bare ids, it comes from the vendor's tenant entry, interim until TASK-112: SLACK_TEAM_ID in app/integrations/slack/settings.py, and the real GOOGLE_WORKSPACE_CUSTOMER_ID (not the my_customer alias). Features reach these ids only through the configured-systems read (TASK-145.5.5), never by importing a vendor slice.
- Interim signals (configuration.md tolerated list): SLACK_ENABLED is the Slack transport switch, not vendor enablement; switched on, it requires SLACK_TEAM_ID. With the transport off, SLACK_TEAM_ID is optional and only shape-checked when present (human, 2026-10-15). Google is in use when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set, and then GOOGLE_WORKSPACE_CUSTOMER_ID must be the real customer id. Tenant ids are opaque: Slack and Google document no format, so only blank values and aliases are rejected. An invalid vendor slice fails boot (plugins.md boot-failure table), so lifespan's configuration phase builds both slices.
- common/settings.py: incident core settings (incidents and timeline table names, defaulting to the provisioned tables) and the new-incident system policy (incident-management.md:73), which names a system, not a tenant id, and is unset by default. Other settings slices arrive with the layers that consume them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 common/vocabulary.py defines IncidentStatus, Severity, the role names and StatusUpdateStage; lint-imports enforces that common/ imports no adapter, store or provider module
- [x] #2 The incident core settings carry the incidents and timeline table names with the provisioned names as defaults
- [x] #3 core/domain.py defines the frozen Incident (title, product, severity, security flag, declarer, status, declared, detection, impact start, impact end, the five roles, optional typed references), TimelineEntry, and the six reference types, each reference carrying system, tenant, vendor id and vendor link; every datetime is rejected when naive and a system that is not a WorkplaceSystem member is rejected at construction
- [x] #4 StatusUpdateStage is defined once, in common/vocabulary.py; core/api.py still exports it and every existing status-update test passes unchanged
- [x] #5 SlackSettings requires a non-blank SLACK_TEAM_ID when SLACK_ENABLED (the interim transport switch) is true; with the transport off the id is optional, an empty value counts as absent and a present value must be non-blank; the id is opaque (no format regex, per Slack's documentation) and no network call is made
- [x] #6 GoogleWorkspaceSettings rejects a blank GOOGLE_WORKSPACE_CUSTOMER_ID and the my_customer alias when Google is in use (GCP_SRE_SERVICE_ACCOUNT_KEY_FILE set), requires nothing otherwise, applies no format regex and makes no network call
- [x] #7 The incident core settings carry the new-incident system policy as a closed WorkplaceSystem naming a system, not a tenant id, unset by default (resolved later against the configured systems); an unknown system fails validation
- [x] #8 contracts/workplace/ defines the closed WorkplaceSystem (slack, google); contracts stays a leaf (lint-imports contract (c)) and workplace-systems.md names it as the enum's home
- [x] #9 Lifespan's configuration phase builds the Slack and Google slices, so a Slack transport switched on without SLACK_TEAM_ID or a Google key file with the my_customer alias fails boot naming the key before plugins load, and absent vendor entries boot with no network call
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope: additive types and settings, and the vendor slices validated at boot. No I/O, no store, no consumer. One subsystem (app/), about 12 production files (four of them one-liners: an empty __init__.py, the pyproject contract line, the README layout line, the ADR line) and about 400 production lines incl. docstrings. Single-PR gate: borderline on files, pass on lines and subsystems; the one-line files are not split out because each belongs to the change it documents (human approval of the plan covers this). One git revert restores the previous state.

Decisions (human, 2026-10-15):
- Vendor enablement follows TASK-153 (layer 4): a configured tenant entry enables a vendor; until the entries and configuration files exist (TASK-112), SLACK_ENABLED is the interim Slack transport switch and a set GCP_SRE_SERVICE_ACCOUNT_KEY_FILE the interim Google signal.
- Tenant ids are opaque non-blank strings: Slack and Google document no id format (Slack: code must not assume the characters or length of an id), so no regex; Google's my_customer API alias is rejected. SLACK_TEAM_ID is the workspace (team) id; an Enterprise Grid id is a separate field and is not accepted in its place by contract (not checked).
- SLACK_TEAM_ID with the transport off: optional; an empty value counts as absent; a present value must be non-blank. No secret is required for it while the transport is off (TASK-24/TASK-112 tighten this with the real tenant entry).
- WorkplaceSystem is a closed StrEnum in contracts/workplace/ (platform vocabulary; the configured-systems read returns it). Strict where a value is chosen (settings, record construction: a reference rejects a value that is not a member). Tolerant reads of stored values belong to the store (TASK-145.5.4); a new member ships in readers one deploy before writers.
- The configured-systems read (system -> tenant id of configured vendors) is built by TASK-145.5.5 where the store is built; this slice only makes the tenant ids exist and validate. The incident feature never imports a vendor settings slice.
- Severity is an IntEnum SEV0..SEV4; unset is None on the record, never a member.
- The five roles are named optional fields on Incident; IncidentRole gives generic access.
- core/api.py exports the new record types now.
- The new-incident policy names a system and is unset by default (incident-management.md:73 as amended by TASK-153). Resolving it against the configured systems happens where the store is built (TASK-145.5.5), not in this slice.

Structure:
- contracts/workplace/ is a new contracts package (contract (c): contracts imports nothing else from the app). features/ and integrations/ may import it (contract (d) allows contracts).
- common/ is a new directory under features/incident (feature-packages.md: vocabulary and settings tree, no I/O). Contract (i) gains a bottom layer: layers = ["comms | documents | drive | meet | scheduling | scribe", "core", "common"], exhaustive stays true. Layering forbids common -> core/comms; contract (b) forbids infrastructure/server; contract (e) forbids integrations outside adapters/.
- Subdomains import common/ directly; core/api.py re-exports StatusUpdateStage (existing public name) plus the new record types (Incident, TimelineEntry, the six reference types) and WorkplaceSystem is imported from contracts.workplace by whoever needs it (not re-exported).
- Table names and the policy live in IncidentCoreSettings (common/settings.py, env prefix INCIDENT_CORE__, singleton get_incident_core_settings, same style as comms/settings.py). The status_updates table name is added by TASK-145.5.6, not here.

STEPS
1. contracts/workplace/__init__.py (empty) and contracts/workplace/systems.py (new): WorkplaceSystem(StrEnum): SLACK="slack", GOOGLE="google" (more members arrive with their adapters). Docstring cites workplace-systems.md rules 3 and 4 and cloud-portability.md contract 4.
2. features/incident/common/__init__.py (empty) and common/vocabulary.py (new):
   - IncidentStatus(StrEnum): OPEN="Open", IN_PROGRESS="In Progress", READY_TO_BE_REVIEWED="Ready to be Reviewed", REVIEWED="Reviewed", CLOSED="Closed"; property is_open (every status except Closed).
   - Severity(IntEnum): SEV0..SEV4, value = level.
   - IncidentRole(StrEnum): incident_commander, operations_lead, communications_lead, policy_lead, postmortem_owner.
   - StatusUpdateStage moved verbatim from core/domain.py:44-55.
3. common/settings.py (new): IncidentCoreSettings(BaseSettings) with INCIDENTS_TABLE (default "incidents", alias INCIDENT_CORE__INCIDENTS_TABLE), TIMELINE_TABLE (default "sre_bot_incident_timeline", alias INCIDENT_CORE__TIMELINE_TABLE), NEW_INCIDENT_SYSTEM: WorkplaceSystem | None (default None, alias INCIDENT_CORE__NEW_INCIDENT_SYSTEM; incident-management.md:73); non-blank table-name validation; get_incident_core_settings lru_cache provider. Defaults match terraform/dynamodb.tf:92 and :154.
4. core/domain.py: drop the StatusUpdateStage class and import it from common.vocabulary (StatusUpdate at core/domain.py:~112 uses it). Add frozen dataclasses:
   - ResourceReference base (system: WorkplaceSystem, tenant: str, vendor_id: str, url: str | None); __post_init__ rejects a system that is not a WorkplaceSystem member (isinstance check, no coercion of plain strings) and blank tenant and vendor_id (workplace-systems.md rule 4). Six thin subclasses so each is its own type: ConversationReference, ReportReference, VideoCallReference, PostmortemMeetingReference, ExternalCaseReference, SourceAlertReference.
   - Incident: id, title, status (IncidentStatus member, checked), declarer, declared_at, product, severity (Severity member or None, checked), security_flag (existing IncidentSecurityFlag), detected_at, impact_started_at, impact_ended_at, the five roles (str | None) and the six optional references. __post_init__: blank id/title rejected; every datetime must be timezone-aware (same check as StatusUpdate at core/domain.py:~140).
   - TimelineEntry: incident_id, entry_id, posted_at (aware), author, text, source_message: optional message reference (system, tenant, conversation id, message id; system checked like ResourceReference) so the capture key in TASK-145.5.4 can derive uuid5; blank incident_id/entry_id rejected.
5. core/api.py: import StatusUpdateStage from common.vocabulary (still in __all__); add Incident, TimelineEntry and the six reference types to imports and __all__. No provider or Protocol change (TASK-145.5.4/5.5).
6. app/integrations/slack/settings.py: add TEAM_ID: str | None (alias SLACK_TEAM_ID, description). A field validator turns an empty string into None (absent). Extend the existing _validate_transport_credentials model_validator: when ENABLED, TEAM_ID is required; whenever TEAM_ID is present it must be non-blank after strip (opaque, no format regex); error messages name SLACK_TEAM_ID. Update the module docstring (SLACK_ENABLED = interim transport switch, SLACK_TEAM_ID = interim tenant entry).
7. app/infrastructure/configuration/integrations/google.py (current Google home until TASK-24): add a model_validator on GoogleWorkspaceSettings. When GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is non-empty (the only credential signal the client reads, integrations/google_workspace/client.py:135), GOOGLE_WORKSPACE_CUSTOMER_ID must be non-blank and not "my_customer" (opaque, no format regex); the message names the key. Unconfigured (CI, local, tests): no check, default unchanged (TASK-24 removes the alias default). Update the class docstring. The directory provider (infrastructure/directory/factory.py:61) keeps working: the Directory API accepts the real id.
8. server/lifespan.py: the configuration phase (beside get_app_settings, get_server_settings, get_directory_settings) also calls get_google_workspace_settings(), so an invalid Google slice fails boot before plugins load, as the Slack slice already does through get_slack_provider() (lifespan.py:265). Google is otherwise built lazily (directory factory, talent google_drive import, first client call). No secret value is logged.
9. pyproject.toml: contract (i) layers gain "common"; no ignore_imports change.
10. decisions/workplace-systems.md rule 4: one sentence naming contracts/workplace/ as WorkplaceSystem's home (ADR is otherwise silent); Changes row. features/incident/README.md: add common/ to the layout if it lists directories (verify at implementation).

TESTS (new files under tests/unit and tests/integration, layered tree; legacy files edited in place only)
- tests/unit/contracts/workplace/test_contracts_workplace_system_members.py: members and values; unknown value raises.
- tests/unit/features/incident/common/: test_incident_common_vocabulary_status.py (is_open for all five; Closed alone is not open; values), test_incident_common_vocabulary_severity.py (levels 0-4, ordering, no sev-5), test_incident_common_vocabulary_role.py (five names), test_incident_common_settings_load.py (defaults equal the provisioned names, env override, blank rejected, policy default None, accepts slack and google, rejects an unknown system).
- tests/unit/features/incident/core/: test_incident_core_incident_record.py (valid Incident, defaults None, naive datetime rejected for each of the four timing fields, blank id/title, status and severity must be members, frozen), test_incident_core_reference_types.py (each of six requires system, tenant, vendor id; blank tenant rejected; a plain string or unknown system rejected; distinct types), test_incident_core_timeline_entry_record.py (aware posted_at, blank ids, source_message system checked).
- tests/unit/integrations/slack/test_slack_settings_team_id_validate.py: transport on without id or with a blank id fails naming SLACK_TEAM_ID; on with any non-blank id passes, including one longer than 11 characters; off with no id passes; off with an empty id passes as absent; off with a whitespace-only id fails naming the key; no network (constructing settings only). In-place edits to tests/unit/integrations/slack/test_slack_settings.py where a test sets SLACK_ENABLED=true (lines ~66, 73, 127-199) to also set SLACK_TEAM_ID.
- tests/unit/infrastructure/configuration/test_google_workspace_settings_customer_id_validate.py: key file set + my_customer fails; key file set + blank fails; key file set + any other non-blank id passes; key file empty + default passes; explicit real id with key file empty passes.
- tests/integration/server/test_lifespan_vendor_slice_validation.py (configuration.md Checks: boot test): Slack transport on without SLACK_TEAM_ID fails startup naming the key; Google key file set with my_customer fails startup naming the key; both absent boots with the vendors unconfigured; no network (stubs as in test_lifespan.py).
- In-place: tests/unit/features/incident/core/test_incident_core_api_surface.py (expected __all__ gains the new names; StatusUpdateStage identity is common.vocabulary's).
- Existing status-update tests must pass unchanged (AC4).

AC TRACEABILITY
- AC1: steps 2, 9 | test_incident_common_vocabulary_*; lint-imports kept (plus a one-off temporary common -> core import to see contract (i) break, not committed; record in notes).
- AC2: step 3 | test_incident_common_settings_load.
- AC3: steps 4, 5 | test_incident_core_incident_record, _reference_types, _timeline_entry_record, api_surface.
- AC4: steps 2, 4, 5 | api_surface plus the existing status-update suites.
- AC5: step 6 | test_slack_settings_team_id_validate.
- AC6: step 7 | test_google_workspace_settings_customer_id_validate.
- AC7: step 3 | test_incident_common_settings_load.
- AC8: steps 1, 10 | test_contracts_workplace_system_members; lint-imports contract (c).
- AC9: step 8 | test_lifespan_vendor_slice_validation.
Every step maps to an AC.

ASSUMPTIONS AND DOUBTS
- The production Slack workspace id (auth.test team_id) and Google customer id (Admin console, Account settings > Profile) are known before deploy; they go into sre-bot-config SSM (see blast radius).
- GCP_SRE_SERVICE_ACCOUNT_KEY_FILE non-empty means Google is in use. Verify with rg that no environment sets the key file but legitimately relies on my_customer for directory calls (dev .env, SSM sre-bot-config).
- Existing tests that build SlackSettings with ENABLED true must gain SLACK_TEAM_ID; found by rg "SLACK_ENABLED|ENABLED=True" in app/tests (pytest env sets SLACK_ENABLED=false, pyproject.toml:133, so most are unaffected). The lifespan tests' env must not set the Google key file with my_customer; verify by running the full suite.
- The other two SLACK_ENABLED definitions (infrastructure/configuration/integrations/slack.py, infrastructure/configuration/infrastructure/platforms.py) do not drive the transport and are removed by TASK-24; untouched here.

BLAST RADIUS AND ROLLBACK
- Deployment prerequisite (ordering): before this merges and deploys, SLACK_TEAM_ID and the real GOOGLE_WORKSPACE_CUSTOMER_ID must be present in the production, staging and dev configuration (the sre-bot-config SSM parameter that app/bin/entry.sh writes to .env; not managed by terraform). Otherwise boot fails with a message naming the key. Local .env files of developers with Google or Slack enabled need the same two keys.
- Nothing else reads the new fields yet; domain types and settings have no consumers. The only runtime risk is a missing id or the alias in an environment with the vendor in use, which fails closed at boot naming the key. A typo'd id is not caught here; writers compare it with the event payload from TASK-145.7.
- One git revert of the PR restores the previous behavior; the SSM keys left in place are ignored (extra="ignore").

GATES (from app/): ruff check ., ruff format --check, lint-imports, mypy on touched files (repo-wide errors elsewhere ignored, record 0 in touched), pytest tests --ignore=tests/smoke.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-15 with TDD (all new tests failed first: missing modules, missing TEAM_ID field, no Google check).
- contracts/workplace/ (systems.py + __init__ export): WorkplaceSystem slack, google.
- features/incident/common/: vocabulary.py (IncidentStatus with is_open, Severity SEV0-4, IncidentRole, StatusUpdateStage moved verbatim), settings.py (IncidentCoreSettings: INCIDENT_CORE__INCIDENTS_TABLE default incidents, INCIDENT_CORE__TIMELINE_TABLE default sre_bot_incident_timeline, INCIDENT_CORE__NEW_INCIDENT_SYSTEM default None; get_incident_core_settings).
- core/domain.py: ResourceReference and six subclasses, Incident, MessageReference, TimelineEntry; strict isinstance checks for system, status, severity; aware-time and blank-text helpers, also reused by StatusUpdate (same messages). core/api.py exports the new types; MessageReference is exported too (TimelineEntry.source_message needs it; not named in the plan).
- integrations/slack/settings.py: TEAM_ID (SLACK_TEAM_ID); empty counts as absent; present must be non-blank; required when SLACK_ENABLED.
- infrastructure/configuration/integrations/google.py: GoogleWorkspaceSettings rejects blank and my_customer when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set.
- server/lifespan.py: configuration phase calls get_slack_settings() and get_google_workspace_settings() before the logger and core services.
- pyproject.toml: contract (i) layers gain common; pytest env gains GOOGLE_WORKSPACE_CUSTOMER_ID=C0test0id (the pytest env sets the key file).
- decisions/workplace-systems.md rule 4 names contracts/workplace/ (Changes row). features/incident/README.md: common/ row, layers sentence, domain.py types.
- In-place test edits: test_slack_settings.py (SLACK_TEAM_ID beside each SLACK_ENABLED=true; deprecated from __future__ import annotations removed), test_settings_structure.py (alias default test clears the key file), test_incident_core_api_surface.py (new exports, StatusUpdateStage identity).
AC1 probe: a temporary common/settings.py -> core.api import made lint-imports report '(i) Incident subdomains are independent siblings over core BROKEN ... features.incident.common is not allowed to import features.incident.core'; reverted, 12 kept.

Gates (2026-10-15, from app/):
- uv run ruff check . -> All checks passed!; uv run ruff format --check . -> 950 files already formatted
- uv run lint-imports -> Contracts: 12 kept, 0 broken.
- uv run mypy <touched files> -> 0 errors in touched files (18 pre-existing in untouched infrastructure/i18n, integrations/slack/channels.py, modules/incident/utils.py, ignored)
- uv run pytest tests --ignore=tests/smoke -> 4998 passed

Deploy prerequisite: sre-bot-config SSM needs SLACK_TEAM_ID (SLACK_ENABLED=true) and the real GOOGLE_WORKSPACE_CUSTOMER_ID (ECS injects GCP_SRE_SERVICE_ACCOUNT_KEY_FILE), else boot fails naming the key.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-15 16:56
---
2026-10-15 (human): revised plan approved in chat, including the review against TASK-153 (WorkplaceSystem in contracts/workplace/, configured-systems read in TASK-145.5.5, SLACK_TEAM_ID shape-checked with the transport off) and AC 9 kept in this layer despite the borderline file count.
---

created: 2026-10-15 17:30
---
2026-10-15 (human): prod SSM checked before deploy. sre-bot-config has SLACK_ENABLED=true and a real GOOGLE_WORKSPACE_CUSTOMER_ID (not my_customer); SLACK_TEAM_ID lives in sre-bot-config-infrastructure, which app/bin/entry.sh appends to the same .env, so both new boot checks are satisfied. The deploy prerequisite in the plan and notes covers both parameters.
---
<!-- COMMENTS:END -->
