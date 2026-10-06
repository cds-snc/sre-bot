---
id: doc-2
title: Delivery Sequence and Stacked Pull Requests
type: guide
created_date: '2026-09-24 20:23'
updated_date: '2026-10-06 16:23'
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
- Whole-stack merges fail here. `main` requires approval of the most recent reviewable push, so merging a stack in one step merges only the bottom layer: GitHub rebases the remaining layers onto `main` and force-pushes them, which makes their approvals stale. Merge layers manually, bottom-up, one at a time, and get a re-approval for each rebased layer. Don't push to stack branches while waiting on re-approvals. Expect one re-approval round per layer, so keep stacks short.

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
- Each stack has a handoff doc under `backlog/docs/stacks/` that records its current state. Sessions start and end with the `stacked-pr-session` skill, which ends every session with a resume prompt.
- When a stack's next layer is blocked on work outside the stack, pause the stack rather than build around the blocker. The handoff doc then records the resume conditions, and the submitted layers go through review and merge on their own.

## Critical path

TASK-18, TASK-105 -> TASK-105.1 -> TASK-105.2 -> TASK-105.3 -> TASK-106 -> TASK-26.1 (as TASK-26.1.1 -> TASK-26.1.2 -> TASK-26.1.3; also after TASK-25.4, and TASK-35 -> TASK-36) -> TASK-107 (as TASK-107.1 -> TASK-107.2 -> TASK-107.3 -> TASK-107.4) -> TASK-110 -> TASK-112 (with TASK-111) -> TASK-114.

TASK-109 (the service registry) is also required before the capability and feature moves. It follows TASK-108, TASK-58 and the TASK-92 decision. Almost every later task depends on TASK-114 and TASK-109.

## Sequence

### Wave 0: independent starts

| Lane | Tasks | Form |
| --- | --- | --- |
| Decisions (docs only) | TASK-92 (health model, gates TASK-109), TASK-117 (i18n library, gates TASK-118), TASK-97 (incident architecture, gates TASK-38; decided 2026-10-02, decisions/incident-management.md, with the TASK-38.1 to TASK-38.8 packet and the expansion drafts DRAFT-1 to DRAFT-7 that start after this sequence), TASK-83.1 (identity Draft records), TASK-104 (CLAUDE.md and skills) | single PRs |
| Critical-path prerequisites | TASK-25.4 (Slack client factory and classifier), TASK-24 (vendor settings, SecuritySettings), TASK-35 (sre single registration) -> TASK-36 (legacy-surface inventory and pinning tests for the 8 Slack command hookimpls) | single PRs; TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515) have merged |
| Legacy-surface pinning | TASK-36.1 (hard-coded slash commands and interactions), TASK-36.2 (webhook route), TASK-36.3 (scheduled jobs), each after TASK-36 | parallel single PRs; each gates the rebuilds that change its surface |
| Storage | TASK-27.1 (vendor-neutral read) | single PR, behaviour change |
| Live defects | TASK-99 (Tier-2 jobs safe to run twice), TASK-72 (i18n memory growth), TASK-86, TASK-95, TASK-96 | single PRs |
| Vendor cleanup (m-3) | TASK-25.2.6.3, TASK-25.5, TASK-25.6, TASK-25.8, TASK-25.9, TASK-84, TASK-85, TASK-87.1 -> TASK-87.3, TASK-87.2 | parallel single PRs |

### Wave 1: contracts spine

| Stack | Layers (bottom -> top) | Risk |
| --- | --- | --- |
| A: contracts spine | TASK-18 (import-linter) -> TASK-105 (OperationResult envelope) -> TASK-105.1 (drop provider/operation, delete the unused operations classifiers) -> TASK-105.2 (error-code registry) -> TASK-105.3 (clear the call-site mypy errors from TASK-105's optional message) -> TASK-106 (create contracts/, adds the contracts import-linter contract) -> TASK-26.1.1 (Slack command models to contracts/) -> TASK-26.1.2 (Slack lookups behind package adapters) -> TASK-26.1.3 (Slack registrar and reply Protocols; every hookimpl) -> TASK-107.1 (scheduler registration Protocol to contracts/) -> TASK-107.2 (i18n resource spec to contracts/) -> TASK-107.3 (hookspecs and markers to contracts/) -> TASK-107.4 (plugin manager to server/plugins/) | low: configuration, types, codemod moves. TASK-26.1.3 changes every Slack hookimpl signature and gets the closest review. |
| B: logging | TASK-28.2 -> TASK-28.3 -> TASK-115 (logging setup to server/) | low |

Stack A status (2026-10-02): complete and merged. Part 1 (TASK-18 through TASK-106, #1504-#1511, stack #1506) and part 2 (TASK-26.1.1 through TASK-107.4, #1517-#1519 and #1521-#1524, stack #1520) are on `main`, as are the prerequisites TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515). The next critical-path task is TASK-110. The stack's handoff doc was retired on 2026-10-02; its open follow-ups moved to the tasks that own them: TASK-137 (mypy errors in infrastructure/i18n), TASK-110 (the uncalled discovery functions in server/plugins/manager.py, the entry points, and the `PLUGIN_NAMESPACE` check in a real image build) and TASK-67 (stale since TASK-26.1.3).

Stack A review follow-up: TASK-136 (Protocols are named for their role; the `Port` suffix is retired) came out of the review of #1518 and #1519. It shipped as three single PRs from `main`, all merged: TASK-136.1 (the recorded rule, `SlackReplySender`; #1525), TASK-136.2 (`IncidentDocumentStore`; #1526) and TASK-136.3 (packages/access; #1527). `IncidentChannelPort`, its provider function and the test names that go with them are left to TASK-135.

Single PRs: TASK-28.1; TASK-94 (alarm filters, Terraform) after TASK-28.2; TASK-133 (AWS and Google classifiers emit registry codes) after TASK-105.2, standalone because it changes the codes callers see.

### Wave 2: registry and plugin host

| Stack or PR | Content | Form |
| --- | --- | --- |
| C: registry | TASK-108 (storage Protocol to contracts/) -> TASK-102 (ownership-checked release) -> TASK-58 (coordination rename) -> TASK-109 (svcs registry) | stack; starts once Stack A's TASK-106 and TASK-27.1 have merged (TASK-106 has; TASK-27.1 is open as of 2026-10-02); TASK-109 also needs the TASK-92 decision |
| TASK-100 | lease re-read fail-open | single PR, after TASK-99 and TASK-58 |
| TASK-110 | as TASK-110.1 (modules.sre and modules.dev onto explicit legacy registration, behaviour-preserving) -> TASK-110.2 (entry-point plugin loading; plugin load failures become fatal); split on 2026-10-06 for the single-PR gate | two single PRs in order, not a stack; TASK-110.2 is deployed and observed on its own |
| TASK-111 | TOML configuration files | single PR, coordinated with the Terraform and SSM changes |
| D: host tooling | TASK-112 (per-environment enablement) -> TASK-113 (extension-point phase) -> TASK-114 (generator and shape check) | stack; no runtime change while every plugin is enabled by default |

### Wave 3: framework services into server/

| Stack or PR | Content | Form |
| --- | --- | --- |
| TASK-26.2 | Slack runtime, parser, formatter and help to server/slack/ | single PR (mechanical, large), after TASK-36.1 |
| TASK-33 | async Bolt | single PR with a soak period; highest-risk runtime change in the plan |
| TASK-116 | security to server/security/ with the current-user contract | single PR |
| TASK-118 | translator contract and implementation | single PR, after TASK-117 |
| E: scheduler | TASK-64 (widen the registry) -> TASK-52 (runtime to server/scheduler/, after TASK-36.3) | stack |

### Wave 4: capability and feature moves

These are mechanical moves with no dependencies between them. Ship them as parallel single PRs. For a single review sitting, short stacks of two or three are acceptable.

- Capabilities: TASK-119 (directory), TASK-120 (drive), TASK-121 (spreadsheets), TASK-122 (audit), TASK-123 (rotations), TASK-32 (notifications placeholder). TASK-25.7 (Sentinel) follows TASK-122. TASK-25.10 (OpenAI onto the outbound-client contract, creating the text-generation capability) moved here from Wave 2 on 2026-10-01: it now creates a capability, so it waits for TASK-110 and TASK-114 like the others. TASK-134 (structured template fill in that capability) follows it. TASK-138 (calendar capability, from packages/incident/scheduling; TASK-38.6 consumes it) was added on 2026-10-02 by the TASK-97 decision.
- Features: TASK-124.3 (rant), TASK-124.6 (geolocate), TASK-124.4 (talent), TASK-124.2 (oncall_sync, after TASK-123), TASK-124.5 (incident umbrella with core/ and the scribe subdomain, after TASK-120, TASK-134 and TASK-135; the adapter-only packages documents, drive, meet and scheduling move as they are and are folded in by TASK-38).
- Incident reshape, a behaviour-preserving refactor and not a move: TASK-135 (incident_draft and incident_summary become the scribe subdomain over incident/core), as TASK-135.1 -> TASK-135.2 and TASK-135.3 (parallel) -> TASK-135.4, after TASK-26.1; TASK-25.10 blocks no slice and the TASK-97 decision (2026-10-02) unblocked TASK-135.4. Delivered as Stack G (human, 2026-10-02): TASK-135.1 -> TASK-135.2 -> TASK-135.3 -> TASK-135.4 -> TASK-135.5, bottom-up, one task per layer; TASK-135.4 was split after implementation for review size, into TASK-135.4 (add packages/incident/scribe, unregistered) and TASK-135.5 (register it and delete the two packages), and 135.2 and 135.3, independent in content, were ordered summary first. Stack G status (2026-10-06): complete and merged, #1530-#1534, bottom-up; its handoff doc (doc-4) was retired on 2026-10-06 and its one forward item, the `incident.scribe` entry-point name, is recorded on TASK-110. It also finishes TASK-136: the replacement for `IncidentChannelPort` takes a role name, and the `_CHANNEL_PORT` / `mock_port` test names are renamed with it (listed in the TASK-135 notes).

### Wave 5: behaviour-changing tracks

| Track | Order | Form |
| --- | --- | --- |
| Webhooks | Stack F: TASK-37.1 -> TASK-37.2 -> TASK-37.3 (behaviour-preserving, held by the TASK-36.2 pinning tests); then TASK-37.4 (cutover), TASK-47 (HMAC), TASK-48 and TASK-49 in parallel, TASK-37.5 | stack F, then single PRs |
| Approvals | TASK-60 -> TASK-125 -> TASK-61 -> TASK-30; then TASK-62 and TASK-63; TASK-124.1 (access) after TASK-61 and TASK-30; it also decides whether the route-local Protocol twins kept by TASK-136.3 are collapsed | single PRs |
| Identity | TASK-83.3 and TASK-83.12 early; TASK-83.2 -> TASK-83.4 -> TASK-83.5 and TASK-83.6 -> TASK-83.7 -> TASK-83.8; TASK-83.9 -> TASK-83.10 after TASK-38 | single PRs |
| Incident status updates (prioritised 2026-10-06) | After TASK-110.2: TASK-140.1 (decision records) -> TASK-140.2 (Slack action and view registrar), TASK-140.3 (conversation to incident id in core) and TASK-140.4 (status-update records and table) in parallel -> TASK-140.5 (draft command, after 140.3 and 140.4, with the 140.4 table applied in Terraform first) -> TASK-140.6 (approval modal and copy-ready publish, after 140.2) -> TASK-140.7 (retire legacy /sre incident updates). TASK-139 (incident and scribe READMEs) is a docs PR after TASK-110.2, parallel with TASK-140.1. TASK-140.5 uses today's Summarizer, so it is sequenced with TASK-25.10 and TASK-134 rather than run beside them | single PRs, not a stack: a new feature changes behaviour, and 140.2 to 140.4 do not build on each other |
| Legacy rebuild by surface | TASK-38 as TASK-38.1 (core record and store, after TASK-124.5, TASK-27.2, TASK-108 and TASK-109) -> TASK-38.2 (core resource interfaces) -> TASK-38.3 -> TASK-38.4 -> TASK-38.5 (lifecycle; TASK-38.5 frees packages/aws_platform for TASK-88) with TASK-38.6 (retrospective, after TASK-138) in parallel after TASK-38.2 -> TASK-38.7 (record cutover) -> TASK-38.8 (delete modules/incident); then TASK-39, TASK-88, TASK-40, TASK-41, each held by the TASK-36.1 and TASK-36.3 pinning tests for its surface; TASK-53, TASK-55, TASK-56 and TASK-65 ride with the surfaces that own them. The incident expansion drafts under TASK-97 (metrics replacement, products as records, the external case recorder and DFIR-IRIS adapter, inbound case events, second-suite adapters, the updates command, retro meeting management and retro action items as records) start only after this sequence is finished | single PRs per surface; each cutover is a standalone merge |

## Standalone merges

These change runtime or deployment behaviour. Merge and deploy each one separately:
- TASK-110.2: plugin load failures abort boot (TASK-110.1 before it is behaviour-preserving).
- TASK-111: configuration moves to files.
- TASK-33: async Bolt.
- TASK-100: lease read-failure policy.
- TASK-37.4: webhooks cutover.
- TASK-47: HMAC enforcement.
- TASK-61: approvals refactor.
- TASK-30: event bus deletion.
- TASK-140.6: the first public status updates (approval and publish).
- TASK-140.7: legacy /sre incident updates cutover.
- Each legacy surface cutover.
