---
id: doc-18
title: Stack W handoff
type: guide
created_date: '2026-11-25T20:23:00Z'
updated_date: '2026-11-27T19:30:00Z'
---
## Stack

- Name: Stack W, webhooks dark chain (Lane B): the provisioned-content loader and the decisions/webhooks.md rewrite (TASK-37.1, merged), the event model and engines (TASK-37.2.1), the event-consumer extension point and the Slack poster (TASK-37.2.3), async ingest and the inbox (TASK-37.2.2), then sender kinds as content, the Notify handler and the incident alert consumer (TASK-37.3). Every layer is dark; production-changing slices are single PRs from `origin/main` (doc-11 rows 22.3a, 22.3b, 22.5 onward, 22.12a, 22.12b).
- doc-2 line: Wave 5, "Webhooks" (Stack W). doc-11 rows 22.1-22.4 and 22.2b, unit "Stack W"; side PRs 22.1a (TASK-25.8, before W4), 22.1d (TASK-196), 22.3a (TASK-37.2.4 inbox table, before 22.7), 22.3b (TASK-198 body cap, before 22.7), 22.12a and 22.12b (TASK-197.1 and 197.2 field encryption, before 22.13).
- Program plan: decisions/webhooks.md and the re-cut tasks; background in the TASK-168 research packet (untracked, `/workspace/task-168-webhooks-research-packet.md`). Content layout: `<root>/<owner>/<kind>/[<folder>/]<id>.yaml`, self-describing files, schemas at `app/content/schemas/<owner>/<kind>.json`, validator `python -m bin.check_content_schemas --root`.
- Trunk `main`. Worktree `/home/vscode/worktrees/sre-bot-webhooks` (Lane B; Lane A runs in `/workspace`, whose checked-out `main` is never touched; base on `origin/main`). Branches: stacked layers `stack-w/<task-id>-<slug>`; Lane B side PRs `task-<id>-<slug>` from `origin/main`.
- Planning: the agent plans each layer (plan-task skill), writes it with `backlog task edit <id> --plan`, and stops for approval.
- Merges: squash, bottom-up, re-approval per layer after rebase; never merge the top layer while more layers are planned. Every layer is dark: one git revert each.
- Task status: a layer is set Done once its PR is merged, every AC is checked and no human post-deploy step is open.
- Task files for side rows: tasks created at a layer's planning are committed in that layer's plan commit. A side-row session from `origin/main` brings its task file onto its branch with `git checkout <layer branch> -- "<task file>"` so the file ships with that PR; when the layer later rebases onto main, keep main's copy of that file.
- Never stage: `backlog/docs/doc-11*`, `doc-15*`, `doc-16*`, `task-168-webhooks-research-packet.md`, `task-168-webhooks-architecture-review.md` (all untracked in `/workspace` only; never copied here).

## Shared-machine rules (agreed with Lane A, 2026-11-25)

- Lane A runs in another VS Code window on this Codespace (`/workspace`). Every full mypy and full pytest runs under the shared lock, which waits while the other lane holds it:
  - `cd app && flock /tmp/sre-bot-heavy-gates.lock uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`
  - `cd app && flock /tmp/sre-bot-heavy-gates.lock uv run pytest tests --ignore=tests/smoke` (in the background; wait for its notification)
  - Ruff, targeted tests and the make checks stay unlocked.
- Every git command block given to the human starts with a guard: `cd /home/vscode/worktrees/sre-bot-webhooks` and a check that the current branch is the expected one, stopping otherwise. (On 2026-11-25 a Lane A block ran in this worktree by mistake; it was undone.)
- decisions/migration.md coexistence rule 7 (Lane A PR #1888): a task id appears in a `.py` file only as `TODO(TASK-<id>)`, naming the task that removes or changes those lines; guarded by `make check-task-references` (CI step, baseline only ratchets down). Lane B code follows it; W1 adds no task id to any `.py` file.
- Shared files with #1888: `decisions/migration.md` (rule 7, its Checks line, a Changes line), `.github/workflows/ci_code.yml` and `app/Makefile` (#1888 adds a step and target after check-test-seams, the same spot as W1's content-schema ones: keep both, both targets in `.PHONY`). Whichever PR merges second rebases onto main and keeps both sides.
- W1 (#1889) merged the delivery-session skill files; `/workspace` holds no copies (checked 2026-11-27).

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| W1 | TASK-37.1 provisioned-content loader, webhooks.md rewrite, task re-cut | `stack-w/task-37.1-content-loader` | #1889 | merged | merged 2026-11-27 (ba7e479b); TASK-37.1 and TASK-168 closed Done 2026-11-27 (committed with W3's plan commit) |
| W2 | TASK-37.2.1 event model, sender-kind content kind, engines, [webhooks] settings, Destination as a workplace reference | `stack-w/task-37.2.1-event-model` | #1891 | in review | all 12 ACs checked; In Progress; rebased onto main 2026-11-27 (`gh stack sync`); stays open while layers above are planned |
| W2b | TASK-37.2.3 event-consumer extension point, platform-neutral Slack poster, fallback rendering, Translator contract | `stack-w/task-37.2.3-event-consumers` | #1896 | in review | all 10 ACs checked; In Progress; submitted 2026-11-27 and retitled; shares server/lifespan.py, server/plugins/extension_points.py, integrations/slack/client.py, contracts/i18n/translator.py and three ADRs with main (keep both sides on rebase) |
| W3 | TASK-37.2.2 async ingest: aws_sns and legacy_slack_json protocols, WebhookStore, the inbox on the records contract, inline processor, sweeper (built, not registered), route (not mounted) | `stack-w/task-37.2.2-async-ingest` | #1898 | in review | plan approved 2026-11-27 (D1-D20; one PR under a size-gate exception); plan commit 49f970e8, code commit 028c94f1; all 12 ACs checked, full mypy 33 pre-existing in untouched files, full pytest 8667 passed; In Progress; submitted 2026-11-27; stays open while W4 is planned |
| W4 | TASK-37.3 sender kinds as YAML, parity and injection tests, Notify handler, incident alert consumer | `stack-w/task-37.3-...` | - | planned (task, no plan) | also waits on TASK-25.8 (row 22.1a); its SNS kinds match the parsed `Message` (W3 D11) |

## Position

- Top of stack: `stack-w/task-37.2.2-async-ingest` (W3, #1898, in review), above W2b (#1896) above W2 (#1891). Main moved to 3c196467 (Lane A TASK-145.7.13, no file overlap with the stack): `gh stack sync` and `gh stack submit` on 2026-11-27, with this handoff update committed on W3 first.
- No uncommitted stack work. Lane B's next session works row 22.3a on `task-37.2.4-webhook-inbox-table` from origin/main (not a stack layer).
- Background agents: none.

## Next actions

1. W2, W2b and W3 stay open (W4 is planned): never merge them.
2. **agent, Lane B**: row 22.3a (TASK-37.2.4, inbox table and the webhooks-table index), a single PR from origin/main, before 22.7; then 22.3b (TASK-198).
3. **agent, later**: plan W4 (TASK-37.3) after row 22.1a (TASK-25.8, single PR from origin/main, must merge before W4); row 22.1d (TASK-196) any time; rows 22.12a and 22.12b (TASK-197) before 22.13.

## Open decisions

- None open for W3: Q1-Q6 approved 2026-11-27 (recorded in TASK-37.2.2's plan and in doc-11 row 22.3).

## Planning queue

- W3 TASK-37.2.2: in review (#1898) since 2026-11-27.
- W4 TASK-37.3: plan after W3 is implemented; waits on TASK-25.8 (row 22.1a).
