---
id: TASK-136
title: >-
  Name Protocols for their role and retire the Port suffix across contracts and
  packages
status: To Do
assignee: []
created_date: '2026-10-01 20:28'
updated_date: '2026-10-02 00:42'
labels:
  - plugin-architecture
  - naming
milestone: m-7
dependencies:
  - TASK-26.1.3
references:
  - 'https://github.com/cds-snc/sre-bot/pull/1518#discussion_r4158715513'
  - 'https://github.com/cds-snc/sre-bot/pull/1519#discussion_r4158973633'
  - .claude/skills/type-model-boundaries/SKILL.md
  - decisions/feature-packages.md
priority: medium
ordinal: 297000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reviewer feedback on #1518 and #1519 (2026-10-01): the word 'port' in interface names and docstrings was read as a network port, four times across two PRs. 'Port' is the ports-and-adapters term for an interface one side owns and another implements; it says which pattern is in use, not what the interface does. The codebase already has the plainer style: DirectoryProvider, IdempotencyStore, Summarizer, SlackCommandRegistrar, BackgroundJobRegistry, I18nResourceRegistrar. This task makes that style the rule and renames what does not follow it.

RULE TO RECORD
A Protocol is named for the role it plays (Reader, Lookup, Store, Provider, Registrar, Sender), never for the pattern. 'Port' stays out of class, function and variable names. In docstrings and decision-record prose, say 'interface'; keep 'port' only where a record discusses ports-and-adapters itself.

TODAY (verified 2026-10-01 on the Stack A tip, after TASK-107.4)
- contracts/slack/reply.py: SlackReplyPort (6 production files, 3 test files). Public contract API reached through SlackCommandRegistrar.reply; its docstring says 'only through this port'. Lands on main with TASK-26.1.3.
- packages/incident_draft/service.py: IncidentDocumentPort (4 production files, 2 test files) and the provider function get_incident_document_port.
- packages/access: AccessRequestServicePort, CatalogServicePort and AccessSyncApplicationServicePort, plus six private ones in the interactions/http.py modules (_AccessRequestSettingsPort, _AccessRequestServicePort, _AccessSyncSettingsPort, _AccessSyncApplicationServicePort, _CatalogSettingsPort, _CatalogServicePort).
- Handler docstrings in the incident and rant packages describe parameters as 'Port used to ...' / 'Port reading ...'.

OUT OF SCOPE
- IncidentChannelPort and get_incident_channel_port in incident_draft and incident_summary: TASK-135 replaces that interface and gives the replacement a role name (the reviewer asked for IncidentChannelReader).
- Any behaviour change. This is a mechanical rename plus the recorded rule.

QUESTIONS FOR THE PLANNER (raise them in chat, do not decide them in the plan)
- The new name for SlackReplyPort. SlackReplySender was proposed in session; not decided.
- The access names: dropping the suffix may collide with the concrete service classes, so each needs a role name rather than a bare strip.
- Whether IncidentDocumentPort is renamed here or moves with TASK-135 / TASK-38 first; skip it here if one of those already replaced it.

SIZE. About 20 production files across three areas (contracts/slack, incident, access), so likely over the single-PR gate. A natural split: (1) the recorded rule plus SlackReplyPort; (2) incident; (3) access. Decompose at planning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The naming rule (Protocols named for their role, no Port suffix, 'interface' in prose) is recorded in the type-model-boundaries skill and in the decision record that owns package structure
- [ ] #2 SlackReplyPort is renamed to the role name agreed at planning, with every importer rewritten and no alias or re-export left at the old name
- [ ] #3 IncidentDocumentPort and get_incident_document_port are renamed to role names, unless TASK-135 or TASK-38 already replaced them
- [ ] #4 The three public and six private Port-suffixed Protocols under packages/access are renamed to role names that do not collide with the concrete classes
- [ ] #5 rg finds no Protocol class ending in Port and no class, function, variable or parameter name ending in _port in app/ production code or tests, except IncidentChannelPort / get_incident_channel_port and the test names that refer to them (TASK-135) and the network-port identifiers in app/bin/dev-token.py, app/modules/webhooks/patterns/aws_sns_notification/auto_mitigation.py and its test; docstrings in the touched files say interface instead of port
- [ ] #6 No behaviour change: the TASK-36 legacy_surface suite is green before and after with no assertion change
- [ ] #7 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 00:38
---
Decomposed 2026-10-02 into TASK-136.1 (naming rule recorded in the type-model-boundaries skill and decisions/feature-packages.md, plus SlackReplyPort rename), TASK-136.2 (incident_draft document interface; depends on 136.1 because both edit incident_draft/platforms/slack.py) and TASK-136.3 (packages/access; new names pending the human, plan intentionally empty). Decisions made by the human in chat 2026-10-02: SlackReplyPort becomes SlackReplySender with no alias or re-export; IncidentDocumentPort becomes IncidentDocumentStore and get_incident_document_port becomes get_incident_document_store in this task, not deferred to TASK-135 or TASK-38; IncidentChannelPort and get_incident_channel_port stay untouched (TASK-135 owns them); the rule is recorded in .claude/skills/type-model-boundaries/SKILL.md and decisions/feature-packages.md because no decision record owns Protocol naming. The access role names and whether the six route-local twins are kept or collapsed are still open. Parent ACs are unchanged and this task stays the coordinator.
---

created: 2026-10-02 00:42
---
Decisions 2026-10-02 (Guillaume Charest, in session): access names are AccessRequestWorkflow, EntitlementCatalog and AccessSynchronizer, with underscore twins and _AccessRequestRouteSettings / _CatalogRouteSettings / _AccessSyncRouteSettings; the route-local twins are kept here and their collapse is noted on TASK-124.1. AC #5 reworded to name its exceptions (TASK-135 names, genuine network ports). Left out of every slice: 'port' prose in incident_summary (TASK-135 rewrites the package; noted there), in decisions/transport-slack.md and decisions/outbound-clients.md, and the module name packages/oncall_sync/ports.py.
---
<!-- COMMENTS:END -->
