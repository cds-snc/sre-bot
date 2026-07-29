---
id: TASK-10
title: Adopt decisions/ as sole source of truth; delete docs/adr/ and its machinery
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 16:20'
labels:
  - governance
  - phase-1
milestone: m-1
dependencies: []
references:
  - decisions/governance.md
  - decisions/README.md
  - 'https://github.com/cds-snc/sre-bot/issues/1264'
priority: high
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/governance.md. decisions/*.md supersedes docs/adr/ (44 records). docs/adr/ is deleted outright; git history preserves it for anyone who needs to consult prior ADR content - no banner/archive folder is kept in the working tree.

Steps:
1. Delete docs/adr/ entirely (all decision-record files, INDEX.md, templates/) - git history is the historical record, no in-tree banner needed.
2. Confirm the ADR index machinery (.github/scripts/generate_adr_indexes.py) does not exist and no workflow references docs/adr - nothing further to delete there.
3. Add a short section to the repo README linking to decisions/README.md's reading order.
4. Clean the two production docstring citations of the now-deleted docs/adr/ (app/integrations/aws/settings.py, app/integrations/aws/shield.py) to state the rule factually instead of citing the removed path. Do not touch other decisions/*.md citations elsewhere in the codebase (out of scope, candidate for a separate follow-up task).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 docs/adr/ no longer exists in the repository tree (fully removed, not banner-archived); repo README links to decisions/README.md
- [x] #2 No script, workflow, or in-tree file generates or validates docs/adr indexes (the folder itself is gone)
- [x] #3 app/integrations/aws/settings.py and shield.py no longer cite docs/adr/*; the rule is stated factually, not by citation
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 PR merged with reviewer sign-off on what was archived vs deleted
- [x] #2 PR references decisions/governance.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Implementation Plan (TASK-10) - REVISED 2026-07-29

Scope changed from the original banner+selective-delete approach: `docs/adr/` is deleted OUTRIGHT (all 44 decision-record files + INDEX.md + templates/), not archived with an in-tree README banner. Git history is the historical record for anyone who needs to consult prior ADR content - this resolves the original plan's step 1/step 2 contradiction (a "kept for history, do not update" banner directory vs. "delete the machinery tied to it" were pulling in opposite directions for the same folder).

Size: still trivial, docs-only, single PR. Files touched: ~47 deleted (44 records + INDEX.md + 2 template files), 1 edited (root README.md), 2 edited (docstring citation cleanup). Zero production behavior change. No decomposition needed.

### Codebase findings (verified 2026-07-29)
- `.github/scripts/generate_adr_indexes.py` does NOT exist anywhere in the repo (`.github/scripts/` directory itself does not exist; only `.github/workflows/scripts/run-shellcheck.sh` exists, unrelated). Referenced only in prose (`docs/adr/decision-record-governance.md`'s own Confirmation section, `ADR-REVIEW-AND-MIGRATION-PLAN.md`) - both of which are being deleted along with the rest of `docs/adr/`. Nothing to delete for this bullet; it becomes moot once the folder is gone.
- No `.github/workflows/*.yml` references `docs/adr` in any form (grep across every workflow file: zero hits). Full deletion is safe from a CI/tooling standpoint.
- Zero inbound references to `docs/adr/INDEX.md` or `docs/adr/templates/*` from anywhere else in the repo.
- Root `README.md` has zero references to either `docs/adr/` or `decisions/` today - still need the new linking section regardless of banner-vs-delete.
- `decisions/README.md` already states the supersession and does not need to change.
- Two LIVE production docstrings cite the path being deleted and MUST be cleaned as part of this same PR (dangling references otherwise):
  - `app/integrations/aws/settings.py:10` - docstring: "Feature-domain configuration ... lives with the consuming feature per `docs/adr/configuration-ownership.md`." Rewrite to state the rule factually (settings partitioning: vendor-transport concerns here, feature-domain config lives with the owning feature) without citing any doc path.
  - `app/integrations/aws/shield.py:46` - docstring: "Owns SDK construction with native retry configured per `docs/adr/outbound-retry-policy.md`..." Rewrite to state the rule factually (SDK-native retry configuration, not hand-rolled backoff) without citing any doc path.
- Per explicit human decision this session (asked via clarifying question): the citation cleanup is SCOPED ONLY to these two dangling `docs/adr` citations. Repo-wide `decisions/*.md` citations (e.g. `app/infrastructure/configuration/app.py`'s three "see decisions/security.md SEC-1" error-message citations) and other stale/orphaned ADR references found during this research (`app/infrastructure/operations/result.py:7` cites a dead path `docs/decisions/tier-1-foundation/ADR-001-operation-result-pattern.md` that predates even the old `docs/adr/` layout; `app/packages/access/request/__init__.py:9` cites "ADR-0059 Standard 3"; `app/modules/ops/notifications.py:13` cites "the logging ADR" vaguely; two test-docstring citations of `decisions/observability.md`) are explicitly OUT OF SCOPE for TASK-10 - left untouched, flagged as a candidate separate follow-up task (a repo-wide citation-hygiene sweep), not folded in here.

### Steps
1. Delete `docs/adr/` in its entirety: all decision-record `.md` files, `INDEX.md`, and `templates/` (both `decision-record-template.md` and `adr-metadata-reference.md`). No banner file is created or kept in the tree - git history at the commit before this deletion is the durable historical reference.
2. Confirm (no action needed) that `.github/scripts/generate_adr_indexes.py` does not exist and no workflow references `docs/adr` - both already verified true.
3. Edit root `README.md`: add a new section (after "## Project Structure", before "## Security & Privacy") linking to `decisions/README.md` as the architecture/decision-record source of truth, noting `docs/adr/` has been retired (historical content available via git history/tags, not in the working tree). Keep the existing `---` section-separator convention.
4. Edit `app/integrations/aws/settings.py`'s module docstring: replace the `docs/adr/configuration-ownership.md` citation with a factual, self-contained statement of the settings-partitioning rule (no external doc reference).
5. Edit `app/integrations/aws/shield.py`'s class docstring: replace the `docs/adr/outbound-retry-policy.md` citation with a factual, self-contained statement of the SDK-native-retry rule (no external doc reference).
6. Do not touch any other file's `decisions/*.md` or ADR-number citations (out of scope per the human's explicit scoping decision this session).

### AC-to-step traceability
- AC#1 (docs/adr/ no longer exists in the tree; repo README links to decisions/README.md) -> Steps 1, 3.
- AC#2 (no script/workflow/in-tree file generates or validates docs/adr indexes) -> Step 1 (deleting the folder removes INDEX.md/templates outright) + Step 2 (script already absent).
- AC#3 (the two dangling docs/adr docstring citations are cleaned to be factual, not citations) -> Steps 4, 5.

### Test strategy
Documentation/docstring-only change; no application code behavior change, no automated tests apply to steps 1-3. For steps 4-5 (docstring text edits, no signature/behavior change): existing test suites for `app/integrations/aws/` continue to pass unmodified (docstrings are not asserted on) - run `cd app && uv run pytest tests/integrations/aws -q` as a smoke check that nothing else broke incidentally.
Manual/reviewer verification:
- `docs/adr/` is fully absent from the working tree (`git status`/`ls docs/adr` shows nothing).
- Root `README.md`'s new section link resolves to `decisions/README.md`.
- `settings.py`/`shield.py` docstrings contain no `docs/adr` (or any doc-path) citation and read as standalone factual statements.

### Blast radius / rollback
Docs + two docstrings, zero application behavior change, zero CI/workflow files touched. Fully reversible via a follow-up revert PR (git history retains all deleted content); no data/runtime impact.

### Assumptions / doubts flagged for human review
1. Confirmed with the human (2026-07-29, via clarifying question): docs/adr/ is deleted outright, not banner-archived; citation cleanup is scoped only to the two dangling docs/adr citations, not a repo-wide decisions/*.md sweep.
2. `app/infrastructure/operations/result.py:7`, `app/packages/access/request/__init__.py:9`, and `app/modules/ops/notifications.py:13` all contain stale/orphaned ADR citations (dead paths or vague numbered-ADR references predating the current `docs/adr`/`decisions` layout) discovered during this research. Left untouched per the scoping decision above; recommend filing a separate follow-up task for a repo-wide citation-hygiene pass across decisions/*.md and legacy ADR-number references.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
All three ACs verified and checked. Changes: deleted docs/adr/ (44 records + INDEX.md + templates/) outright; added Architecture & Decision Records section to root README.md linking to decisions/README.md; rewrote docs/adr docstring citations in app/integrations/aws/settings.py and shield.py to factual statements. No workflows touched. DoD items left for human: PR reviewer sign-off on what was deleted (vs archived), and PR description must reference decisions/governance.md.
<!-- SECTION:NOTES:END -->
