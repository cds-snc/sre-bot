---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-10-01 16:47'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

**Status: part 2 in progress (2026-10-01, sixth session).** Part 1 (layers 0-6, GitHub stack #1506) merged to `main`. The three standalone prerequisites merged too: TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515). Part 2 is GitHub stack #1520, whose bottom layer targets `main`. Layers 7a-7c (TASK-26.1) are pushed and in review as #1517, #1518 and #1519, all with green CI. Layers 8a (TASK-107.1) and 8b (TASK-107.2) are committed, pushed and in review as #1521 and #1522. Layer 8c (TASK-107.3) is implemented on its branch with gates green but not committed. Layer 8d has an approved plan and no branch yet.

The 2026-10-01 decision amendment (decisions/feature-packages.md: umbrellas gain a `core/` layer; text generation becomes a capability) is off this stack: it is commit f0c0e6da on branch `docs/umbrella-core-layer`, cut from `main`, open as PR #1516. It changes later work only: TASK-25.10, TASK-124.x, TASK-38, TASK-97 and the new TASK-134 and TASK-135.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0-6 | planning, TASK-18, 105, 105.1, 105.2, 105.3, 106 | `stack-a/*` | #1504-#1511 (stack #1506) | merged | Part 1: import-linter contracts (a)-(h), OperationResult envelope, ErrorCode registry, app/contracts/operations/. |
| 7a | TASK-26.1.1 | `stack-a/task-26.1.1-slack-models-to-contracts` | #1517 | in review | Commits 90d9d72a (planning) and 1a87d62a. CI green. Also fixes the help.py locale bug (user-visible) and deprecated utcnow. The PR title is still the branch-derived "stack a/task 26.1.1 slack models to contracts". |
| 7b | TASK-26.1.2 | `stack-a/task-26.1.2-slack-lookup-adapters` | #1518 | in review | Commit 19843a16. CI green. Slack lookups in rant, incident_draft and incident_summary run through package Protocols (service.py) implemented in adapters/slack.py and wired by providers.py. The draft and summary adapters are a stepping stone that TASK-135 replaces; the rant one stays. |
| 7c | TASK-26.1.3 | `stack-a/task-26.1.3-slack-registrar-reply` | #1519 | in review | Commits 0741db20 and 4dfef224 (CI fix). CI green. contracts/slack/registrar.py and reply.py; `SlackWebReply` lives in integrations/slack/provider.py (exposed as provider.reply) because the vendor-package contract check rejects a new module in integrations/slack/; hookspec re-signed to `registrar`, register_slack_listeners deleted; all 8 hookimpls migrated; 4 contract (e) entries deleted (38 -> 34). Closest review. |
| 8a | TASK-107.1 | `stack-a/task-107.1-scheduler-registry-to-contracts` | #1521 | in review | Commits 972a0106 (planning), 63e42311 and 3fdb25ae (handoff doc). CI green. The PR title is still the branch-derived "stack a/task 107.1 scheduler registry to contracts". `BackgroundJobRegistry` moved to contracts/scheduler/registry.py; jobs/models.py deleted; contract (a) ignores 12 -> 11. |
| 8b | TASK-107.2 | `stack-a/task-107.2-i18n-spec-to-contracts` | #1522 | in review | Commits a7da6f99 and 577c117f (handoff doc). CI green. The PR title is still branch-derived. `I18nResourceSpec` and the `I18nResourceRegistrar` Protocol live in contracts/i18n/resources.py; the infrastructure registry implements it; the 4 hookimpls are typed on the Protocol. Contract (b) ignores 57 -> 53. |
| 8c | TASK-107.3 | `stack-a/task-107.3-hookspecs-to-contracts` | - | in progress | Implemented, uncommitted, all 5 ACs checked, gates green. contracts/plugins/ holds `PLUGIN_NAMESPACE`, both markers (namespace.py), `FeatureLifecycleSpecs` and the `EventHandlerRegistrar` Protocol (hookspecs.py); infrastructure/plugins/specs.py deleted; 11 hookimpl imports rewritten; inventory test moved; manager stays put. 18 production files (3 new, 1 deleted). Contract (b) ignores 53 -> 44. |
| 8d | TASK-107.4 | `stack-a/task-107.4-plugin-manager-to-server` (not created) | - | plan approved | Manager and discovery to server/plugins/; infrastructure/plugins/ deleted; `scheduled_tasks.init` takes the registration callable; the stale decision-record text is fixed here. 7 production files plus 8 lines across 7 decision records. |

TASK-26.1 is the parent of 7a-7c and TASK-107 the parent of 8a-8d; each parent is done when its layers are.

## Position

Branch `stack-a/task-107.3-hookspecs-to-contracts` at 577c117f, the same commit as the 8b branch below it (8c has no commit yet). `gh stack view` shows the six branches in order; the lower five have PRs. No background agents.

Uncommitted, all of it layer 8c (TASK-107.3): new `app/contracts/plugins/` and `app/tests/unit/contracts/plugins/` (the inventory test moved there from `app/tests/unit/infrastructure/plugins/`, which no longer exists); deleted `app/infrastructure/plugins/specs.py`; edited `app/infrastructure/plugins/{__init__,manager}.py`, the `__init__.py` of the 9 packages with hookimpls and of `modules/dev` and `modules/sre`, `app/pyproject.toml`, `app/tests/unit/infrastructure/events/test_hookspec_registration.py` and `app/tests/integration/legacy_surface/conftest.py`; the TASK-107.3 task file (status, notes and ACs). This doc is also uncommitted and goes in its own `plan:` commit.

Gates recorded for 8c (run from `app/` on the uncommitted tree): ruff check clean; ruff format --check 777 files already formatted; check-sdk-typing, check-vendor-package-contract (16 baselined), check-aws-platform-seam (11 baselined) and check-runtime-imports OK; lint-imports 8 kept, 0 broken, contract (b) 44 ignored; mypy 65 errors in 22 files repo-wide, the same error set as 8b, 0 in touched files; `make test` 2848 passed, then 760 passed.

PR checks at the last look (2026-10-01): #1517, #1518, #1519, #1521 and #1522 all green.

Gate rule for every remaining layer: run the whole CI sequence from `.github/workflows/ci_code.yml` before calling a layer ready (`make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test`, plus ruff check and mypy). #1519 first failed CI because only ruff, mypy, lint-imports and pytest had been run and the vendor-package guardrail was missed.

## Next actions

1. **human**: commit layer 8c, commit this doc, and push:
   ```shell
   git add app "backlog/tasks/task-107.3 - Move-the-hookspecs-the-hookimpl-marker-and-the-namespace-constant-to-app-contracts-plugins.md"
   git commit -m "refactor(contracts): move the hookspecs, the pluggy markers and the plugin namespace constant to app/contracts/plugins (TASK-107.3)"
   git add backlog/docs
   git commit -m "plan: update the Stack A handoff after layer 8c"
   gh stack submit
   ```
2. **human**: create layer 8d's branch:
   ```shell
   gh stack add stack-a/task-107.4-plugin-manager-to-server
   ```
3. **agent**: implement 8d (TASK-107.4) on that branch: tests first, then code, the full CI sequence, ACs through the CLI. It also fixes the decision records that still name `infrastructure/plugins/specs.py` (plugins.md, i18n.md, platform-transports.md, platform-entrypoints.md, hookspec-deprecation.md).
4. **human**: review and merge #1517, #1518, #1519, #1521 and #1522 bottom-up, one layer at a time, with a re-approval per rebased layer (doc-2 rules). The PR descriptions should carry the flags listed under Open decisions (7a locale fix, 7b client factory, 7c rotation-view message and catch-all reply port). #1517, #1521 and #1522 still have branch-derived titles.
5. **human**: merge the docs-only PR #1516 (`docs/umbrella-core-layer`) when approved; it is independent of this stack.

## Open decisions

- 7a carries a one-line user-visible bug fix (Slack argument help now honours the user's locale; before, it always rendered en-US). It is kept per the fix-bugs-in-touched-files rule. If the reviewer wants 7a to be purely mechanical, split it into its own task/PR.
- 7b moves the three packages' lookups onto `integrations.slack.client.get_slack_web_client()`, so those calls now carry that factory's timeout and retry handlers instead of the Bolt app client's defaults. Same token, same calls and arguments. This follows from the approved plan; flag it in the PR description.
- 7b came out larger than the plan's estimate (14 production files, about 320 added lines, against 12 files and 140 LOC). It is one subsystem and behaviour-neutral, so it was kept as one layer; split per package if the reviewer prefers.
- 7c touches 22 production files against the plan's 13 (each hookimpl is an `__init__.py` plus a platforms module): 20 modified files, net 8 lines removed, plus 3 new files of 186 lines. It cannot be split: every implementer changes with the hookspec.
- 7c has one user-visible change: when Slack rejects `views.open` for `/sre rotations view`, the user now gets "Unable to open the user rotation view." instead of "Error executing sre.rotations.view: ...". Flag it in the PR description, or ask for the old text back.
- 7c's reply port catches every exception, not only `SlackApiError` (a non-Slack failure becomes PERMANENT_ERROR / UNEXPECTED_ERROR with the exception in `cause`). This keeps rant's fallback and incident_draft's "a failed notice never fails the draft" behaviour, which both caught bare `Exception` before. Narrow it to `SlackApiError` if the reviewer prefers unknown exceptions to propagate.
- Stale text left for a docs follow-up, outside 7c's scope: decisions/plugins.md:18, platform-entrypoints.md, platform-transports.md, transport-slack.md and hookspec-deprecation.md still describe `register_slack_listeners` and the provider-typed hookspec as current; the packages/access/request/__init__.py docstring still says `register_slack_commands(provider)`.
- 8c reads `PLUGIN_NAMESPACE` from the installed `sre-bot` distribution metadata (TASK-107 AC #3), so importing contracts.plugins.namespace raises `PackageNotFoundError` where the project is not installed. Checked in a scratch venv built with the Dockerfile's `uv sync --locked --no-dev --no-editable`: the constant, the marker and the manager all report `sre_bot`. No docker image build was run.
- 8b touches `infrastructure/i18n/service.py` for a docstring example only, and that file carries 11 mypy errors that predate the layer (`Translator | None`: the service accepts no translator, then uses it unguarded). They are left alone because the fix changes how `TranslationService` is constructed (12 test call sites build it bare). Decide: a follow-up task, or fold a fix into 8b.
- 8b annotates the 4 hookimpls' `registry` parameter as `I18nResourceRegistrar` (it was untyped), which the plan did not list. Type-only, no behaviour change.
- 8b (12 files) and 8c (18 files) exceed the 10-file gate through one-line import swaps only, because the plan leaves no re-export shim at the old paths. Same reasoning as 7c.

## Planning queue

Empty. Every remaining Stack A layer has an approved plan (approval comments on TASK-107 and TASK-107.1 to TASK-107.4, 2026-10-01). The TASK-107 approval comment records the cross-layer decisions: `register_event_handlers` stays behind the `EventHandlerRegistrar` Protocol until TASK-30; contracts/plugins/ imports FastAPI and structlog at runtime; `scheduled_tasks.init` takes the registration callable; four layers; i18n and the scheduler are framework services (contracts in contracts/, implementations bound for server/), not capabilities.
