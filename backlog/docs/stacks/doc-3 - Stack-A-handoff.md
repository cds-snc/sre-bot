---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-10-01 14:59'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

**Status: part 2 in progress (2026-10-01, fourth session).** Part 1 (layers 0-6, GitHub stack #1506) merged to `main`. The three standalone prerequisites merged too: TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515). TASK-26.1 was decomposed into three layers; all three are now implemented and committed. TASK-107 was decomposed into four layers (8a-8d); their plans were approved on 2026-10-01. Part 2 is a new stack (`gh stack init` done) whose bottom layer targets `main`. Nothing in part 2 is pushed yet.

The 2026-10-01 decision amendment (decisions/feature-packages.md: umbrellas gain a `core/` layer; text generation becomes a capability) is off this stack: it is commit f0c0e6da on branch `docs/umbrella-core-layer`, cut from `main`, open as PR #1516. It changes later work only: TASK-25.10, TASK-124.x, TASK-38, TASK-97 and the new TASK-134 and TASK-135.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0-6 | planning, TASK-18, 105, 105.1, 105.2, 105.3, 106 | `stack-a/*` | #1504-#1511 (stack #1506) | merged | Part 1: import-linter contracts (a)-(h), OperationResult envelope, ErrorCode registry, app/contracts/operations/. |
| 7a | TASK-26.1.1 | `stack-a/task-26.1.1-slack-models-to-contracts` | - | ready | Committed: 90d9d72a (planning) and 1a87d62a (implementation). Also fixes the help.py locale bug (user-visible) and deprecated utcnow. |
| 7b | TASK-26.1.2 | `stack-a/task-26.1.2-slack-lookup-adapters` | - | ready | Committed: 19843a16. Slack lookups in rant, incident_draft and incident_summary run through package Protocols (service.py) implemented in adapters/slack.py and wired by providers.py. The draft and summary adapters are a stepping stone that TASK-135 replaces; the rant one stays. |
| 7c | TASK-26.1.3 | `stack-a/task-26.1.3-slack-registrar-reply` | - | ready | Committed: 0741db20. All 6 ACs checked. contracts/slack/registrar.py and reply.py; integrations/slack/reply.py (SlackWebReply, exposed as provider.reply); hookspec re-signed to `registrar`, register_slack_listeners deleted; all 8 hookimpls migrated; 4 contract (e) entries deleted (38 -> 34). Closest review. |
| 8a | TASK-107.1 | `stack-a/task-107.1-scheduler-registry-to-contracts` (not created) | - | plan approved | `BackgroundJobRegistry` moves from jobs/ to contracts/scheduler/; jobs/models.py deleted. 6 production files, about 50 LOC. Contract (a) ignores 12 -> 11. |
| 8b | TASK-107.2 | `stack-a/task-107.2-i18n-spec-to-contracts` (not created) | - | plan approved | `I18nResourceSpec` to contracts/i18n/, new `I18nResourceRegistrar` Protocol implemented by the infrastructure registry. 12 production files, about 80 LOC. Contract (b) ignores 57 -> 53. |
| 8c | TASK-107.3 | `stack-a/task-107.3-hookspecs-to-contracts` (not created) | - | plan approved | `FeatureLifecycleSpecs`, both markers and the metadata-derived `PLUGIN_NAMESPACE` to contracts/plugins/; 11 hookimpl imports rewritten; inventory test moves; manager stays put. 19 production files (11 are one-line swaps), about 190 LOC. Contract (b) ignores 53 -> 44. |
| 8d | TASK-107.4 | `stack-a/task-107.4-plugin-manager-to-server` (not created) | - | plan approved | Manager and discovery to server/plugins/; infrastructure/plugins/ deleted; `scheduled_tasks.init` takes the registration callable; the stale decision-record text is fixed here. 7 production files plus 8 lines across 7 decision records. |

TASK-26.1 is the parent of 7a-7c and TASK-107 the parent of 8a-8d; each parent is done when its layers are.

## Position

Branch `stack-a/task-26.1.3-slack-registrar-reply` at 0741db20 (7c), on top of 19843a16 (7b), 1a87d62a (7a) and `main` at 72db5677 (level with `origin/main`). `gh stack view` shows the three layers in order; none is pushed. No background agents.

Uncommitted, all of it planning for layer 8 and none of it code: the TASK-107 task file (plan and approval comment), the four new task files TASK-107.1 to TASK-107.4, the TASK-30 task file (one comment), doc-2 and this doc. It belongs in a `plan:` commit at the bottom of layer 8a's branch, the way 90d9d72a sits under 7a.

Gates recorded for the 7c commit (run from `app/` before committing; not re-run since, the code is unchanged): ruff check clean; lint-imports 8 kept, 0 broken; mypy 0 errors in touched files (65 repo-wide, none new); pytest `tests --ignore=tests/smoke` 3582 passed, 6 failed, the 6 being the known single-process order failures (TASK-90) that pass on their own; legacy_surface 17 passed before and after, with only its registration call changed.

## Next actions

1. **human**: submit 7a-7c. The uncommitted planning files are not pushed:
   ```shell
   gh stack submit
   ```
   The PR descriptions carry the flags listed under Open decisions (7a locale fix, 7b client factory, 7c rotation-view message and catch-all reply port). Merge bottom-up one layer at a time, with a re-approval per rebased layer (doc-2 rules).
2. **human**: create layer 8a's branch and commit the planning files on it:
   ```shell
   gh stack add stack-a/task-107.1-scheduler-registry-to-contracts
   git add backlog/docs backlog/tasks
   git commit -m "plan: decompose TASK-107 into Stack A layers 8a-8d"
   ```
3. **agent**: implement 8a (TASK-107.1) on that branch: tests first, then code, gates, ACs through the CLI.
4. **human**: merge the docs-only PR #1516 (`docs/umbrella-core-layer`) when approved; it is independent of this stack. As of 2026-10-01 it is open and waiting on review.

## Open decisions

- 7a carries a one-line user-visible bug fix (Slack argument help now honours the user's locale; before, it always rendered en-US). It is kept per the fix-bugs-in-touched-files rule. If the reviewer wants 7a to be purely mechanical, split it into its own task/PR.
- 7b moves the three packages' lookups onto `integrations.slack.client.get_slack_web_client()`, so those calls now carry that factory's timeout and retry handlers instead of the Bolt app client's defaults. Same token, same calls and arguments. This follows from the approved plan; flag it in the PR description.
- 7b came out larger than the plan's estimate (14 production files, about 320 added lines, against 12 files and 140 LOC). It is one subsystem and behaviour-neutral, so it was kept as one layer; split per package if the reviewer prefers.
- 7c touches 22 production files against the plan's 13 (each hookimpl is an `__init__.py` plus a platforms module): 20 modified files, net 8 lines removed, plus 3 new files of 186 lines. It cannot be split: every implementer changes with the hookspec.
- 7c has one user-visible change: when Slack rejects `views.open` for `/sre rotations view`, the user now gets "Unable to open the user rotation view." instead of "Error executing sre.rotations.view: ...". Flag it in the PR description, or ask for the old text back.
- 7c's reply port catches every exception, not only `SlackApiError` (a non-Slack failure becomes PERMANENT_ERROR / UNEXPECTED_ERROR with the exception in `cause`). This keeps rant's fallback and incident_draft's "a failed notice never fails the draft" behaviour, which both caught bare `Exception` before. Narrow it to `SlackApiError` if the reviewer prefers unknown exceptions to propagate.
- Stale text left for a docs follow-up, outside 7c's scope: decisions/plugins.md:18, platform-entrypoints.md, platform-transports.md, transport-slack.md and hookspec-deprecation.md still describe `register_slack_listeners` and the provider-typed hookspec as current; the packages/access/request/__init__.py docstring still says `register_slack_commands(provider)`.
- 8c reads `PLUGIN_NAMESPACE` from the installed `sre-bot` distribution metadata (TASK-107 AC #3), so importing contracts.plugins raises `PackageNotFoundError` where the project is not installed. The Dockerfile installs it with `--no-editable`; no image build was run to confirm.
- 8b (12 files) and 8c (19 files) exceed the 10-file gate through one-line import swaps only, because the plan leaves no re-export shim at the old paths. Same reasoning as 7c.

## Planning queue

Empty. Every remaining Stack A layer has an approved plan (approval comments on TASK-107 and TASK-107.1 to TASK-107.4, 2026-10-01). The TASK-107 approval comment records the cross-layer decisions: `register_event_handlers` stays behind the `EventHandlerRegistrar` Protocol until TASK-30; contracts/plugins/ imports FastAPI and structlog at runtime; `scheduled_tasks.init` takes the registration callable; four layers; i18n and the scheduler are framework services (contracts in contracts/, implementations bound for server/), not capabilities.
