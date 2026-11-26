---
id: doc-18
title: Stack W handoff
type: guide
created_date: '2026-11-25T20:23:00Z'
updated_date: '2026-11-26T20:00:00Z'
---
## Stack

- Name: Stack W, webhooks dark chain (Lane B): the provisioned-content loader and the decisions/webhooks.md rewrite (TASK-37.1), the event model and engines (TASK-37.2.1), the event-consumer extension point and the Slack poster (TASK-37.2.3), async ingest and the inbox (TASK-37.2.2), then the content port, the Notify handler and the incident alert consumer (TASK-37.3). Every layer is dark; production-changing slices after W4 are single PRs from `main` (doc-11 rows 22.5-22.14).
- doc-2 line: Wave 5, "Webhooks" (rewritten to Stack W in W1's PR). doc-11 rows 22.1-22.4 and 22.2b, unit "Stack W"; side PRs 22.1a (TASK-25.8, before W4), 22.1c (TASK-195, before W2b), 22.1d (TASK-196).
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
| W1 | TASK-37.1 provisioned-content loader (dark, no kind registered) + webhooks.md rewrite + ADR touches + task re-cut + TASK-168 ACs #1-#4 + delivery-session change-notice.md | `stack-w/task-37.1-content-loader` | #1889 | in review | plan approved 2026-11-25 with C1-C11; implemented, all 8 ACs checked, gates green (full pytest 8151 passed; mypy 33 pre-existing in untouched files); In Progress; committed 1197c9f and submitted 2026-11-25; stays in review until W2 is open above it |
| W2 | TASK-37.2.1 skeleton, domain (InboundEvent, event types, SenderKind, WebhookInstance), the webhooks/sender-kinds content kind, matcher, JSONPath, Liquid with per-language bot wording, email finder, [webhooks] settings | `stack-w/task-37.2.1-event-model` | - | ready | plan approved 2026-11-26 (P1-P5; P2 respecting #1889's content decisions; OWASP corrections); all 12 ACs checked; full pytest 8295 passed, mypy 33 pre-existing in untouched files; In Progress; commit and `gh stack submit` pending (human) |
| W2b | TASK-37.2.3 event-consumer extension point (consumers by type, handlers by id), escaping Slack poster with MultilingualText wording, fallback rendering, Slack lookup cap | `stack-w/task-37.2.3-...` | - | planned (task, no plan) | created 2026-11-26 by the P1 split; also waits on TASK-195 (row 22.1c) merged |
| W3 | TASK-37.2.2 async ingest: protocols (entrypoints/http_<protocol>.py, adapters/aws_sns.py), inbox (conditional insert as dedupe), inline processor + leased sweeper, KMS helper; route not mounted | `stack-w/task-37.2.2-...` | - | planned (task, no plan) | waits on W2b; also 58.2 (done) |
| W4 | TASK-37.3 sender kinds as YAML (en-US and fr-FR bot wording, French reviewed by a human), parity + injection tests, Notify handler, incident alert consumer | `stack-w/task-37.3-...` | - | planned (task, no plan) | also waits on TASK-25.8 (doc-11 row 22.1a, single PR from main); names the Notify package's area (P5) |

## Position

- Branch: `stack-w/task-37.2.1-event-model`, added above W1 with `gh stack add` (at 1197c9f, no commits of its own yet). W1 is `stack-w/task-37.1-content-loader`, PR #1889, open against main.
- Uncommitted, all W2's commit: the webhooks capability, its tests, the exported schema, config, the lock file, four ADRs, the lifespan plugin-set test line, this doc, and the task files (TASK-37.1 notes; TASK-37.2.1; TASK-37.2.2 and TASK-37.3 comments, deps and ACs; new TASK-37.2.3, TASK-195, TASK-196). doc-11 is untracked and never staged.
- Background agents: none.

## Next actions

1. **human**: commit W2 and `gh stack submit` (the session's command block). W1 (#1889) may then merge; W2 stays open (more layers are planned), so never merge the top layer.
2. **agent, next Lane B session**: plan TASK-195 (row 22.1c, single PR from origin/main), then W2b (TASK-37.2.3) once W2 is open; W2b's branch is added with `gh stack add` above W2.
3. **agent, later**: row 22.1a, TASK-25.8, a single PR from origin/main; it must merge before W4. Row 22.1d (TASK-196) any time.
4. **human, when W1 merges**: Lane A drops the /workspace copies of the delivery-session skill files; the next Lane B session closes TASK-37.1 and TASK-168.

## Open decisions

- None open for W2: P1-P5 approved 2026-11-26 (recorded in TASK-37.2.1's plan and comments, and in doc-11 row 22.2).

## Planning queue

- TASK-195 (22.1c): task written, plan at pickup.
- W2b TASK-37.2.3: plan once W2 is open; waits on TASK-195 merged before implementation.
- W3 TASK-37.2.2: plan after W2b's plan.
- W4 TASK-37.3: plan after W3's; waits on TASK-25.8 (row 22.1a).
