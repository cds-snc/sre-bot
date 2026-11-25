---
id: doc-18
title: Stack W handoff
type: guide
created_date: '2026-11-25T20:23:00Z'
updated_date: '2026-11-25T21:11:00Z'
---
## Stack

- Name: Stack W, webhooks dark chain (Lane B): the provisioned-content loader and the decisions/webhooks.md rewrite (TASK-37.1), the event model and engines (TASK-37.2.1), async ingest and the inbox (TASK-37.2.2), then the content port, the Notify handler and the incident alert consumer (TASK-37.3). Every layer is dark; production-changing slices after W4 are single PRs from `main` (doc-11 rows 22.5-22.14).
- doc-2 line: Wave 5, "Webhooks" (rewritten to Stack W in W1's PR). doc-11 rows 22.1-22.4, unit "Stack W".
- Program plan: decisions/webhooks.md (rewritten in W1) and the re-cut tasks; background in the TASK-168 research packet (untracked, `/workspace/task-168-webhooks-research-packet.md`), approved 2026-11-25. Content layout (W1, approved corrections C1-C5 in TASK-37.1's plan): `<root>/<owner>/<kind>/[<folder>/]<id>.yaml`, self-describing files (`kind`, `version`), schemas owned by the app at `app/content/schemas/<owner>/<kind>.json`, validator `python -m bin.check_content_schemas --root`.
- Trunk `main`. Worktree `/home/vscode/worktrees/sre-bot-webhooks` (Lane B; Lane A runs in `/workspace`, whose checked-out `main` is never touched; base on `origin/main`). Branches: stacked layers `stack-w/<task-id>-<slug>`; Lane B side PRs `task-<id>-<slug>` from `origin/main`.
- Planning: the agent plans each layer (plan-task skill, task-planner agent), writes it with `backlog task edit <id> --plan`, and stops for approval.
- Merges: squash, bottom-up, re-approval per layer after rebase; never merge the top layer while more layers are planned. All four layers are dark: one git revert each.
- Task status: the agent sets a layer Done once its PR is merged, every AC is checked and no human post-deploy step is open.
- Never stage: `backlog/docs/doc-11*`, `doc-15*`, `doc-16*`, `task-168-webhooks-research-packet.md`, `task-168-webhooks-architecture-review.md` (all untracked in `/workspace` only; never copied here).

## Shared-machine rules (agreed with Lane A, 2026-11-25)

- Lane A runs in another VS Code window on this Codespace (`/workspace`). Every full mypy and full pytest runs under the shared lock, which waits while the other lane holds it:
  - `cd app && flock /tmp/sre-bot-heavy-gates.lock uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`
  - `cd app && flock /tmp/sre-bot-heavy-gates.lock uv run pytest tests --ignore=tests/smoke` (in the background; wait for its notification)
  - Ruff, targeted tests and the make checks stay unlocked.
- Every git command block given to the human starts with a guard: `cd /home/vscode/worktrees/sre-bot-webhooks` and a check that the current branch is the expected one, stopping otherwise. (On 2026-11-25 a Lane A block ran in this worktree by mistake; it was undone.)
- decisions/migration.md coexistence rule 7 (Lane A PR #1888): a task id appears in a `.py` file only as `TODO(TASK-<id>)`, naming the task that removes or changes those lines; guarded by `make check-task-references` (CI step, baseline only ratchets down). Lane B code follows it; W1 adds no task id to any `.py` file.
- Shared files with #1888: `decisions/migration.md` (rule 7, its Checks line, a Changes line), `.github/workflows/ci_code.yml` and `app/Makefile` (#1888 adds a step and target after check-test-seams, the same spot as W1's content-schema ones: keep both, both targets in `.PHONY`). Whichever PR merges second rebases onto main and keeps both sides.
- W1 carries `.claude/skills/delivery-session/SKILL.md` and `change-notice.md`; `/workspace` holds identical uncommitted copies that Lane A never stages and drops once W1 merges.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| W1 | TASK-37.1 provisioned-content loader (dark, no kind registered) + webhooks.md rewrite + ADR touches + task re-cut + TASK-168 ACs #1-#4 + delivery-session change-notice.md | `stack-w/task-37.1-content-loader` | - (to submit) | ready | plan approved 2026-11-25 with C1-C11; implemented, all 8 ACs checked, gates green (full pytest 8151 passed; mypy 33 pre-existing in untouched files); In Progress; uncommitted until the human runs the session's commands; stays in review until W2 is open above it |
| W2 | TASK-37.2.1 event model (InboundEvent, event types), condition matcher, JSONPath, Liquid, escaping Slack poster, consumer hookspec, linear email matcher; registers the first content kind (webhooks/sender-kinds) | `stack-w/task-37.2.1-event-model` | - | planned (task, no plan) | created by W1's re-cut; plan at pickup; decide whether TASK-193's MultilingualText rule (comment on 37.2.1) becomes an AC |
| W3 | TASK-37.2.2 async ingest: protocols, inbox (conditional insert as dedupe), inline processor + leased sweeper, KMS helper; route not mounted | `stack-w/task-37.2.2-...` | - | planned (packet only) | also waits on 58.2 (done) |
| W4 | TASK-37.3 sender kinds as YAML, parity + injection tests, Notify handler, incident alert consumer | `stack-w/task-37.3-...` | - | planned (packet only) | also waits on TASK-25.8 (doc-11 row 22.1a, single PR from main) |

## Position

- Branch: `stack-w/task-37.1-content-loader` at 87471ee9 (= origin/main at 2026-11-25), not yet a gh stack.
- Uncommitted work: all of W1 (loader, tests, config, CI step, ADRs, re-cut task files, doc-2, this doc, delivery-session skill files); the session's command block stages it by name and renames nine task files whose slugs went stale (git mv).
- Background agents: none.

## Next actions

1. **human**: run the session's command block: `gh stack init stack-w/task-37.1-content-loader`, the `git mv` renames, `git add` of the named paths, `git commit -m "TASK-37.1 Provisioned-content loader, webhooks ADR rewrite and task re-cut"`, `gh pr list --head stack-w/task-37.1-content-loader --state all` (expect none), `gh stack submit`, then set the PR body from the session's message.
2. **human**, before the next session: `gh stack checkout stack-w/task-37.1-content-loader`, then `gh stack add stack-w/task-37.2.1-event-model` (W2's branch above W1, checked out).
3. **agent (next Lane B session)**: row 22.2, W2 TASK-37.2.1: plan it (`/plan-task 37.2.1`) and stop for approval. A stack layer's wait on the layer below is met when that layer is open in review, not merged. W1 may merge only once W2 is open above it (never merge the top layer while more layers are planned).
4. **agent, later**: row 22.1a, TASK-25.8, a single PR from origin/main; it must merge before W4 (TASK-37.3).

## Open decisions

- Whether TASK-193's MultilingualText rule (bot wording multilingual; sender content keeps its source language) becomes an AC on 37.2.1 and 37.3 (comments there today). Decide at 37.2.1 planning.
- The ADR rewrite adds `protocols/` to the capability layout (webhooks.md Decision 1); confirm or change at 37.2.1/37.2.2 planning.

## Planning queue

- W2 TASK-37.2.1: plan at pickup (next Lane B session); stacked on W1 (in review).
- W3 TASK-37.2.2: waits on W2's plan.
- W4 TASK-37.3: waits on W3's plan and TASK-25.8 (row 22.1a).
