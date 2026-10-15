---
id: TASK-145.5.3
title: >-
  Incident vocabulary, record and references in common/ and core/domain.py, with
  the incident core settings and the platform tenant ids
status: To Do
assignee: []
created_date: '2026-10-14 23:09'
updated_date: '2026-10-15 16:32'
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
Layer 4 of Stack K (handoff doc-13). Implements against the vendor enablement ADR text from TASK-153, committed earlier on the same layer. Additive types and settings; no I/O and no consumer yet.

THIS SLICE
- common/vocabulary.py: IncidentStatus (Open, In Progress, Ready to be Reviewed, Reviewed, Closed; every status except Closed counts as open), Severity (levels 0 to 4, wide because teams use different scales), the five role names, StatusUpdateStage moved from core/domain.py (core/api.py keeps exporting it). common/ imports no adapter, store or provider module; import-linter contract (i) gains common below core.
- core/domain.py, frozen dataclasses: Incident (title, product, severity, security flag, declarer, status, declared, detection, impact start, impact end, the five roles) and the typed references (conversation, report, video call, postmortem meeting, external case, source alert), each with system, tenant, vendor id and the vendor link; TimelineEntry as its own record. Times are timezone-aware.
- Tenant (human, 2026-10-14; decisions/workplace-systems.md rules 3 and 4, people-and-accounts.md:45,85): a tenant is the vendor's own identifier, never an invented label. Writers take it from the event payload (Slack team_id, Teams tenantId) from TASK-145.7 on. For mapping legacy items, which carry bare ids, the value comes from platform-owned settings: SLACK_TEAM_ID in app/integrations/slack/settings.py, and the real Google Workspace customer id (not the my_customer API alias). When the vendor is enabled (SLACK_ENABLED), its tenant id is required and validated at boot by the settings validator, with no network call. Google has no enabled flag; under TASK-153 Google is configured when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set (interim, until the tenant entry exists), and then GOOGLE_WORKSPACE_CUSTOMER_ID must be the real customer id, not the my_customer alias (human, 2026-10-15). Tenant ids are opaque: Slack and Google document no format, so only blank values and aliases are rejected.
- common/settings.py: incident core settings (incidents and timeline table names, defaulting to the provisioned tables) and the new-incident system policy (incident-management.md:73), which names a system, not a tenant id. Other settings slices arrive with the layers that consume them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 common/vocabulary.py defines IncidentStatus, Severity, the role names and StatusUpdateStage; lint-imports enforces that common/ imports no adapter, store or provider module
- [ ] #2 The incident core settings carry the incidents and timeline table names with the provisioned names as defaults
- [ ] #3 core/domain.py defines the frozen Incident (title, product, severity, security flag, declarer, status, declared, detection, impact start, impact end, the five roles, optional typed references), TimelineEntry, and the six reference types, each reference carrying system, tenant, vendor id and vendor link; every datetime is rejected when naive
- [ ] #4 StatusUpdateStage is defined once, in common/vocabulary.py; core/api.py still exports it and every existing status-update test passes unchanged
- [ ] #5 SlackSettings requires a non-blank SLACK_TEAM_ID at boot when SLACK_ENABLED is true and ignores it when Slack is disabled; the id is opaque (no format regex, per Slack's documentation) and no network call is made
- [ ] #6 GoogleWorkspaceSettings rejects a blank GOOGLE_WORKSPACE_CUSTOMER_ID and the my_customer alias when Google is configured (GCP_SRE_SERVICE_ACCOUNT_KEY_FILE set), requires nothing otherwise, applies no format regex and makes no network call
- [ ] #7 The incident core settings carry the new-incident system policy as a closed WorkplaceSystem naming a system, not a tenant id, unset by default (resolving later to the only configured system); an unknown system fails validation
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope: additive types and settings only. No I/O, no store, no consumer. One subsystem (app/), about 9 production files, about 370 production lines (incl. docstrings). Single-PR gate: pass. One git revert restores the previous state.

Decisions (human, 2026-10-15):
- Vendor enablement follows TASK-153 (layer 4): a configured tenant entry enables a vendor; until the entries and configuration files exist, SLACK_ENABLED and a set GCP_SRE_SERVICE_ACCOUNT_KEY_FILE are the interim signals.
- Tenant ids are opaque non-blank strings: Slack and Google document no id format (Slack: code must not assume the characters or length of an id), so no regex; Google's my_customer API alias is rejected. SLACK_TEAM_ID is the workspace (team) id; an Enterprise Grid id is a separate field and is not accepted in its place by contract (not checked).
- WorkplaceSystem is a closed StrEnum, strict where a value is chosen (settings, record construction). Tolerant reads of stored values belong to the store (TASK-145.5.4); a new member ships in readers one deploy before writers.
- Severity is an IntEnum SEV0..SEV4; unset is None on the record, never a member.
- The five roles are named optional fields on Incident; IncidentRole gives generic access.
- core/api.py exports the new record types now.
- The new-incident policy names a system and is unset by default (incident-management.md:73 as amended by TASK-153): unset resolves to the only configured system, so an instance without Google (or without Slack) needs no override. Resolving it against the configured systems happens where the store is built (TASK-145.5.5), not in this slice.

Structure:
- common/ is a new directory under features/incident (feature-packages.md: vocabulary and settings tree, no I/O). Contract (i) gains a bottom layer: layers = ["comms | documents | drive | meet | scheduling | scribe", "core", "common"], exhaustive stays true. Layering forbids common -> core/comms (so no adapter, store or provider module of either); contract (b) forbids infrastructure/server; contract (e) forbids integrations outside adapters/.
- Subdomains import common/ directly; core/api.py re-exports StatusUpdateStage only (existing public name) plus the new record types (Incident, TimelineEntry, the six reference types) so the later store and consumers have one door.
- Tenant ids are platform-owned settings read by whoever builds the store (TASK-145.5.4/5.5 pass them in at construction); this slice only makes them exist and validate. core/ never imports integrations/ or infrastructure/.
- Table names live in IncidentCoreSettings (common/settings.py, env prefix INCIDENT_CORE__, singleton get_incident_core_settings, same style as comms/settings.py). The status_updates table name is added by TASK-145.5.6, not here.

STEPS
1. common/__init__.py (empty) and common/vocabulary.py (new):
   - WorkplaceSystem(StrEnum): SLACK="slack", GOOGLE="google" (more members arrive with their adapters).
   - IncidentStatus(StrEnum): OPEN="Open", IN_PROGRESS="In Progress", READY_TO_BE_REVIEWED="Ready to be Reviewed", REVIEWED="Reviewed", CLOSED="Closed"; property is_open (every status except Closed).
   - Severity(IntEnum): SEV0..SEV4, value = level; "unset" is None on the record, never a member.
   - IncidentRole(StrEnum): incident_commander, operations_lead, communications_lead, policy_lead, postmortem_owner.
   - StatusUpdateStage moved verbatim from core/domain.py:44-55.
2. common/settings.py (new): IncidentCoreSettings(BaseSettings) with INCIDENTS_TABLE (default "incidents", alias INCIDENT_CORE__INCIDENTS_TABLE), TIMELINE_TABLE (default "sre_bot_incident_timeline", alias INCIDENT_CORE__TIMELINE_TABLE), NEW_INCIDENT_SYSTEM: WorkplaceSystem | None (default None = the only configured system, alias INCIDENT_CORE__NEW_INCIDENT_SYSTEM; incident-management.md:73); non-blank table-name validation; get_incident_core_settings lru_cache provider. Defaults match terraform/dynamodb.tf:92 and :154.
3. core/domain.py: drop the StatusUpdateStage class and import it from common.vocabulary (StatusUpdate at core/domain.py:~112 uses it). Add frozen dataclasses:
   - ResourceReference base (system: WorkplaceSystem, tenant: str, vendor_id: str, url: str | None); __post_init__ rejects blank tenant and vendor_id (workplace-systems.md rule 4: never a bare vendor id). Six thin subclasses so each is its own type: ConversationReference, ReportReference, VideoCallReference, PostmortemMeetingReference, ExternalCaseReference, SourceAlertReference.
   - Incident: id, title, status, declarer, declared_at, product, severity, security_flag (existing IncidentSecurityFlag), detected_at, impact_started_at, impact_ended_at, the five roles (incident_commander, operations_lead, communications_lead, policy_lead, postmortem_owner: str | None) and the six optional references. __post_init__: blank id/title rejected; every datetime must be timezone-aware (same check as StatusUpdate at core/domain.py:~140).
   - TimelineEntry: incident_id, entry_id, posted_at (aware), author, text, source_message: ConversationReference-style optional message reference (system, tenant, conversation id, message id) so the capture key in TASK-145.5.4 can derive uuid5; blank incident_id/entry_id rejected.
4. core/api.py: import StatusUpdateStage from common.vocabulary (still in __all__); add Incident, TimelineEntry and the six reference types to imports and __all__. No provider or Protocol change (those are TASK-145.5.4/5.5).
5. app/integrations/slack/settings.py: add TEAM_ID: str | None (alias SLACK_TEAM_ID, description). Extend the existing _validate_transport_credentials model_validator (or a sibling after-validator): when ENABLED, TEAM_ID is required and must be non-blank after strip (opaque, no format regex); error message names SLACK_TEAM_ID. Disabled: no check. Update module docstring.
6. app/infrastructure/configuration/integrations/google.py (current single Google home until TASK-24): add a model_validator on GoogleWorkspaceSettings. When GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is non-empty (Google is configured; the only credential signal the client reads, integrations/google_workspace/client.py:135), GOOGLE_WORKSPACE_CUSTOMER_ID must be non-blank and not "my_customer" (opaque, no format regex); message names the key. Unconfigured (CI, local, tests): no check, default unchanged. Update the class docstring ("defaults to my_customer" now qualified). The directory provider (infrastructure/directory/factory.py:61) keeps working: the Directory API accepts the real id.
7. pyproject.toml: contract (i) layers gain "common"; no ignore_imports change.
8. features/incident/README.md: add common/ to the layout if it lists directories (verify at implementation).

TESTS (new files under tests/unit, layered tree; legacy files edited in place only)
- tests/unit/features/incident/common/__init__.py; test_incident_common_vocabulary_status.py (is_open for all five; Closed alone is not open; values), test_incident_common_vocabulary_severity.py (levels 0-4, ordering, no sev-5), test_incident_common_vocabulary_role.py (five names), test_incident_common_settings_load.py (defaults equal the provisioned names, env override, blank rejected, system policy default None, accepts slack and google, rejects an unknown system).
- tests/unit/features/incident/core/test_incident_core_incident_record.py (valid Incident, defaults None, naive datetime rejected for each of the four timing fields, blank id/title, frozen), test_incident_core_reference_types.py (each of six requires system, tenant, vendor id; blank tenant rejected; distinct types), test_incident_core_timeline_entry_record.py (aware posted_at, blank ids).
- tests/unit/integrations/slack/test_slack_settings_team_id_validate.py: enabled without id or with a blank id fails naming SLACK_TEAM_ID; enabled with any non-blank id passes, including one longer than 11 characters (no format assumed); disabled with no id passes; no network (constructing settings only). In-place edits to tests/unit/integrations/slack/test_slack_settings.py where a test sets SLACK_ENABLED=true (lines ~66, 73, 127-199) to also set SLACK_TEAM_ID.
- tests/unit/infrastructure/configuration/test_google_workspace_settings_customer_id_validate.py: key file set + my_customer fails; key file set + blank fails; key file set + any other non-blank id passes; key file empty + default passes; explicit real id with key file empty passes.
- In-place: tests/unit/features/incident/core/test_incident_core_api_surface.py (expected __all__ gains the new names; StatusUpdateStage identity is common.vocabulary's).
- Existing status-update tests must pass unchanged (AC4).

AC TRACEABILITY
- AC1: steps 1, 7 | test_incident_common_vocabulary_*; lint-imports kept (plus a one-off temporary common -> core import to see contract (i) break, not committed; record in notes).
- AC2: step 2 | test_incident_common_settings_load.
- AC3: steps 3, 4 | test_incident_core_incident_record, _reference_types, _timeline_entry_record, api_surface.
- AC4: steps 1, 3, 4 | api_surface plus the existing status-update suites.
- AC5: step 5 | test_slack_settings_team_id_validate.
- AC6: step 6 | test_google_workspace_settings_customer_id_validate.
- AC7: step 2 | test_incident_common_settings_load.
Every step maps to an AC (step 8 is documentation of step 1/7).

ASSUMPTIONS AND DOUBTS
- The production Slack workspace id (auth.test team_id) and Google customer id (Admin console, Account settings > Profile) are known before deploy; they go into sre-bot-config SSM (see blast radius).
- GCP_SRE_SERVICE_ACCOUNT_KEY_FILE non-empty means Google is in use. Verify with rg that no environment sets the key file but legitimately relies on my_customer for directory calls (dev .env, SSM sre-bot-config).
- Existing tests that build SlackSettings with ENABLED true must gain SLACK_TEAM_ID; found by rg "SLACK_ENABLED|ENABLED=True" in app/tests (pytest env sets SLACK_ENABLED=false, pyproject.toml:133, so most are unaffected). Verify by running the full suite.
- ENABLED Slack with the old infrastructure/configuration SlackSettings (integrations/slack.py) is a different class that TASK-24 removes; untouched here.
- The README and plugin-architecture docs need no ADR change: common/ and its contents are already specified in incident-management.md and feature-packages.md.

BLAST RADIUS AND ROLLBACK
- Deployment prerequisite (ordering): before this merges and deploys, SLACK_TEAM_ID and the real GOOGLE_WORKSPACE_CUSTOMER_ID must be present in the production, staging and dev configuration (the sre-bot-config SSM parameter that app/bin/entry.sh writes to .env; not managed by terraform). Otherwise boot fails with a message naming the key. Local .env files of developers with Google or Slack enabled need the same two keys.
- Nothing else reads the new fields yet; domain types and settings have no consumers. The only runtime risk is a missing id or the alias in an environment with the vendor configured, which fails closed at boot naming the key. A typo'd id is not caught here; writers compare it with the event payload from TASK-145.7.
- One git revert of the PR restores the previous behavior; the SSM keys left in place are ignored (extra="ignore").

GATES (from app/): ruff check ., ruff format --check, lint-imports, mypy on touched files (repo-wide errors elsewhere ignored, record 0 in touched), pytest tests --ignore=tests/smoke.
<!-- SECTION:PLAN:END -->
