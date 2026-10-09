---
id: doc-9
title: 'Incident rebuild by purpose and on-call capability: delivery plan'
type: guide
created_date: '2026-10-09 16:50'
---

# Incident rebuild by purpose and on-call capability: delivery plan

Planning record, 2026-10-09. Not a decision record: the decisions are in `decisions/incident-management.md`, `decisions/oncall.md`, `decisions/product-scope.md` and `decisions/feature-packages.md` (all amended or created the same day on the branch that carries this document). This document holds the delivery chain, what it supersedes, the assumptions each slice relies on and the open questions. When every task below is Done, this document is retired.

## Why this exists

- `packages/incident/scribe/` grew to three use cases (`draft`, `summarize`, `status-update`) behind one 921-line Slack entry point and one 838-line views module. The size is a symptom: the subdomain was formed around a mechanism (the model writes text) rather than a purpose in the incident process, and rule 2 of feature-packages.md ("a unit you would enable, own or delete on its own") let every command pass.
- The three use cases serve three audiences at three moments: a responder catching up (active response), the people who use the affected service (external audience), the postmortem owner and reviewers (learning). They share a capability and nothing else.
- TASK-38 and its eight slices were written for `lifecycle | retrospective | scribe`, so continuing them would rebuild the legacy module into a shape already known to be wrong. Starting fresh costs the task text and nothing else: no slice had started.
- On-call was split between a planned `rotations` capability (TASK-123) and the `oncall_sync` feature, with the incident declare flow carrying Opsgenie vocabulary. Opsgenie serves a small subset of teams, ends on 2027-04-05 and has no chosen replacement.
- The bot's stated purpose ("designed for site reliability engineering") did not match half of its surfaces, which kept raising the question of carving talent, ATIP and access out into their own app.

## Decisions taken on 2026-10-09 (recorded in the ADRs)

| Decision | Where |
| --- | --- |
| Subdomains are the stages and audiences of the incident process, named in the domain's words; never named for a mechanism; one command joins the subdomain whose users need it | feature-packages.md rule 2; incident-management.md "The feature umbrella" |
| `response`, `comms`, `postmortem` over `core/` and `common/`; `scribe` dissolves (summarize to response, draft to postmortem, status updates to comms); the umbrella moves to `features/incident/` before the rebuild, not after | incident-management.md |
| The record gains severity (levels 0 to 3) and the five roles (IC, OL, CL, PL, PO); the four timing fields stay so time to detect and time to recover derive | incident-management.md "The incident record" |
| Communications are defined by audience: the public update first; internal staff and senior management as later profiles, never new subdomains | incident-management.md "Communications" |
| Detection reaches the bot through alert channels fed by product infrastructure and the SIEM via the webhooks pipeline; the bot owns the call-incident button only | incident-management.md "The feature umbrella" |
| On-call is a capability with two schedule sources (Opsgenie, self-managed rotations), selected by the reference's system; `oncall_sync` is a feature over it; incident consumes it at declare; paging is the notifications capability's concern | oncall.md |
| One app, four product areas (incident response, cloud operations, platform access, workplace utilities), written carve-out criteria | product-scope.md; root README |
| Views hold no language-keyed literal tables | i18n.md Checks |
| Expansions are optional and recorded as drafts with the role they depend on | incident-management.md "Expansions, all optional"; DRAFT-12 to DRAFT-15 |

## Target shape

```text
app/capabilities/text_generation/        # TASK-25.10, TASK-134 (unchanged tasks)
app/capabilities/oncall/                 # TASK-146.1: api.py, service, domain, adapters/{opsgenie,rotations}.py, entrypoints/slack.py
app/features/oncall_sync/                # TASK-146.2: usergroup projection over the capability

app/features/incident/                   # moved as it stands in TASK-145.1, the first slice
├── common/        settings.py, vocabulary.py (IncidentStatus, Severity, roles, StatusUpdateStage, shared action ids)
├── core/          api.py, domain.py, store.py, adapters/{slack,google_docs,google_drive,google_meet,status_updates,in_memory}.py
├── response/      declare, status, severity, roles, show/update, archive, recreate, timeline, nudge, alert buttons, summary.py
├── comms/         service, approval, history, prompt, comms_profile, domain, ports, providers, adapters/copy_ready.py
└── postmortem/    meeting scheduling over the calendar capability, report.py (draft), prompt.py
```

Each subdomain keeps two flat entry-point modules, `entrypoints/slack.py` and `entrypoints/slack_views.py`; a views split waits for TASK-118. Tests mirror the tree under `tests/unit/features/incident/{core,response,comms,postmortem}/`.

## The chain

Two coordinators, created 2026-10-09, each child a single PR under the size gate, merged bottom-up. A gh stack is acceptable inside a group.

### TASK-145: incident feature by purpose (supersedes TASK-38, TASK-38.1 to TASK-38.8, TASK-124.5)

| Group | Task | Content | Depends on |
| --- | --- | --- | --- |
| A, move and clean in place | TASK-145.1 | The umbrella moves to `app/features/incident/` as it stands, with the first-mover wiring (hatch, import-linter root and contracts, ruff first-party, renamed ignore entries, tests under `tests/*/features/incident/`) | TASK-144 merged |
| A | TASK-145.2 | Status-update wording and prompt text leave the views module; i18n literal-table check | 145.1 |
| A | TASK-145.3 | Every status-update handler calls one service method; results carry what failure renders | 145.2 |
| A | TASK-145.4 | `comms` carved out of scribe as plugin `incident.comms`; ids `incident.comms.status_update.*`; the scribe-local TextGenerator moves whole | 145.3 |
| B, core | TASK-145.5 | Record with severity and five roles, interim DynamoDB `IncidentStore`, two-part command check, `common/` | 145.1 |
| B | TASK-145.6 | `IncidentConversation`, `IncidentReport` (absorbs `documents/`, `drive/`, scribe's section writer), `ProductCatalog`; transcript reader takes the reference | 145.5 |
| C, response | TASK-145.7 | Declare and the alert buttons; `meet/` folds into core | 145.6, TASK-36.1 |
| C | TASK-145.8 | Status, severity, show and update, five roles, archive, recreate | 145.7 |
| C | TASK-145.9 | Timeline capture, nudge job; `summarize` moves in; incident leaves `aws_platform` | 145.8, TASK-36.3 |
| D, postmortem | TASK-145.10 | Meeting scheduling over the calendar capability | 145.6, TASK-138, TASK-36.1 |
| D | TASK-145.11 | `draft` moves in; scribe deleted; layers contract lists response, comms and postmortem above core above common | 145.10, 145.9 |
| E, cutover | TASK-145.12 | List sheet becomes a write-only projection; references backfilled | 145.9 |
| E | TASK-145.13 | Delete `app/modules/incident`, legacy registration and catalogues; inventory closed | 145.11, 145.12, TASK-118 |

Group A can start as soon as the TASK-144 stack is merged; TASK-145.1 goes first because the open TASK-144 PRs edit scribe files and every later slice then builds in the final home. Group B needs only TASK-145.1. Groups C and D wait for pinning (TASK-36.1, TASK-36.3) and D for the calendar capability (TASK-138). The package-shape check (TASK-114), per-environment enablement (TASK-112) and TOML settings (TASK-111) are not in the chain and apply to `features/incident` when they land. TASK-25.10 and TASK-134 are not in the chain either: when they land, they replace the `comms` TextGenerator and the direct Summarizer calls in `response/summary.py` and `postmortem/report.py`, wherever those files are at the time.

### TASK-146: on-call capability (supersedes TASK-123, TASK-124.2)

| Task | Content | Depends on |
| --- | --- | --- |
| TASK-146.1 | `capabilities/oncall/`: `OnCallLookup`, schedule types, Opsgenie and self-managed sources, fake, the rotation commands as entry points; `user_rotations` deleted | TASK-25.6, TASK-114 |
| TASK-146.2 | `oncall_sync` consumes the capability, loses its Opsgenie adapter and `ports.py`, moves to `features/` | 146.1 |
| TASK-146.3 | Incident declare invites through the capability; no Opsgenie vocabulary in the umbrella | 146.1, TASK-145.7 |

### Optional enhancements (drafts, not scheduled)

| Draft | Content | Waits for |
| --- | --- | --- |
| DRAFT-12 | Self-managed schedules: shifts, overrides, escalation, so Opsgenie can be retired | the organisation's choice of a replacement product, or none |
| DRAFT-13 | Internal and senior-management updates as comms audience profiles | the communications and policy roles |
| DRAFT-14 | Privacy flag on the record; policy lead invited | the policy role |
| DRAFT-15 | Participant roster, in-incident tasks, postmortem feedback (reference only) | a request from the process owners |
| DRAFT-9, DRAFT-10 | Action items as records with reminders; status-page adapter | the postmortem owners; the communications role |

## Assumptions in force

Stated on the coordinators; change them there before the slice that depends on them starts.

- The umbrella moves to `app/features/incident/` in the first slice, as it stands and with no runtime change; the shape check, enablement and TOML settings arrive with TASK-114, TASK-112 and TASK-111 on their own.
- The incident record store is an interim adapter over the existing DynamoDB table behind `IncidentStore` and a fake, as the status-update store already is; TASK-108 and TASK-109 swap its inside later.
- The comms carve-out moves the scribe-local `TextGenerator`, its OpenAI binding and the availability predicate whole; draft and summarize keep calling the Summarizer directly until TASK-25.10, so nothing is duplicated.
- Each legacy surface is pinned before the slice that rebuilds it; names, fields, replies and i18n keys do not change during the rebuild, apart from three added role pickers.
- Alert buttons register into the webhooks capability's extension point when it exists, otherwise through the Slack registrar with a later move.
- Severity levels are 0 to 3, confirmed with the incident process owners before TASK-145.4 merges.
- Renaming a plugin renames its action ids; modals open across that deploy are accepted as broken.
- The on-call capability works with the self-managed source alone; the Opsgenie adapter is transitional.

## What was superseded or touched

| Item | Change |
| --- | --- |
| TASK-38, TASK-38.1 to TASK-38.8 | Archived (`backlog/archive/tasks/`) with a pointer to the TASK-145 slice that replaces each; dependents (TASK-40, TASK-41, TASK-88, TASK-83.9, TASK-83.10, DRAFT-1, 2, 3, 6, 7, 8, 9) repointed to TASK-145 or its slice; descriptions of open tasks name the new ids, dated comments and notes keep the old ones as history |
| TASK-124.5, TASK-123, TASK-124.2 | Archived with pointers to TASK-145.1, TASK-146.1, TASK-146.2 |
| TASK-124 | Children list and dependencies updated: oncall_sync and the incident umbrella move through TASK-146.2 and TASK-145.1 |
| TASK-140.11, TASK-140.12 | Still deferred; their text says they belong to `comms` |
| TASK-112 | Acceptance criterion added: enablement keys grouped by product area |
| TASK-144 | Unchanged; main is at f5aa2ca5 with TASK-144.1 to 144.3 merged, and TASK-144.4 and 144.5 merge from the stack-i branches before group A starts |
| decisions/incident-management.md | Rewritten in place: vocabulary, record fields, the three subdomains, communications by audience, postmortem, detection and on-call pointers, optional expansions, rejects, checks, migration |
| decisions/feature-packages.md | Rule 2 is the purpose test; migration tickets; Changes |
| decisions/oncall.md, decisions/product-scope.md | New |
| decisions/plugin-architecture.md, transport-slack.md, interaction-toolkits.md, i18n.md, workplace-systems.md, migration.md, README.md | Cross-references and one Check updated |
| README.md (root) | First paragraph describes the operations platform and its areas |
| doc-2 | Superseded lines noted |
| doc-6 | Part 1 noted as superseded |

## Open questions (human)

1. Severity scale: levels 0 to 3 as recorded, or 1 to 3? Confirm with the incident process owners before TASK-145.5 merges.
2. "Postmortem" is the code and record word; user-facing labels still say "retro". Rename the labels in the catalogues with TASK-145.10, or leave them?
3. Pinning (TASK-36.1, TASK-36.3) is kept as a gate before groups C and D. Hold the gate, or allow an incident-only pinning slice?
4. Interim DynamoDB `IncidentStore` adapter (recorded assumption) versus waiting for TASK-108 and TASK-109: confirm.
5. The alert buttons' registration path if the webhooks capability's extension point (TASK-37) is not built when TASK-145.7 starts: registrar now and move later (recorded assumption), or wait?
6. Should DRAFT-7 (internal updates as timeline records) be folded into DRAFT-13 (internal audience profile) or kept as a separate idea?
