---
id: TASK-24.5
title: Add the Google and Slack tenant entries
status: In Progress
assignee: []
created_date: '2026-10-19 17:19'
updated_date: '2026-10-20 20:26'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies:
  - TASK-24.3
  - TASK-24.4
  - TASK-145.5.5
references:
  - decisions/configuration.md
  - decisions/workplace-systems.md
parent_task_id: TASK-24
priority: medium
ordinal: 403000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 of TASK-24 (decisions/configuration.md: vendor enablement is the presence of a tenant entry; workplace-systems.md rule 3). The behaviour change of TASK-24:
- Google: GOOGLE_WORKSPACE_CUSTOMER_ID loses its my_customer default; a tenant entry (SubModel | None) in integrations/google_workspace/settings.py is present when the service-account key file is set and carries the real customer id; a present entry missing a secret or the id fails boot naming the variable.
- Slack: SLACK_TEAM_ID becomes the Slack tenant entry; SLACK_ENABLED stays the interim transport switch until TASK-112, and the transport on without a tenant entry fails boot naming the key.
- server/configured_systems.py reads the tenant entries in its Google and Slack TenantSource rows.
TASK-24.4 already deleted app/infrastructure/configuration/integrations/. GoogleResourcesConfig (also in integrations/google_workspace/settings.py) is feature data, not a vendor slice, and stays until TASK-111.
No <VENDOR>_ENABLED key. Env names unchanged (renames in TASK-111); TASK-112 moves the tenant entries into the configuration files.

Merge order (human, 2026-10-19): only after TASK-145.5.5 (Stack K layer 9, the incident cutover) has deployed and been checked, so the cutover runs on the tenant configuration production already has. The cutover is the first real consumer of the configured-systems read. Never in the same deploy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GOOGLE_WORKSPACE_CUSTOMER_ID has no default; the Google slice's tenant entry (GoogleWorkspaceTenant) is present when the key file or the customer id is set, carries the real customer id, and a present entry missing either fails boot naming the variable
- [x] #2 The Slack slice's tenant entry (SlackTenant) carries SLACK_TEAM_ID and a tenant_id read, so TASK-157 adds the optional enterprise id inside the entry without changing its readers; Slack transport on without it fails boot naming SLACK_TEAM_ID
- [x] #3 server/configured_systems.py and the directory factory read the tenant entries only; the my_customer fallback is gone from the directory provider; tests cover present, absent and invalid entries
- [x] #4 Each vendor has exactly one vendor settings slice (GoogleResourcesConfig is feature data, tolerated until TASK-111)
- [x] #5 decisions/configuration.md's interim list records the derived entries and the Google presence rule; TASK-111, TASK-157 and TASK-24.6 reflect the entry shape
- [x] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decisions (human, 2026-10-20)
- Entry shape: the end-state sub-model type, derived in the interim. Frozen pydantic sub-models SlackTenant and GoogleWorkspaceTenant (decisions/configuration.md: SubModel | None, read from env and later TOML, so the I/O-boundary type), exposed by each slice as a read-only `tenant: X | None` built from the flat fields after validation. The flat fields stay declared until TASK-111 (pydantic-settings reads only declared fields; env renames are TASK-111's), which then promotes `tenant` to the real nested field (<SLICE>__TENANT__<FIELD>) and drops the flat ones. Readers use only the entry, so TASK-111 and TASK-157 change no reader.
- Google presence: the entry is present when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE or GOOGLE_WORKSPACE_CUSTOMER_ID is set; a present entry requires both and fails boot naming the missing one (configuration.md "a present entry requires its secrets"; the TASK-112 end state, where a configured Google table without its key secret fails boot). Gives TASK-24.6 AC2 its Google case.
- Slack: SlackTenant(team_id) with a `tenant_id` read returning team_id. TASK-157 adds the optional enterprise_id, makes team_id optional and changes tenant_id to the Enterprise org id when set, all inside the entry. No enterprise id here. Production: team T2G2S06PM, no Enterprise org (notes, 2026-10-20).

Steps
1. integrations/slack/settings.py: add `class SlackTenant(BaseModel)` (frozen; team_id: str described as auth.test team_id; property tenant_id -> team_id, docstring: Slack's tenant id, the pair's resolution lives here). SlackSettings gains `tenant` (property returning SlackTenant | None, from the validated TEAM_ID, stripped). Validator unchanged in behaviour (blank rejected; ENABLED without the entry fails naming SLACK_TEAM_ID). Module docstring: TEAM_ID is read into the tenant entry; the entry is the expected tenant (per-request check TASK-157).
2. integrations/google_workspace/settings.py: GOOGLE_WORKSPACE_CUSTOMER_ID: str | None = None (empty string -> None, like TEAM_ID); add `class GoogleWorkspaceTenant(BaseModel)` (frozen; customer_id: str; service_account_key: str with repr=False, matching the field it copies; SecretStr typing is TASK-156's). Validator: either key set -> both non-blank, customer id not my_customer; each failure names its variable. `tenant` property returns the entry or None. Docstrings updated (no default, presence rule).
3. integrations/google_workspace/client.py _build_service: read the key from settings.tenant; absent entry raises ValueError("Google Workspace is not configured: GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and GOOGLE_WORKSPACE_CUSTOMER_ID are unset") before json.loads, and logs google_workspace_not_configured.
4. infrastructure/directory/google.py: customer_id becomes a required str (drop the my_customer default and the `or "my_customer"` fallback; workplace-systems rule 3: never an API alias). infrastructure/directory/factory.py get_directory_provider: customer_id from the Google entry, "" when absent (no credentials then, so no call sends it; dev boot without Google keeps building the default google directory provider), with a one-line comment.
5. server/configured_systems.py: slack_tenant returns settings.tenant.tenant_id or None; google_tenant returns settings.tenant.customer_id or None. Module docstring: sources read the vendor tenant entries.
6. decisions/configuration.md interim list (line 85): the interim tenant entries are derived from the flat env fields (Slack SLACK_TEAM_ID; Google present when its key file or customer id is set, both then required) until TASK-111 makes them nested fields; dated history line. Line 20 is Context (state before the decision) and stays.
7. Sync siblings via CLI: TASK-111 description gains "the derived tenant entries (SlackSettings.tenant, GoogleWorkspaceSettings.tenant, TASK-24.5) become nested fields read as <SLICE>__TENANT__<FIELD>, and the flat fields go"; TASK-157 notes: entry shape ready (add enterprise_id and change tenant_id inside SlackTenant; configured_systems unchanged); TASK-24.6 notes: Google missing-credential case is customer id set without the key file.
8. Docs: features/incident/comms/README.md line 51 unchanged (still names SLACK_TEAM_ID); pyproject pytest env already sets both Google keys.

Test matrix (TDD, failing first)
- tests/unit/integrations/slack/test_slack_settings_team_id_validate.py (extend): entry present with stripped team id and tenant_id == team id; absent when unset or empty; blank rejected naming SLACK_TEAM_ID; ENABLED without it fails naming SLACK_TEAM_ID; entry is frozen.
- tests/unit/integrations/google_workspace/test_google_workspace_settings_customer_id_validate.py (extend): no default (unset -> None, entry absent); both set -> entry with the real id; key only -> fails naming GOOGLE_WORKSPACE_CUSTOMER_ID; id only -> fails naming GCP_SRE_SERVICE_ACCOUNT_KEY_FILE; my_customer and blank rejected; entry repr hides the key.
- tests/unit/integrations/google_workspace/test_google_workspace_client.py (edit in place): absent entry raises the not-configured error without parsing.
- tests/unit/infrastructure/directory/test_factory.py (edit in place): factory passes the entry's customer id; "" when absent. The provider default removal is checked by mypy (every construction passes customer_id); no new test.
- tests/unit/server/test_server_configured_systems_read.py (edit): sources build from the entries; present, absent and invalid (validator rejects) per vendor; _google helper default changes from my_customer.
- tests/integration/server/test_lifespan_vendor_slice_validation.py (extend): Google customer id without key file fails boot naming GCP_SRE_SERVICE_ACCOUNT_KEY_FILE.

AC traceability
- AC1 -> steps 2, 4 -> Google settings tests, factory test, lifespan test.
- AC2 -> step 1 -> Slack settings tests, lifespan test (existing).
- AC3 -> step 5 -> configured_systems tests.
- AC4 -> steps 2-3 (no new slice; GoogleResourcesConfig untouched) -> grep in notes.
- AC5 -> gates. AC6 -> steps 6-7 -> doc diff, task views.

Size: 7 production files (2 settings, client, 2 directory, configured_systems, 1 ADR), about 110 LOC; one concern (vendor settings and their readers). Under the gate.

Assumptions to verify
- Production and staging set GOOGLE_WORKSPACE_CUSTOMER_ID with the key file (the current validator already requires it when the key is set, so production does). An environment setting only the customer id now fails boot naming the key file: human check of the sre-bot-config parameters for dev/staging before deploy.
- No reader of GOOGLE_WORKSPACE_CUSTOMER_ID beyond factory.py:61 and configured_systems.py:53 (rg, 2026-10-20).

Blast radius and rollback: a wrong presence rule fails boot (visible at deploy, one git revert restores). Directory calls keep the configured id; only the unused alias fallback goes. No data change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 (SLACK_TEAM_ID review): the Slack tenant entry is the expected tenant, Slack's pair in Slack's terms: SLACK_TEAM_ID and the optional SLACK_ENTERPRISE_ID added by TASK-157 (the Enterprise org id is the tenant when set). Line 30 and AC2 read with that: the entry carries both ids, transport on with neither fails boot naming the keys. The per-request check is TASK-157's, not this task's.

2026-10-20 (production facts, for this task and TASK-157): auth.test returns team "GC Digital", team_id T2G2S06PM, enterprise_id null, is_enterprise_install false. SLACK_TEAM_ID in sre-bot-config-infrastructure matches T2G2S06PM. Production sets no SLACK_ENTERPRISE_ID. So the production Slack tenant entry is the team id alone; the enterprise id stays TASK-157's to add.

2026-10-20 (implementation):
- Entries: SlackTenant (team_id, tenant_id read) in integrations/slack/settings.py and GoogleWorkspaceTenant (customer_id, service_account_key repr=False) in integrations/google_workspace/settings.py, frozen pydantic sub-models exposed as the read-only SlackSettings.tenant and GoogleWorkspaceSettings.tenant, built from the validated flat fields (a property, so model_construct test slices work too).
- Google: GOOGLE_WORKSPACE_CUSTOMER_ID is str | None with no default (empty means absent). Either key set makes the entry present; the key without a real id fails naming GOOGLE_WORKSPACE_CUSTOMER_ID, the id without the key fails naming GCP_SRE_SERVICE_ACCOUNT_KEY_FILE.
- Readers: server/configured_systems.py (slack_tenant reads tenant_id, google_tenant reads customer_id), infrastructure/directory/factory.py (entry id, empty when absent: no key then, so no call sends it), integrations/google_workspace/client.py (key from the entry; absent entry raises naming both keys and logs google_workspace_not_configured). GoogleDirectoryProvider takes a required customer_id; the my_customer default and fallback are gone.
- Touched-file cleanup: test_google_workspace_client.py imported its module through importlib in a fixture; now a top-level import.
- AC4: rg 'class .*Settings' in integrations/slack and integrations/google_workspace: SlackSettings; GoogleWorkspaceSettings plus GoogleResourcesConfig (feature data, until TASK-111). No reader of the flat tenant fields remains outside the two slices.
- AC5: decisions/configuration.md interim list and a dated change line; TASK-111, TASK-157 and TASK-24.6 notes record the entry shape.
- Gates (from app/): uv run ruff check . -> All checks passed!; ruff format --check on touched files -> 14 files already formatted; uv run lint-imports -> Contracts: 12 kept, 0 broken; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 48 errors in 19 files, none in touched files (pre-existing); uv run pytest tests --ignore=tests/smoke -> 5405 passed.
- Deploy check (human): any environment that sets GOOGLE_WORKSPACE_CUSTOMER_ID without GCP_SRE_SERVICE_ACCOUNT_KEY_FILE now fails boot naming the key file; check the dev and staging sre-bot-config parameters before deploy. Production sets both.
<!-- SECTION:NOTES:END -->
