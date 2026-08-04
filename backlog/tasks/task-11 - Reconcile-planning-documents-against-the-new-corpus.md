---
id: TASK-11
title: Reconcile planning documents against the new corpus
status: Done
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 17:32'
labels:
  - governance
  - phase-1
milestone: m-1
dependencies:
  - TASK-10
references:
  - ADR-REVIEW-AND-MIGRATION-PLAN.md
  - 'https://github.com/cds-snc/sre-bot/issues/1265'
priority: medium
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The root-level analysis documents (ADR-REVIEW-AND-MIGRATION-PLAN.md, architecture-progress-assessment.md, shield-pattern-assessment-analysis.md, claude-research-outcome.md) predate or straddle the new decisions/ corpus and still describe some now-resolved gaps as open (e.g. "transport-slack.md does not exist" - it now does).

Steps:
1. Move the four documents into docs/history/ (or another agreed archive location) with a dated header noting they are point-in-time analyses superseded by decisions/ + the backlog.
2. Where a document is still load-bearing (the migration plan sections referenced by backlog tasks), add a short preface mapping its phases to the backlog milestones instead of rewriting it.
3. Remove tmp.json and other stray analysis artifacts from the repo root if unneeded (plugins-sequence.png, docs/sequenceDiag*.* - confirm with maintainer before deleting).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Repo root contains no unarchived analysis documents; each archived doc carries a superseded-by preface
- [x] #2 No document in the repo asserts a decision record is missing that now exists in decisions/
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Maintainer confirmed the disposition of stray artifacts before deletion
- [x] #2 No live backlog artifact (task, doc, or milestone) cites a path that no longer exists without it being an acknowledged historical reference; the deleted root docs were never committed, so no path-migration was needed
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Research findings (grounding) - revised 2026-07-29 after TASK-10 merged

1. **TASK-10 is now Done** (merged to `main`). Its final, human-ratified resolution changes the calculus for this task: `docs/adr/` (44 records + INDEX.md + templates/) was **deleted outright** - no banner file, no archive folder kept in the tree. Rationale recorded on TASK-10: "git history preserves it... no banner/archive folder is kept in the working tree." The entire top-level `docs/` directory is now gone from the repo (confirmed: `docs/` no longer exists at all, not just `docs/adr/`). This is a real, human-confirmed precedent against introducing a new `docs/history/` folder for TASK-11 - doing so would immediately reintroduce the exact kind of in-tree archive tree TASK-10 just eliminated on purpose.
2. TASK-10 also explicitly scoped its citation cleanup NARROWLY (only the two live, dangling production docstrings) and deferred a broader "repo-wide citation-hygiene sweep" (stale ADR-number/path citations in `app/infrastructure/operations/result.py:7`, `app/packages/access/request/__init__.py:9`, `app/modules/ops/notifications.py:13`) as a **candidate separate follow-up task, not yet filed**. That's a related but distinct concern from TASK-11 (app-code docstrings vs. root analysis documents) - not folding it in here, but noting it exists as an open opportunity.
3. Root-doc state is otherwise unchanged from the prior research pass: all 6 candidate docs remain **untracked** (`ADR-REVIEW-AND-MIGRATION-PLAN.md`, `shield-pattern-assessment-analysis.md`, plus the 4 newer 2026-07-28 advisory docs), `tmp.json` remains untracked+gitignored, `architecture-progress-assessment.md`/`claude-research-outcome.md` still don't exist anywhere, `plugins-sequence.png`/`docs/sequenceDiag*.*` still don't exist. README.md now has a working "Architecture & Decision Records" section linking to `decisions/README.md` (added by TASK-10) - unrelated to this task but confirms the reading-order pointer already exists at the repo-README level.
4. **Revised recommendation given the TASK-10 precedent**: delete `ADR-REVIEW-AND-MIGRATION-PLAN.md` and `shield-pattern-assessment-analysis.md` outright rather than moving them into a new `docs/history/` folder - consistent with the just-set convention, and avoids recreating the `docs/` tree TASK-10 removed. Caveat that materially differs from the docs/adr case: docs/adr's content is recoverable via git history because it had 20+ months of real commit history before deletion; these two root docs were **never committed at all**, so deleting them without ever committing means the content is **not recoverable from git afterward** - a genuine, permanent loss, not just "history instead of working tree." Flagged explicitly below as a decision the human must make knowingly (not the same risk profile as TASK-10's precedent, even though the *policy* - no in-tree archive - is the same).
5. This resolves/narrows the previously open questions:
   - Archive-vs-delete (old Q1): now recommend **delete**, per TASK-10 precedent - conditional on the human accepting the permanent-loss caveat in finding 4 above (option to commit-once-then-delete remains available if they want recoverability, see Steps).
   - Milestone `m-0` CLI-edit gap (old Q2): **becomes moot** under the delete approach - there is no new path to update its citation to, so it is left as a harmless historical/prose reference (mirrors how TASK-10 left `docs/adr/decision-record-governance.md`'s own internal cross-references behind once that whole folder was deleted - no attempt was made to scrub every citation of deleted content). No CLI or hand-edit needed for `m-0`.
   - Scope of the 4 newer (2026-07-28) advisory docs (old Q3): **still open**, unaffected by TASK-10.
   - Skip-PR / mark-ACs-done ask (old Q4): unchanged - still correct that the raw deletions need no PR (untracked), still not something this planning session can execute or close out.
6. TASK-11's own **Definition of Done #1 wording ("refs updated to new paths") assumes a move-based approach** and doesn't fit a delete-based approach (there is no new path to update refs to under Option A below). This is a direct conflict between the task's original authored intent and the now-precedented delete approach - flagged for explicit human sign-off rather than silently rewritten.

## Steps

1. **Human decision gate (blocking)**: choose between
   - **Option A - delete outright (recommended, matches TASK-10 precedent)**: `rm ADR-REVIEW-AND-MIGRATION-PLAN.md shield-pattern-assessment-analysis.md` with no prior commit. Zero git diff, no PR needed for the deletion itself. Accept that the content becomes permanently unrecoverable (finding 4). Backlog citations (`doc-1`, `m-0`, TASK-3/12/50) are left as historical/prose references, same treatment TASK-10 gave its own internal dangling citations - no CLI edits required for those. Requires loosening TASK-11's DoD#1 (see Step 3).
   - **Option B - preserve then delete**: commit the two files once (at their current root paths, with the dated preface prepended) in one PR commit, then delete them in a second commit in the same PR, so git history retains a recoverable snapshot without leaving anything in the working tree. Caveat: if this repo squash-merges PRs, the two commits collapse into a net-zero diff and the "preserved" commit is never reachable on `main` - confirm the repo's merge strategy before relying on this for recoverability.
2. Regardless of A/B: delete `tmp.json` locally (untracked + gitignored, zero git diff, no PR needed - confirmed superseded VS Code editor settings, already covered by `.vscode/settings.json`).
3. If Option A is chosen: rewrite TASK-11's DoD#1 (requires human approval, since it changes the task's own committed Definition of Done) from "refs updated to new paths" to something like "no live backlog artifact cites a path that no longer exists without it being an acknowledged historical reference" - matching what actually happened for docs/adr's own leftover citations under TASK-10. If Option B is chosen, DoD#1 as originally written still applies (paths become `docs/history/...`, TASK-3/12/50/doc-1 refs get updated via `backlog task edit --ref` / `backlog doc update`, and `m-0`'s prose citation is left as-is since no CLI update path exists for milestones - same conclusion as the prior planning pass).
4. `architecture-progress-assessment.md` / `claude-research-outcome.md`: still no file action (neither exists). Only remaining action either way: annotate or accept `doc-1`'s dangling citation of `claude-research-outcome.md` as an external, uncommitted research input (optional hygiene, not required by any AC).
5. `plugins-sequence.png` / `docs/sequenceDiag*.*`: no action, already absent.
6. Leave the 4 newer (2026-07-28) root advisory docs untouched pending explicit scope confirmation (unchanged from prior pass - open question, not resolved by TASK-10).
7. Verification pass:
   - Root file listing has no standalone analysis `.md` beyond `README.md` (plus the 4 out-of-scope docs per Step 6, if confirmed out of scope) - AC#1 check.
   - Under Option A, no document exists to make a stale "missing decision record" claim at all - AC#2 trivially satisfied. Under Option B, the preface added before deletion neutralizes the stale claims in the git-history snapshot (moot in the working tree either way once deleted).
8. Maintainer sign-off required on: Option A vs B (finding 4's permanent-loss caveat), the DoD#1 rewording (Step 3), and disposition of `tmp.json`/the 4 newer docs - satisfies DoD#2.

## AC / Step traceability

- AC#1 <- Steps 1, 2, 6, 7
- AC#2 <- Steps 1, 7
- DoD#1 <- Step 3 (reworded under Option A, or satisfied via ref updates under Option B)
- DoD#2 <- Step 8

## Assumptions / doubts requiring human sign-off (updated)

1. **Option A vs Option B** (delete-only vs preserve-then-delete): recommend Option A for consistency with TASK-10's precedent, conditional on the human accepting that the two documents' content becomes permanently unrecoverable (they were never committed, unlike docs/adr which had real prior history). If recoverability matters, Option B, with the squash-merge caveat called out explicitly.
2. **DoD#1 rewording**: needs explicit approval since it's a change to the task's own authored Definition of Done, not just an implementation detail.
3. Scope of the 4 newer (2026-07-28) advisory docs under AC#1's broad wording - still unresolved, independent of TASK-10.
4. (Carried over, still accurate) Raw document deletions need no PR (untracked files); any backlog-metadata edits that are still chosen (Option B's ref updates, or the optional `doc-1` citation hygiene) do need a normal reviewed PR; this planning session still cannot execute deletions, edit ACs/DoD, or move the task's status - that requires an implementation pass plus human verification.

## Blast radius / rollback

- Zero `app/**` changes; zero risk to running code or tests, under either option.
- Option A: no tracked-file changes at all beyond the optional DoD#1 rewording and optional `doc-1` citation hygiene edit - smallest possible footprint.
- Option B: one small PR (2 doc files added-then-removed across two commits, `doc-1` ref update, TASK-3/12/50 ref updates) - same small footprint as previously planned.
- Rollback is trivial either way: revert the small commit(s); the untracked-file deletions have no git footprint to roll back regardless.

## Size / gate verdict

Still fits comfortably in a single small PR (or requires no PR at all under Option A for the document deletions themselves). No decomposition needed.
<!-- SECTION:PLAN:END -->
