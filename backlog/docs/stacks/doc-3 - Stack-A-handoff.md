---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-10-02 00:08'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

**Status: complete and merged (2026-10-01, seventh session).** Part 1 (layers 0-6, GitHub stack #1506) and part 2 (layers 7a-8d, GitHub stack #1520) are both on `main`. The standalone prerequisites TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515) merged earlier, and so did the docs-only decision amendment #1516 (umbrellas gain a `core/` layer; text generation becomes a capability). No implementation, review or planning work is left in this stack. What remains is housekeeping by the human: task statuses, the local checkout, and the follow-ups listed under Open decisions.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0-6 | planning, TASK-18, 105, 105.1, 105.2, 105.3, 106 | `stack-a/*` | #1504-#1511 (stack #1506) | merged | Part 1: import-linter contracts (a)-(h), OperationResult envelope, ErrorCode registry, app/contracts/operations/. |
| 7a | TASK-26.1.1 | `stack-a/task-26.1.1-slack-models-to-contracts` | #1517 | merged | 4e8b657d on `main`. Slack command models in contracts/slack/; also the help.py locale fix (user-visible) and the utcnow removal. |
| 7b | TASK-26.1.2 | `stack-a/task-26.1.2-slack-lookup-adapters` | #1518 | merged | 0c541136 on `main`. Slack lookups in rant, incident_draft and incident_summary run through package Protocols and adapters. The draft and summary adapters are a stepping stone that TASK-135 replaces; the rant one stays. |
| 7c | TASK-26.1.3 | `stack-a/task-26.1.3-slack-registrar-reply` | #1519 | merged | dc8dc74b on `main`. contracts/slack/registrar.py and reply.py; `SlackWebReply` in integrations/slack/provider.py; hookspec re-signed to `registrar`; all 8 hookimpls migrated; contract (e) 38 -> 34. |
| 8a | TASK-107.1 | `stack-a/task-107.1-scheduler-registry-to-contracts` | #1521 | merged | f2072026 on `main`. `BackgroundJobRegistry` in contracts/scheduler/registry.py; contract (a) ignores 12 -> 11. |
| 8b | TASK-107.2 | `stack-a/task-107.2-i18n-spec-to-contracts` | #1522 | merged | 459ff6c0 on `main`. `I18nResourceSpec` and the `I18nResourceRegistrar` Protocol in contracts/i18n/resources.py; contract (b) ignores 57 -> 53. |
| 8c | TASK-107.3 | `stack-a/task-107.3-hookspecs-to-contracts` | #1523 | merged | c227a1cd on `main`. contracts/plugins/ holds `PLUGIN_NAMESPACE`, both markers, `FeatureLifecycleSpecs` and the `EventHandlerRegistrar` Protocol; contract (b) ignores 53 -> 44. |
| 8d | TASK-107.4 | `stack-a/task-107.4-plugin-manager-to-server` | #1524 | merged | 9c6ed346 on `main`. Manager and discovery in server/plugins/; infrastructure/plugins/ deleted; `scheduled_tasks.init` takes the registration callable; 7 decision records updated. |

TASK-26.1 is the parent of 7a-7c and TASK-107 the parent of 8a-8d.

## Position

Checked 2026-10-01 after the merges. The checkout is still on `stack-a/task-107.4-plugin-manager-to-server` at f28aa1ca. Its tree is identical to `origin/main` at 9c6ed346 (`git diff HEAD origin/main` is empty), so nothing on the branch is missing from `main`. Local `main` is behind, at e6d086b5 (#1516). No background agents.

Uncommitted, and none of it Stack A work (it comes from a planning session that followed the review of #1518 and #1519):

- `backlog/tasks/task-135 - ...` modified: an Implementation Notes section recording that the replacement interface in packages/incident/core/ takes a role name instead of a `Port` suffix.
- `backlog/tasks/task-136 - Name-Protocols-for-their-role-and-retire-the-Port-suffix-across-contracts-and-packages.md` untracked: a new task.
- This doc (rewritten in the seventh session).

Task statuses at this check: TASK-26.1.1, 26.1.2, 26.1.3, TASK-107 and TASK-107.1 to 107.4 are In Progress; the parent TASK-26.1 is still To Do; the prerequisites TASK-25.4 and TASK-36 are still In Progress although their PRs merged.

## Next actions

1. **human**: carry the uncommitted backlog edits onto a new branch cut from `origin/main`, then fast-forward local `main`. Do not `git switch main` first: local `main` is behind and holds an older doc-3, so git refuses the switch. This branch's tree equals `origin/main`, so cutting the new branch from `origin/main` keeps the edits:
   ```shell
   git switch --no-track -c plan/task-136-protocol-role-names origin/main
   git fetch origin main:main
   git add backlog/tasks backlog/docs
   git commit -m "plan: add TASK-136, note the role-name rule on TASK-135, and close the Stack A handoff"
   git push -u origin plan/task-136-protocol-role-names
   ```
2. **human**: set the merged tasks to Done: TASK-26.1.1, TASK-26.1.2, TASK-26.1.3, TASK-26.1, TASK-107.1, TASK-107.2, TASK-107.3, TASK-107.4, TASK-107, and the prerequisites TASK-25.4 and TASK-36 if they are finished.
3. **human**: delete the merged local `stack-a/*` branches once step 1 is done (the remote ones too, if GitHub did not delete them on merge).
4. **human**: decide the follow-ups under Open decisions.
5. **agent**: on request, update the Stack A status line in doc-2 (Wave 1, dated 2026-09-29, which still says part 2 is a new stack in flight) and start the next stack's handoff doc. Per doc-2, Stack C (registry) starts once TASK-106 and TASK-27.1 have merged; TASK-106 has, and TASK-27.1 (a single PR, Wave 0) is still To Do.

## Open decisions

These outlive the stack. The items that were only flags for PR descriptions are dropped: those PRs are approved and merged.

- `infrastructure/i18n/service.py` carries 11 mypy errors that predate layer 8b (`Translator | None`: the service accepts no translator, then uses it unguarded). The fix changes how `TranslationService` is constructed (12 test call sites build it bare). It needs a follow-up task; none exists.
- `discover_and_init_features` and `collect_feature_i18n_resources` moved to server/plugins/manager.py in 8d, but nothing calls them (lifespan inlines the same steps). Delete them in a small PR, or leave them for TASK-110.
- `pyproject.toml` declares no entry points yet, so the entry-point-group use of `PLUGIN_NAMESPACE` has no consumer until TASK-110.
- `PLUGIN_NAMESPACE` is read from the installed `sre-bot` distribution metadata, so importing contracts.plugins.namespace raises `PackageNotFoundError` where the project is not installed. It was checked in a scratch venv built the way the Dockerfile builds it; no docker image build was run.
- TASK-67 (To Do) is stale: it describes `register_slack_commands` as deprecated in favour of `register_slack_listeners` and names `infrastructure/plugins/specs.py` and the old inventory test path. Layer 7c deleted `register_slack_listeners` and re-signed `register_slack_commands` on the registrar Protocol. The task needs a rewrite or a close, not a path fix.
- The review of #1518 and #1519 read "port" as a network port. TASK-136 (new, uncommitted) retires the `Port` suffix across contracts and packages; `IncidentChannelPort` is left to TASK-135. TASK-136 has no plan yet.

## Planning queue

Empty for Stack A. TASK-136 is outside this stack and needs a plan before any implementation.
