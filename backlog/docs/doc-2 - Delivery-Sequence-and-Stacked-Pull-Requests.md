---
id: doc-2
title: Delivery Sequence and Stacked Pull Requests
type: guide
created_date: '2026-09-24 20:23'
updated_date: '2026-09-24 20:23'
---
# Delivery Sequence and Stacked Pull Requests

How the plugin-architecture migration backlog is delivered: the order of work, which changes go in a stacked pull request, and which ship as standalone PRs. The target and the milestones are in doc-1 (Migration Plan). The dependencies recorded on each task are authoritative; this document explains the order they produce.

## Stacked pull requests

GitHub stacked pull requests are available in our organization (feature in public preview). References: [about stacked PRs](https://docs.github.com/en/enterprise-cloud@latest/pull-requests/get-started/about-stacked-prs), [merging](https://docs.github.com/en/enterprise-cloud@latest/pull-requests/how-tos/merge-and-close-pull-requests/merging-stacked-pull-requests), [CLI commands](https://docs.github.com/en/enterprise-cloud@latest/pull-requests/reference/stacked-prs-cli-commands), [CI](https://docs.github.com/en/enterprise-cloud@latest/pull-requests/how-tos/merge-and-close-pull-requests/optimizing-ci-for-stacked-pull-requests).

**How a stack works**
- A stack is a chain of pull requests. The bottom PR targets `main`; each PR above it targets the branch of the PR below.
- Reviewers see one layer's diff at a time. A stack map in the merge box shows every layer and its status.
- CI runs on every layer as if it targeted `main`, so `ci_code.yml` (`pull_request` filtered on `app/**`) needs no change.
- Merging is bottom-up only. You can merge one layer, a contiguous group from the bottom, or the whole stack. Merging a mid-stack PR always merges every PR below it.
- After lower layers merge, the next unmerged PR is rebased onto `main` automatically.
- The merge queue is supported and adds a stack's PRs in order. If one PR leaves the queue, every PR above it leaves too.

**Rules and limits**
- All branches of a stack live in this repository. Cross-fork stacks are not supported.
- Auto-merge is not supported for stacked PRs.
- Every layer must meet `main`'s branch protection on its own: approvals, required checks and a linear stack history. Each layer therefore leaves `main` releasable.

**Commands** (the `gh stack` extension)

```shell
gh extension install github/gh-stack
gh stack init            # start a stack in the current repository
gh stack add <branch>    # add a layer on top of the current stack
gh stack submit          # push every branch and create or update the PRs
gh stack sync            # fetch, cascade-rebase, push and sync PR state
gh stack view            # show the stack
gh stack merge <number>  # merge a stack, or one PR and everything below it
```

These are git write operations and are run by the developer; agents do not run them unless asked (CLAUDE.md git guardrail).

**How we use stacks**
- One layer is one backlog task and one PR. CLAUDE.md's rule "one task, one branch, one PR" is unchanged.
- Stack only a chain where each PR builds on the one below.
- Stack only mechanical or low-risk changes: moves, codemods, contracts, tooling, and refactors that preserve behaviour and are pinned by tests or the smoke suite.
- A change that alters runtime or deployment behaviour ships as a standalone PR and is merged and deployed on its own: boot semantics, the Slack concurrency model, configuration sources, security, cutovers, lease policy.
- Changes that don't depend on each other ship as parallel single PRs. Stacking them would only make each wait for the ones below it.
- Never mix a mechanical move with a behaviour change in one layer.
- A mechanical move rewrites every importer in the same PR. A split that needs a re-export shim is not allowed.

## Critical path

TASK-18, TASK-105 and TASK-25.4 -> TASK-106 -> TASK-26.1 -> TASK-107 -> TASK-110 -> TASK-112 (with TASK-111) -> TASK-114.

TASK-109 (the service registry) is also required before the capability and feature moves. It follows TASK-108, TASK-58 and the TASK-92 decision. Almost every later task depends on TASK-114 and TASK-109.

## Sequence

### Wave 0: independent starts

| Lane | Tasks | Form |
| --- | --- | --- |
| Decisions (docs only) | TASK-92 (health model, gates TASK-109), TASK-117 (i18n library, gates TASK-118), TASK-97 (incident architecture, gates TASK-38), TASK-83.1 (identity Draft records), TASK-104 (CLAUDE.md and skills) | single PRs |
| Critical-path prerequisites | TASK-25.4 (Slack client factory and classifier), TASK-24 (vendor settings, SecuritySettings), TASK-35 (dev/sre registration), TASK-36 (smoke harness), TASK-14 | single PRs |
| Storage | TASK-27.1 (vendor-neutral read) | single PR, behaviour change |
| Live defects | TASK-99 (Tier-2 jobs safe to run twice), TASK-72 (i18n memory growth), TASK-86, TASK-95, TASK-96 | single PRs |
| Vendor cleanup (m-3) | TASK-25.2.6.3, TASK-25.5, TASK-25.6, TASK-25.8, TASK-25.9, TASK-84, TASK-85, TASK-87.1 -> TASK-87.3, TASK-87.2 | parallel single PRs |

### Wave 1: contracts spine

| Stack | Layers (bottom -> top) | Risk |
| --- | --- | --- |
| A: contracts spine | TASK-18 (import-linter) -> TASK-105 (OperationResult envelope) -> TASK-106 (create contracts/) -> TASK-26.1 (Slack handler contract; requires TASK-25.4 merged) -> TASK-107 (hookspecs to contracts/) | low: configuration, types, codemod moves. TASK-26.1 changes every Slack hookimpl signature and gets the closest review. |
| B: logging | TASK-28.2 -> TASK-28.3 -> TASK-115 (logging setup to server/) | low |

Single PRs: TASK-28.1; TASK-94 (alarm filters, Terraform) after TASK-28.2.

### Wave 2: registry and plugin host

| Stack or PR | Content | Form |
| --- | --- | --- |
| C: registry | TASK-108 (storage Protocol to contracts/) -> TASK-102 (ownership-checked release) -> TASK-58 (coordination rename) -> TASK-109 (svcs registry) | stack; starts once Stack A's TASK-106 and TASK-27.1 have merged; TASK-109 also needs the TASK-92 decision |
| TASK-100 | lease re-read fail-open | single PR, after TASK-99 and TASK-58 |
| TASK-110 | entry-point plugin loading; plugin load failures become fatal | single PR, deployed and observed on its own |
| TASK-111 | TOML configuration files | single PR, coordinated with the Terraform and SSM changes |
| TASK-25.10 | OpenAI onto the outbound-client contract | single PR, after TASK-106 |
| D: host tooling | TASK-112 (per-environment enablement) -> TASK-113 (extension-point phase) -> TASK-114 (generator and shape check) | stack; no runtime change while every plugin is enabled by default |

### Wave 3: framework services into server/

| Stack or PR | Content | Form |
| --- | --- | --- |
| TASK-26.2 | Slack runtime, parser, formatter and help to server/slack/ | single PR (mechanical, large) |
| TASK-33 | async Bolt | single PR with a soak period; highest-risk runtime change in the plan |
| TASK-116 | security to server/security/ with the current-user contract | single PR |
| TASK-118 | translator contract and implementation | single PR, after TASK-117 |
| E: scheduler | TASK-64 (widen the registry) -> TASK-52 (runtime to server/scheduler/) | stack |

### Wave 4: capability and feature moves

These are mechanical moves with no dependencies between them. Ship them as parallel single PRs. For a single review sitting, short stacks of two or three are acceptable.

- Capabilities: TASK-119 (directory), TASK-120 (drive), TASK-121 (spreadsheets), TASK-122 (audit), TASK-123 (rotations), TASK-32 (notifications placeholder). TASK-25.7 (Sentinel) follows TASK-122.
- Features: TASK-124.3 (rant), TASK-124.6 (geolocate), TASK-124.4 (talent), TASK-124.2 (oncall_sync, after TASK-123), TASK-124.5 (incident umbrella, after TASK-120 and TASK-25.10).

### Wave 5: behaviour-changing tracks

| Track | Order | Form |
| --- | --- | --- |
| Webhooks | Stack F: TASK-37.1 -> TASK-37.2 -> TASK-37.3 (behaviour-preserving, held by the smoke suite); then TASK-37.4 (cutover), TASK-47 (HMAC), TASK-48 and TASK-49 in parallel, TASK-37.5 | stack F, then single PRs |
| Approvals | TASK-60 -> TASK-125 -> TASK-61 -> TASK-30; then TASK-62 and TASK-63; TASK-124.1 (access) after TASK-61 and TASK-30 | single PRs |
| Identity | TASK-83.3 and TASK-83.12 early; TASK-83.2 -> TASK-83.4 -> TASK-83.5 and TASK-83.6 -> TASK-83.7 -> TASK-83.8; TASK-83.9 -> TASK-83.10 after TASK-38 | single PRs |
| Legacy rebuild by surface | TASK-38 (per the TASK-97 packet), TASK-39, TASK-88, TASK-40, then TASK-41; TASK-53, TASK-55, TASK-56 and TASK-65 ride with the surfaces that own them | single PRs per surface |

## Standalone merges

These change runtime or deployment behaviour. Merge and deploy each one separately:
- TASK-110: plugin load failures abort boot.
- TASK-111: configuration moves to files.
- TASK-33: async Bolt.
- TASK-100: lease read-failure policy.
- TASK-37.4: webhooks cutover.
- TASK-47: HMAC enforcement.
- TASK-61: approvals refactor.
- TASK-30: event bus deletion.
- Each legacy surface cutover.
