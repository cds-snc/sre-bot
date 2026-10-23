---
id: TASK-157
title: >-
  Slack inbound tenant guard: check every request's enterprise and team against
  the configured Slack tenant; optional [slack.tenant] enterprise_id
status: To Do
assignee: []
created_date: 2026-10-20 18:35
updated_date: '2026-10-23T17:07:00Z'
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
  - https://docs.slack.dev/enterprise/developing-for-enterprise-orgs
  - https://openid.net/specs/openid-connect-core-1_0.html
  - https://github.com/cds-snc/sre-bot/issues/1758
ordinal: 406000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Standalone PR from main (doc-2: a security behaviour change merges and deploys alone), after TASK-111.9. Rules: decisions/workplace-systems.md rules 3 and 4, transport-slack.md (Verification), configuration.md.

WHY. The [slack.tenant] entry is the expected tenant, the single-tenant pattern of an OpenID Connect client that configures its issuer and rejects tokens from any other (OIDC Core 5.7). Nothing checks it yet: no Bolt middleware compares a request's team or enterprise with it (server/configured_systems.py:45 only reads the entry; integrations/slack/settings.py:10 leaves the per-request check to this task), so a wrong value is stamped onto references and makes IncidentStore.find_by_conversation miss silently. Nothing persists a tenant yet, so the check must land before the first persisting writers: TASK-145.5.7 (upgrade job, apply) and TASK-145.7 (declare writers).

WHAT
- integrations/slack/settings.py SlackTenant: an optional enterprise_id beside team_id in [slack.tenant] (env SLACK__TENANT__ENTERPRISE_ID), Slack's Enterprise org id; team_id becomes optional and the entry needs team_id or enterprise_id (an org-wide install has no workspace); same blank and opaque-id rules as team_id. tenant_id is the enterprise id when set, otherwise the team id (Slack advises keying org data by enterprise_id); server/configured_systems.py slack_tenant reads tenant_id and does not change. Docstrings and field descriptions say the ids are verified per request.
- The transport switched on ([slack_transport] enabled, TASK-112) requires the tenant entry through the cross-slice Slack rule in server/configuration/host_configuration.py; that rule accepts team_id, enterprise_id or both.
- Slack runtime (host code, after request verification): a global Bolt middleware compares the request's enterprise_id and team_id (Bolt context) with the configured ids. A configured id must match; a request naming an Enterprise org the settings do not name is refused. A mismatch acks where Slack requires an ack, answers a short ephemeral notice where a response URL exists, runs no listener, and logs slack_tenant_mismatch (error) with the expected and received ids. Boot makes no network call.
- No change to stored data: TASK-145.5.7 checks auth.test before apply.

OUT OF SCOPE. Re-stamping stored tenants after a Grid migration (a job planned when it happens; the guard refusing every request is its signal). Deriving the tenant from auth.test at boot (rejected: boot stays free of network calls, TASK-112).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With [slack_transport] enabled, boot succeeds with [slack.tenant] team_id, enterprise_id, or both, and fails naming the keys with neither; blank values are rejected and no format is checked
- [ ] #2 The configured Slack tenant (ConfiguredSystems.tenants()[SLACK]) is the enterprise id when [slack.tenant] enterprise_id is set, otherwise the team id
- [ ] #3 Every inbound Slack request (command, action, view, event) whose enterprise_id or team_id does not match a configured id, or that names an Enterprise org the settings do not name, runs no listener, is acked where required, gets an ephemeral notice where a response URL exists, and logs slack_tenant_mismatch at error with the expected and received ids; a matching request passes unchanged
- [ ] #4 decisions/transport-slack.md, workplace-systems.md and configuration.md match the shipped behaviour; the settings docstring states the per-request check
- [ ] #5 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with commands and output recorded in notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 (TASK-24.5): the Slack tenant entry is SlackTenant (integrations/slack/settings.py), read through SlackSettings.tenant, with team_id and a tenant_id read. Add the optional enterprise_id inside it, make team_id optional, and make tenant_id the enterprise id when set; server/configured_systems.py already reads tenant_id and does not change. Production (2026-10-20): team T2G2S06PM, enterprise_id null, is_enterprise_install false, no SLACK_ENTERPRISE_ID set.
<!-- SECTION:NOTES:END -->
