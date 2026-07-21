---
name: implementation-planning
description: Author review-ready implementation plans grounded in real code, with a hard single-PR size gate and decomposition into safe incremental tasks when exceeded.
---

# Implementation Planning

Use this skill when writing the implementation plan for a backlog task (checkpoint #2 for human review). A plan is a contract: reviewable in minutes, executable without re-research, and sized for a single reviewable PR.

## Ground the Plan in Real Code

1. Never plan from memory or from the task description alone. Run the searches (`rg`, `grep -rn`), read the files, and enumerate exact call sites (`path:line`) the change will touch.
2. Read every file listed under the task's `references:` frontmatter (decision records, linked issues) before writing a line of plan.
3. If the description says "find every place that does X", the plan must contain the found list, not repeat the instruction.

## Required Plan Contents

1. **Ordered steps** — each step names exact files and what changes in them.
2. **AC traceability** — every acceptance criterion maps to at least one step and one named test; every step maps back to an AC or is justified as enabling work.
3. **Test matrix** — happy path, boundary, failure, and (where relevant) authorization/idempotency cases, with intended test file names per `testing-standards`.
4. **Assumptions and doubts** — everything the plan takes on faith, each with how to verify it (for example: "assumes all environment branching reads the typed `ENVIRONMENT` and that `PREFIX` is read only by frozen `app/modules/` command registration — verify with repo-wide grep including terraform/ and scripts/").
5. **Blast radius and rollback** — what breaks if this ships wrong, whether a single `git revert` restores service, and any ordering constraints (for example: env vars must exist in manifests before code requiring them merges).

## Single-PR Size Gate (MANDATORY)

Estimate the diff before finalizing any plan: production files touched, production LOC changed (tests excluded), subsystems crossed. Then apply the gate.

The task MUST be decomposed into smaller tasks when ANY of these hold:

1. Estimated production diff exceeds ~400 changed LOC or ~10 files.
2. The change crosses more than two subsystems in one PR (for example app code + terraform + CI pipeline).
3. It mixes a mechanical refactor (rename, move, signature change) with a behavior change. These are separate PRs: mechanical diffs are reviewed for completeness, behavior diffs for correctness — mixing them makes both unreviewable.
4. It can be staged with expand/contract (add new path → migrate consumers → remove old path) but is planned as one big-bang change.
5. A single `git revert` of the PR would not safely restore the previous behavior.

This gate is non-negotiable: oversized PRs cannot be properly reviewed by the dev team, and unreviewable changes are a delivery risk regardless of code quality.

## How to Decompose

1. Slice by the expand/contract pattern, not by layer: each slice must be independently shippable, deployable, and revertible with main staying green after each merge.
   - Slice 1 (expand): add the new capability alongside the old, unused or behind a flag/default that preserves behavior.
   - Slice 2..n (migrate): move consumers over in small groups; each slice keeps both paths working.
   - Final slice (contract): remove the old path and its guards.
2. Order slices so environment/config prerequisites land first (CI variables, terraform, compose examples) when later slices fail without them.
3. Create the subtasks via CLI, wiring dependencies so ordering is explicit:

```bash
backlog task create "Slice title" \
  -d "Scoped description" \
  --ac "Independently verifiable criterion" \
  --dep TASK-1 --parent TASK-1 \
  --ref decisions/<record>.md \
  -l <labels> -m <milestone> --priority <p>
```

4. Repoint the original task: either narrow it to slice 1, or keep it as the coordinator whose ACs become "all subtasks done".
5. Present the proposed breakdown (slice titles, scope, dependency order, estimated size per slice) to the human for approval BEFORE creating tasks. Task breakdown is a human checkpoint.

## Right-sizing Heuristics

- Target per-slice diff: reviewable in under ~30 minutes (roughly ≤400 production LOC, ≤10 files).
- Each slice's ACs must be verifiable without the later slices existing.
- If a slice cannot be described in one sentence without "and", split it again.
- Config/manifest-only slices (CI, terraform, env examples) are cheap to review — prefer isolating them.

## Anti-patterns

- A plan that restates the task description instead of enumerating discovered call sites.
- "Big-bang" migration PRs that add the new path, migrate all consumers, and delete the old path at once.
- Slices that only compile together (not independently shippable).
- Decomposing by architectural layer (one PR of models, one of services, one of routes) — slices must each deliver verifiable behavior.
- Creating subtasks without `--dep`/`--parent` wiring, losing execution order.
