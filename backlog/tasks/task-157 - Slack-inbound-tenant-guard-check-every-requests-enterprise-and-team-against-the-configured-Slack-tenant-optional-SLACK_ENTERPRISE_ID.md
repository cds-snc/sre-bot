---
id: TASK-157
title: >-
  Slack inbound tenant guard: check every request's enterprise and team against
  the configured Slack tenant; optional SLACK_ENTERPRISE_ID
status: To Do
assignee: []
created_date: '2026-10-20 18:35'
updated_date: '2026-10-20 23:36'
labels:
  - security
  - slack
  - phase-4
dependencies:
  - TASK-111.9
references:
  - decisions/workplace-systems.md
  - decisions/transport-slack.md
  - decisions/configuration.md
  - 'https://docs.slack.dev/enterprise/developing-for-enterprise-orgs'
  - 'https://openid.net/specs/openid-connect-core-1_0.html'
  - 'https://github.com/cds-snc/sre-bot/issues/1758'
ordinal: 406000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Standalone PR from main (doc-2: a security behaviour change merges and deploys alone). Decided 2026-10-20 (human) after a review of the SLACK_TEAM_ID introduction against industry practice; recorded in decisions/workplace-systems.md rules 3 and 4, transport-slack.md (Verification) and configuration.md.

WHY. SLACK_TEAM_ID is the expected tenant, the single-tenant pattern of an OpenID Connect client that configures its issuer and rejects tokens from any other (OIDC Core 5.7). Today it is never checked: a wrong value is stamped onto references and makes IncidentStore.find_by_conversation miss silently, and no request is compared with it. Nothing persists a tenant yet (the cutover stamps legacy items on read; status updates carry none), so the check must land before the first persisting writers: TASK-145.5.7 (upgrade job, apply) and TASK-145.7 (declare writers).

WHAT
- integrations/slack/settings.py: optional ENTERPRISE_ID (SLACK_ENTERPRISE_ID), Slack's org id; SLACK_ENABLED=true requires SLACK_TEAM_ID or SLACK_ENTERPRISE_ID (an org-wide install has no workspace); same blank and opaque-id rules as TEAM_ID. Docstring and field descriptions say the ids are verified per request.
- server/configured_systems.py slack_tenant: the Enterprise org id when configured, otherwise the team id (Slack advises keying org data by enterprise_id).
- Slack runtime (host code, after request verification): a global Bolt middleware compares the request's enterprise_id and team_id (Bolt context) with the configured ids. A configured id must match; a request naming an Enterprise org the settings do not name is refused. A mismatch acks where Slack requires an ack, answers a short ephemeral notice where a response URL exists, runs no listener, and logs slack_tenant_mismatch (error) with the expected and received ids. Boot makes no network call.
- No change to stored data: TASK-145.5.7 checks auth.test before apply.

OUT OF SCOPE. Re-stamping stored tenants after a Grid migration (a job planned when it happens; the guard refusing every request is its signal). Deriving the tenant from auth.test at boot (rejected: boot stays free of network calls, TASK-112).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SLACK_ENABLED=true boots with SLACK_TEAM_ID, with SLACK_ENTERPRISE_ID, or with both, and fails naming the keys with neither; blank values are rejected and no format is checked
- [ ] #2 The configured Slack tenant (ConfiguredSystems.tenants()[SLACK]) is the enterprise id when SLACK_ENTERPRISE_ID is set, otherwise the team id
- [ ] #3 Every inbound Slack request (command, action, view, event) whose enterprise_id or team_id does not match a configured id, or that names an Enterprise org the settings do not name, runs no listener, is acked where required, gets an ephemeral notice where a response URL exists, and logs slack_tenant_mismatch at error with the expected and received ids; a matching request passes unchanged
- [ ] #4 decisions/transport-slack.md, workplace-systems.md and configuration.md match the shipped behaviour; the settings docstring states the per-request check
- [ ] #5 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with commands and output recorded in notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 (TASK-24.5): the Slack tenant entry is SlackTenant (integrations/slack/settings.py), read through SlackSettings.tenant, with team_id and a tenant_id read. Add the optional enterprise_id inside it, make team_id optional, and make tenant_id the enterprise id when set; server/configured_systems.py already reads tenant_id and does not change. Production (2026-10-20): team T2G2S06PM, enterprise_id null, is_enterprise_install false, no SLACK_ENTERPRISE_ID set.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-20 23:27
---
2026-10-20 (TASK-111 planning): SLACK_ENTERPRISE_ID lands as a flat env name here (interim, per decisions/configuration.md's tolerated list); TASK-111.9 moves it into [slack.tenant] in the configuration files. In the doc-11 queue this task now runs after TASK-111, so if 111.9 has merged, read it from the files directly.
---

created: 2026-10-20 23:27
---
2026-10-20 correction to the previous comment: the doc-11 queue runs all of TASK-111 first, so TASK-111.9 has merged when this task starts. Add the optional enterprise id as enterprise_id in [slack.tenant] in the configuration files (lower snake_case field, no flat SLACK_ENTERPRISE_ID env name); the inbound guard reads it from the Slack tenant entry.
---
<!-- COMMENTS:END -->
