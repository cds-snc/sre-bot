---
id: TASK-153
title: >-
  Vendor enablement: a configured tenant entry enables a vendor client; amend
  the configuration, workplace-systems, plugins, lifecycle and
  incident-management ADRs
status: Done
assignee: []
created_date: '2026-10-15 16:06'
updated_date: '2026-10-19 15:27'
labels:
  - decisions
  - configuration
dependencies: []
references:
  - decisions/configuration.md
  - decisions/workplace-systems.md
  - decisions/plugins.md
  - decisions/lifecycle.md
  - decisions/incident-management.md
priority: medium
type: task
ordinal: 394000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Part of layer 4 of Stack K (handoff doc-13): ADR text only, no code, committed on the TASK-145.5.3 branch before that task's revised plan (human, 2026-10-15: a planning-only refinement is not its own layer). TASK-145.5.3 implements against the amended text.

PROBLEM
- No ADR says how a vendor client (integrations/<vendor>/) is enabled: integrations are clients, not plugins, so the per-entry-point enablement key (configuration.md:37) never reaches them.
- SLACK_ENABLED is an environment variable (configuration.md:35 keeps env vars for secrets and deployment identity), is defined in three slices with three defaults, and mixes two meanings: run the Slack transport, and have a Slack workspace.
- Google has no flag; it is in use when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set, and GOOGLE_WORKSPACE_CUSTOMER_ID defaults to the my_customer API alias, not a tenant id.
- incident-management.md:73 has the new-incident policy name a tenant; the incident core settings name a system.

DECISIONS (human, 2026-10-15)
- A vendor client is available when its settings slice holds a tenant entry (Backstage-style presence of configuration, pydantic SubModel | None, later a list). There is no <VENDOR>_ENABLED key. A present entry requires its secrets and is shape-checked at boot with no network call; an absent entry means the vendor is not configured. An invalid vendor slice fails boot, like a capability slice.
- The entry carries the vendor's real tenant id, never an alias (Google my_customer; Microsoft common, organizations, consumers, domain names). Format checks follow vendor documentation only: Slack and Google document no format, so their ids are opaque non-blank strings (aliases rejected); Microsoft documents a GUID.
- The Slack transport is host code with a real on/off switch: it gets a plugin-style enablement key in the configuration files. Until the configuration files exist (TASK-112), SLACK_ENABLED is the interim switch and SLACK_TEAM_ID is required when it is on.
- Features check their policies against the configured systems when they are built (a small configured-systems read), never by importing another slice; a feature whose policy names an unconfigured system is skipped and the event names the key.
- The incident new-incident policy names a system; it resolves to that system's single configured tenant. A (system, tenant) pair is deferred until an instance has several tenants of one system.
- Settings values that are persisted (WorkplaceSystem on references) are closed enums validated strictly where they are chosen; stored records are read tolerantly (an unknown value is kept, not a crash), and a new member ships in readers one deploy before any writer.

PRIOR ART (2026-10-15)
- Backstage integrations: https://backstage.io/docs/integrations/
- Netflix Dispatch plugin instances: https://github.com/Netflix/dispatch/blob/main/src/dispatch/plugin/models.py
- pydantic-settings nested models: https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/
- OpenFeature (runtime flags are not static vendor setup): https://openfeature.dev/docs/reference/intro
- Slack ids are opaque: https://docs.slack.dev/changelog/2016/08/11/user-id-format-changes ; Google customer id: https://knowledge.workspace.google.com/admin/getting-started/find-your-customer-id ; Entra tid is a GUID: https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference
- Closed vs open enums on persisted data: https://google.aip.dev/126 , https://protobuf.dev/programming-guides/enum/
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 configuration.md states the vendor enablement rule: a tenant entry in the vendor's slice enables its client, no <VENDOR>_ENABLED key, secrets required only for a present entry, static shape checks, an invalid vendor slice fails boot, and one owning slice per vendor key
- [x] #2 workplace-systems.md rule 3 states that each tenant entry carries the vendor's real tenant id, never an API alias, with format checks taken from vendor documentation only; features learn the configured systems through a read API, never by importing another slice
- [x] #3 plugins.md and lifecycle.md give a platform transport an enablement key in the configuration files, record SLACK_ENABLED as its interim form until TASK-112, and the boot-failure table gains the invalid vendor slice row
- [x] #4 incident-management.md:73 says the new-incident policy names a system that resolves to its single configured tenant, and that the incident feature is skipped when that system is not configured
- [x] #5 The persisted-enum rule (strict where chosen, tolerant on read, readers before writers) is recorded in the ADR that owns domain records, with sources cited
- [x] #6 TASK-24, TASK-112 and TASK-145.5.3 to TASK-145.5.5 descriptions are consistent with the amended ADRs (edited through the CLI where stale)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope: ADR text only (five to six files under decisions/, plus task descriptions through the CLI). No code, no tests; gates still run to prove nothing else moved. Single-PR gate: pass (no production LOC). One git revert restores the previous text. Drafted by the architecture agent (mandatory web refresh for ADRs older than 30 days; sources already gathered in the description).

STEPS
1. decisions/configuration.md: add a "Vendor enablement" rule after the plugin enablement rule (line 37): a vendor client is available when its integrations/<vendor>/settings.py slice holds a tenant entry (SubModel | None, a list once several tenants exist); no <VENDOR>_ENABLED key; secrets required only for a present entry; static presence and shape checks, no network; an invalid vendor slice fails boot. Context (line 15) gains the three SLACK_ENABLED definitions and Google's implicit enablement. Checks gain: no settings field named <VENDOR>_ENABLED in integrations/ (SLACK_ENABLED excepted until TASK-112). Migration: Slack keys move to one owner (TASK-24); the tenant entries move to the configuration files with TASK-112.
2. decisions/workplace-systems.md rule 3 (line 41): each tenant entry carries the vendor's real tenant id, never an API alias (my_customer; common, organizations, consumers, domain names); format checks from vendor documentation only (Slack, Google: opaque non-blank; Microsoft: GUID); features read the configured systems through a configured-systems read API, never another slice. Cite the vendor pages.
3. decisions/plugins.md: the boot-failure table (line 57) gains the row "Vendor slice fails validation: abort" and a sentence that a platform transport (Slack Socket Mode / HTTP host) has an enablement key in the configuration files. decisions/lifecycle.md: the configuration phase validates vendor slices with the host slices; SLACK_ENABLED is recorded as the interim transport switch until TASK-112. decisions/transport-slack.md:29 cross-reference if its fail-fast sentence needs the team id.
4. decisions/incident-management.md:73: the new-incident policy names a system, resolves to that system's single configured tenant, and the incident feature is skipped (event names the key) when the system is not configured; a (system, tenant) pair waits for an instance with several tenants of one system.
5. decisions/cloud-portability.md (records contract): persisted enum values are strict where chosen (settings, record construction) and tolerant on read (an unknown stored value is kept and logged, never a crash); a new member ships in readers one deploy before any writer. Cite AIP-126 and the protobuf enum guide.
6. Task sync through the CLI: TASK-24 (single Slack slice, SLACK_ENABLED de-duplicated, Google default no longer the alias), TASK-112 (tenant entries and the transport key in the configuration files), TASK-145.5.4 (tolerant WorkplaceSystem read; tenant ids from the configured entries), TASK-145.5.5 (the policy checked against the configured systems when the store is built). Edit only where a description is stale; record each edit in the notes.
7. Each touched ADR: date bumped, status unchanged (Accepted amendments), links valid.

AC TRACEABILITY
- AC1: step 1. AC2: step 2. AC3: step 3. AC4: step 4. AC5: step 5. AC6: step 6. Step 7 is hygiene for steps 1 to 5.

VERIFICATION
- Read-back of each amended section against the decisions in the description; rg for "tenant" in incident-management.md and workplace-systems.md shows no contradiction left; rg for SLACK_ENABLED in decisions/ shows only the interim mention.
- Markdown links resolve (rg the relative links, check files exist).
- Gates from app/ (no code change expected): ruff check ., mypy on touched files (none), pytest tests --ignore=tests/smoke unchanged.

ASSUMPTIONS
- cloud-portability.md owns the records contract (RecordStore); verify while drafting, else use the ADR that does.
- No ADR other than those listed states vendor enablement; verify with rg "ENABLED|enablement" decisions/.

BLAST RADIUS
- Documentation only; TASK-145.5.3 implements against it. Revert restores the previous text; dependent task descriptions would then be re-synced.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
ADR text only (all dates bumped to 2026-10-15, status unchanged), sources from the task description.
- configuration.md: Context gains the three SLACK_ENABLED definitions and Google's implicit enablement; new rule "Vendor enablement is the presence of a tenant entry" (no <VENDOR>_ENABLED key, secrets required only for a present entry, static shape checks, invalid vendor slice fails boot, platform transport has a config-file key); fail-fast sentence names vendor slices; Checks gain a vendor boot test and a grep; Migration lists TASK-112 and SLACK_ENABLED as tolerated; Changes row.
- workplace-systems.md: rule 3 gains real tenant id (no alias), format checks from vendor docs only (Slack/Google opaque, Microsoft GUID, sources cited), configured-systems read API; rule 4 points to strict-on-choice / tolerant-on-read; Changes row.
- plugins.md: transport enablement key sentence, boot-failure row "Vendor slice fails validation: abort | abort", SLACK_ENABLED tolerated item, Changes row.
- lifecycle.md: phase 1 validates vendor slices with host slices; SLACK_ENABLED interim tolerated item; Changes row.
- transport-slack.md:29: transport enablement key, interim SLACK_ENABLED, SLACK_TEAM_ID required when on.
- incident-management.md:73: policy names a system, resolves to its single configured tenant, feature skipped (event names the key) when unconfigured, (system, tenant) pair deferred; Changes row.
- cloud-portability.md (owns RecordStore, contract 4): persisted-enum paragraph (strict where chosen, tolerant on read, readers one deploy before writers), AIP-126 and protobuf enum guide cited; Changes row.
Task descriptions edited via CLI (stale against the ADRs): TASK-24 (single Slack slice, SLACK_ENABLED once, Google customer id no longer the my_customer alias); TASK-112 (tenant entries and transport key move to config files); TASK-145.5.4 (tolerant WorkplaceSystem read, tenant ids from configured entries); TASK-145.5.5 (policy checked against configured systems where the store is built, feature skipped when unconfigured). TASK-145.5.3 untouched.
Verification: rg SLACK_ENABLED decisions/ shows only interim/context mentions; rg for doc-6/doc-8/doc-11/Handbook/Runbook in decisions/ is empty; relative .md links in the seven ADRs all resolve; rg tenant in incident-management.md and workplace-systems.md shows no contradiction. No code changed, so ruff/mypy/pytest gates were not run.

Gates (2026-10-15, from app/, ADR and task text only): ruff check . -> All checks passed!; pytest tests --ignore=tests/smoke -> 4901 passed; mypy not run (no Python file touched, 0 in touched files).

2026-10-15 follow-up (human review of boot behaviour): plugins.md, transport-slack.md and lifecycle.md now state that a transport switched on without its vendor's tenant entry fails boot naming the key, and that an absent entry with the transport off is an unconfigured vendor, never a failure. incident-management.md:73: the new-incident policy is unset by default and resolves to the only configured system; the feature is skipped when the named system is unconfigured, none is configured, or the policy is unset with several configured. Synced TASK-145.5.5 (resolution rule) and TASK-145.5.3 (AC 7, plan step 2 and its settings test). ACs 3 and 4 re-verified against the new text.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-15 16:13
---
2026-10-15 (human): plan approved (agreed with the intent); folded into layer 4 as an earlier commit on the TASK-145.5.3 branch, not its own layer.
---

created: 2026-10-19 15:27
---
2026-10-19 (human, TASK-145.5.5 planning): decisions/incident-management.md amended. The new-incident policy is resolved only by the declare path at startup (TASK-145.7 AC9). A failed resolution leaves declare unregistered instead of skipping the whole feature: production configures Slack and Google with the policy unset, so the feature-wide skip would have removed every incident command at the cutover.
---
<!-- COMMENTS:END -->
