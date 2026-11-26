---
id: doc-18
title: Stack W handoff
type: guide
created_date: '2026-11-25T20:23:00Z'
updated_date: '2026-11-26T23:00:00Z'
---
## Stack

- Name: Stack W, webhooks dark chain (Lane B): the provisioned-content loader and the decisions/webhooks.md rewrite (TASK-37.1), the event model and engines (TASK-37.2.1), the event-consumer extension point and the Slack poster (TASK-37.2.3), async ingest and the inbox (TASK-37.2.2), then the content port, the Notify handler and the incident alert consumer (TASK-37.3). Every layer is dark; production-changing slices after W4 are single PRs from `main` (doc-11 rows 22.5-22.14).
- doc-2 line: Wave 5, "Webhooks" (rewritten to Stack W in W1's PR). doc-11 rows 22.1-22.4 and 22.2b, unit "Stack W"; side PRs 22.1a (TASK-25.8, before W4), 22.1c (TASK-113, before W2b; TASK-195 folded into it and archived 2026-11-26), 22.1d (TASK-196).
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
| W1 | TASK-37.1 provisioned-content loader (dark, no kind registered) + webhooks.md rewrite + ADR touches + task re-cut + TASK-168 ACs #1-#4 + delivery-session change-notice.md | `stack-w/task-37.1-content-loader` | #1889 | in review | plan approved 2026-11-25 with C1-C11; implemented, all 8 ACs checked, gates green (full pytest 8151 passed; mypy 33 pre-existing in untouched files); In Progress; rebased onto main twice on 2026-11-26 (after #1890; after #1894, conflicts in hookspecs.py, the hookspec inventory test and plugins.md resolved keeping both sides); may merge (W2 is open above it) |
| W2 | TASK-37.2.1 skeleton, domain (InboundEvent, event types, SenderKind, WebhookInstance), the webhooks/sender-kinds content kind, matcher, JSONPath, Liquid with per-language bot wording, email finder, [webhooks] settings | `stack-w/task-37.2.1-event-model` | #1891 | in review | plan approved 2026-11-26 (P1-P5); all 12 ACs checked; In Progress; follow-up commit 2026-11-26 (TASK-37.2.3 S1): `Destination(system, tenant, conversation_id, triage)`, workplace-systems.md rule 4; stays open while layers above are planned |
| W2b | TASK-37.2.3 event-consumer extension point (consumers by type, handlers by id), escaping Slack poster with MultilingualText wording, fallback rendering, Slack lookup cap | `stack-w/task-37.2.3-event-consumers` | - | ready | plan S1-S6 and D1-D10 approved 2026-11-26, plus the Translator contract pulled forward from TASK-118 (human); implemented after #1894 merged: all 10 ACs checked; mypy 33 pre-existing in untouched files; full pytest 8545 passed; fixed #1894's phase to be re-entrant on a cached plugin manager (server/plugins/extension_points.py, shared with Lane A); In Progress; commit and `gh stack submit` pending (human) |
| W3 | TASK-37.2.2 async ingest: protocols (entrypoints/http_<protocol>.py, adapters/aws_sns.py), inbox (conditional insert as dedupe), inline processor + leased sweeper, KMS helper; route not mounted | `stack-w/task-37.2.2-...` | - | planned (task, no plan) | waits on W2b; also 58.2 (done) |
| W4 | TASK-37.3 sender kinds as YAML (en-US and fr-FR bot wording, French reviewed by a human), parity + injection tests, Notify handler, incident alert consumer | `stack-w/task-37.3-...` | - | planned (task, no plan) | also waits on TASK-25.8 (doc-11 row 22.1a, single PR from main); names the Notify package's area (P5) |

## Position

- Branch: `stack-w/task-37.2.3-event-consumers` (W2b), above W2 (#1891) above W1 (#1889), on main at d886a357 (#1894). Its plan commit 4fc03e4c is on the branch.
- Uncommitted, all W2b's commit: the extension point, contracts, poster port, Slack adapter, composition root, locales, the Translator contract and host adapter, the Slack factory overrides, the phase re-entrancy fix, tests, four ADRs (webhooks, security, outbound-clients, i18n), and the task files (TASK-37.2.3; TASK-113 Done; notes on TASK-118, 125, 83, 37.2.2, 37.4.1, 37.6.1; TASK-147.5 dependency). doc-11 is untracked and never staged.
- Background agents: none.

## Next actions

1. **human**: commit W2b and `gh stack submit` (the session's command block). W1 (#1889) may merge; W2 and W2b stay open (W3 and W4 are planned), so never merge the top layer.
2. **agent, next Lane B session**: plan W3 (TASK-37.2.2) against the W2b ports: the processor resolves languages before rendering, picks posters with `poster_for`, gathers actions where `triage` is set, sets `retry_at` from `retry_after`; W3's branch is added with `gh stack add` above W2b.
3. **agent, later**: row 22.1a, TASK-25.8, a single PR from origin/main; it must merge before W4. Row 22.1d (TASK-196) any time.
4. **human, when W1 merges**: Lane A drops the /workspace copies of the delivery-session skill files; the next Lane B session closes TASK-37.1 and TASK-168.

## Open decisions

- None open for W2 or W2b: P1-P5 (W2) and S1-S6, D1-D10 and the Translator contract (W2b) approved 2026-11-26 (recorded in the tasks and in doc-11 rows 22.2 and 22.2b).

## Planning queue

- TASK-113 (22.1c): merged in #1894 2026-11-26; Done.
- W2b TASK-37.2.3: implemented 2026-11-26.
- W3 TASK-37.2.2: plan next (no plan yet).
- W4 TASK-37.3: plan after W3's; waits on TASK-25.8 (row 22.1a).
