---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-10-02 13:31'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

**Status: complete and merged (2026-10-01).** Part 1 (layers 0-6, GitHub stack #1506) and part 2 (layers 7a-8d, GitHub stack #1520) are both on `main`, as are the standalone prerequisites TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515) and the docs-only decision amendment #1516. No work is left in the stack itself.

The review of the stack produced one follow-up, TASK-136 (retire the `Port` suffix on Protocols). It is delivered as three single PRs from `main`, not as stack layers, and is tracked here because no other handoff doc owns it. Two slices have merged; the third is implemented and uncommitted (see Position).

## Layers

Stack A (all merged):

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0-6 | planning, TASK-18, 105, 105.1, 105.2, 105.3, 106 | `stack-a/*` | #1504-#1511 (stack #1506) | merged | Part 1: import-linter contracts (a)-(h), OperationResult envelope, ErrorCode registry, app/contracts/operations/. |
| 7a | TASK-26.1.1 | `stack-a/task-26.1.1-slack-models-to-contracts` | #1517 | merged | 4e8b657d. Slack command models in contracts/slack/. |
| 7b | TASK-26.1.2 | `stack-a/task-26.1.2-slack-lookup-adapters` | #1518 | merged | 0c541136. Slack lookups in rant, incident_draft and incident_summary run through package Protocols and adapters. The draft and summary adapters are a stepping stone that TASK-135 replaces. |
| 7c | TASK-26.1.3 | `stack-a/task-26.1.3-slack-registrar-reply` | #1519 | merged | dc8dc74b. contracts/slack/registrar.py and reply.py; all 8 hookimpls on the registrar Protocol. |
| 8a | TASK-107.1 | `stack-a/task-107.1-scheduler-registry-to-contracts` | #1521 | merged | f2072026. `BackgroundJobRegistry` in contracts/scheduler/. |
| 8b | TASK-107.2 | `stack-a/task-107.2-i18n-spec-to-contracts` | #1522 | merged | 459ff6c0. `I18nResourceSpec` and `I18nResourceRegistrar` in contracts/i18n/. |
| 8c | TASK-107.3 | `stack-a/task-107.3-hookspecs-to-contracts` | #1523 | merged | c227a1cd. contracts/plugins/ holds the namespace, markers, hookspecs and `EventHandlerRegistrar`. |
| 8d | TASK-107.4 | `stack-a/task-107.4-plugin-manager-to-server` | #1524 | merged | 9c6ed346. Manager and discovery in server/plugins/; infrastructure/plugins/ deleted. |

TASK-26.1 is the parent of 7a-7c and TASK-107 the parent of 8a-8d.

Follow-up single PRs (TASK-136, each cut from `main`; not stack layers):

| Slice | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-136.1 | `task-136.1-slack-reply-sender` | #1525 | merged | 8815379b. Naming rule recorded in the type-model-boundaries skill and decisions/feature-packages.md (Protocols are named for their role; prose says 'interface'). `SlackReplyPort` is now `SlackReplySender`. The TASK-136 task files landed with this PR. |
| 2 | TASK-136.2 | `feat/rename_incident_document_port` | #1526 | merged | f182ecd2. `IncidentDocumentPort` is now `IncidentDocumentStore`, `get_incident_document_port` is `get_incident_document_store`. |
| 3 | TASK-136.3 | `feat/rename_port_suffix_protocols` | none yet | in progress | Implemented, gates green, all 5 ACs checked, not committed. packages/access: `AccessRequestWorkflow`, `EntitlementCatalog`, `AccessSynchronizer`, and the six route-local Protocols (`_AccessRequestWorkflow`, `_EntitlementCatalog`, `_AccessSynchronizer`, `_AccessRequestRouteSettings`, `_CatalogRouteSettings`, `_AccessSyncRouteSettings`). No alias at any old name. |

## Position

Checked 2026-10-02. `main` and `origin/main` are at f182ecd2 (#1526). The checkout is on `feat/rename_port_suffix_protocols`, also at f182ecd2, with no commit of its own yet. No background agents.

Uncommitted on that branch:

- TASK-136.3 code: 8 files under `app/packages/access/` and 3 under `app/tests/unit/packages/access/`.
- Task files: TASK-136.3 (plan amendments, approval comment, notes, checked ACs), TASK-136 (two comments), TASK-135 (a note that it must rename the channel-interface test names), TASK-136.2 (assignee cleared).
- doc-2 and this doc.

Evidence for TASK-136.3 is in its task notes: ruff clean, the full `make` gate sequence at exit 0 (2858 and 760 tests passed, import contracts 8 kept), mypy unchanged at 15 errors that predate the change and sit outside the touched files, and the OpenAPI schema of the three access routers byte-identical before and after.

Task statuses at this check: TASK-136.1, 136.2 and 136.3 are In Progress and the parent TASK-136 is To Do. From the stack, TASK-26.1.1, 26.1.2, 26.1.3, TASK-107 and TASK-107.1 to 107.4 are still In Progress, the parent TASK-26.1 is still To Do, and the prerequisites TASK-25.4 and TASK-36 are still In Progress, although every one of their PRs has merged.

## Next actions

1. **human**: commit and submit TASK-136.3. The backlog edits listed under Position ride in the same commit:
   ```shell
   git add app/packages/access app/tests/unit/packages/access backlog/tasks backlog/docs
   git commit -m "feat: Rename the Port-suffixed Protocols in packages/access to role names"
   git push -u origin feat/rename_port_suffix_protocols
   gh pr create --base main --title "feat: Rename the Port-suffixed Protocols in packages/access to role names"
   ```
2. **human**: after it merges, set the merged tasks to Done: TASK-136.1, TASK-136.2, TASK-136.3, and from the stack TASK-26.1.1, TASK-26.1.2, TASK-26.1.3, TASK-26.1, TASK-107.1, TASK-107.2, TASK-107.3, TASK-107.4, TASK-107, plus the prerequisites TASK-25.4 and TASK-36 if they are finished. The parent TASK-136 depends on the decision below.
3. **human**: delete the merged local branches: the fourteen `stack-a/*` branches (including `stack-a/plan`), `task-136.1-slack-reply-sender` and `feat/rename_incident_document_port`, and their remotes if GitHub did not delete them on merge.
4. **human**: decide the follow-ups under Open decisions.
5. **agent**: on request, start the next stack's handoff doc. Per doc-2, Stack C (registry) starts once TASK-106 and TASK-27.1 have merged; TASK-106 has, and TASK-27.1 (a single PR, Wave 0) is still To Do.

## Open decisions

- When to close the parent TASK-136. Its AC #5 (no `Port` or `_port` names left in app/) holds only with exceptions until TASK-135 lands: `IncidentChannelPort`, `get_incident_channel_port`, and the test names that go with them (`_CHANNEL_PORT`, `mock_port`, one test name and two docstrings in test_incident_draft_slack.py and test_incident_summary_slack.py). The human decided on 2026-10-02 that TASK-135 renames all of these, and TASK-135's notes list them with line references. The network-port identifiers (app/bin/dev-token.py, the aws_sns_notification auto_mitigation module and its test) are genuine and stay. Either close TASK-136 once TASK-136.3 merges, with the exceptions as worded in the AC, or keep it open until TASK-135.
- `infrastructure/i18n/service.py` still carries 11 mypy errors that predate layer 8b (`Translator | None`: the service accepts no translator, then uses it unguarded). The fix changes how `TranslationService` is constructed (12 test call sites build it bare). It needs a follow-up task; none exists.
- `discover_and_init_features` and `collect_feature_i18n_resources` sit in server/plugins/manager.py with no caller (lifespan inlines the same steps). Delete them in a small PR, or leave them for TASK-110.
- `pyproject.toml` declares no entry points yet, so the entry-point-group use of `PLUGIN_NAMESPACE` has no consumer until TASK-110.
- `PLUGIN_NAMESPACE` is read from the installed `sre-bot` distribution metadata, so importing contracts.plugins.namespace raises `PackageNotFoundError` where the project is not installed. It was checked in a scratch venv built the way the Dockerfile builds it; no docker image build was run.
- TASK-67 (To Do) is stale: it describes `register_slack_commands` as deprecated in favour of `register_slack_listeners` and names `infrastructure/plugins/specs.py`. Layer 7c deleted `register_slack_listeners` and re-signed `register_slack_commands` on the registrar Protocol. The task needs a rewrite or a close, not a path fix.

Settled, recorded here so they are not reopened: the six route-local Protocol twins in packages/access are kept by TASK-136.3, and their collapse is noted on TASK-124.1. The 'port' prose in packages/incident_summary is left to TASK-135, which rewrites that package. TASK-136 does not touch decisions/transport-slack.md, decisions/outbound-clients.md or the module name packages/oncall_sync/ports.py.

## Planning queue

Empty. Every TASK-136 slice has an approved plan and is implemented. TASK-135 (To Do) has no plan yet and waits on TASK-25.10 and the TASK-97 decision; it is outside this stack.
