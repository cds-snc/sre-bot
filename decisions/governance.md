---
status: Accepted
date: 2026-07-06
applies: now
scope: How decision records are written, accepted, and changed.
---

# Decision Governance

## Context

The previous corpus (`docs/adr/`) failed in specific, diagnosed ways: records grew to 20 KB+, "Accepted" meant "hoped for," decision reversals never propagated to the records that cited the old rule, and a tier/domain/concern taxonomy cost effort without ever resolving a conflict. This record replaces that system with the smallest one that works for a team of one-to-few.

## Decision

**Format.** One decision per file, flat kebab-case filename, **two pages maximum**. Frontmatter has exactly four fields: `status`, `date`, `applies`, `scope`. Body sections: **Context** (including the *current state of the code*, honestly), **Decision**, **Consequences** (tradeoffs included), **Checks**, and — when `applies: target` — **Migration** (ticket link + divergences currently tolerated).

**Statuses.** `Draft` → `Accepted` → `Superseded` (with a pointer) or `Rejected` (with the real reason) — a trimmed variant of the MADR 4 / Nygard vocabulary (`proposed/rejected/accepted/deprecated/superseded`): `Draft` stands in for `proposed`, and `deprecated` folds into `Superseded`. There are no tiers, domains, or concern tags. (MADR frontmatter is explicitly extensible, so the extra `applies` field is an extension, not a fork.)

**Two axes, deliberately.** `status` records the *decision* state; `applies` records the *implementation* truth. `Accepted` means "this is the binding rule for all new code from today" — it does **not** claim the legacy code already complies. That claim belongs to `applies`: `now` means the Checks pass on `main`; `target` means they don't yet, and the record must name its migration ticket and list the tolerated divergences. (Pure MADR would leave unimplemented decisions as `proposed`, but then a codebase mid-migration has no binding rules at all; a Draft here means the *decision itself* is still open.) The old corpus's failure was collapsing these axes and letting "Accepted" describe fiction.

**The honesty rule.** A record may carry `applies: now` only while its Checks pass on `main`. CI does not lie; neither do we.

**The cascade rule.** Any PR that changes a record's status or reverses a decision must grep this folder for references to the changed record and update every one in the same PR. This is the rule whose absence broke the old corpus.

**Checks are executable or deleted.** Each record's Checks section lists only things a CI step, a lint rule, or a five-minute review can verify. Aspirations are not checks.

**Why vs how.** Decisions record *why* and the binding rule. Long procedural detail (step-by-step recipes, exhaustive tables) belongs in code, tests, or a feature package README — not here. If a record is growing past two pages, it is trying to be a design document; split the decision out and delete the rest.

**Sources.** Cite the current codebase freely — describing reality is required, not forbidden. External sources: at most the two or three that actually ground the decision.

## Consequences

- Less impressive-looking documentation; drastically higher trustworthiness.
- Some nuance is lost versus 800-line records. That nuance was not being maintained anyway.
- The `applies` field makes the migration state visible in the index instead of hidden in prose.

## Checks

- Every file in `decisions/` has the four frontmatter fields and is under ~150 lines.
- No record with `applies: now` has a failing check (spot-audit quarterly, or when touched).
- `README.md`'s index matches the folder contents (review on every decisions PR).
