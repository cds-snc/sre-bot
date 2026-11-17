---
id: TASK-145.8.5
title: 'Cut over roles and archive (coordinator: TASK-145.8.5.1 to 145.8.5.3)'
status: In Progress
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-16T19:54:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.7.2
  - TASK-145.8.1
  - TASK-145.8.2
references:
  - decisions/incident-management.md
  - decisions/migration.md
  - decisions/transport-slack.md
parent_task_id: TASK-145.8
priority: medium
type: feature
ordinal: 510000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L7a, split 2026-11-16 (human, OQ1-OQ8 approved; assessment and rulings in the comments): TASK-145.8.5.1 roles (record, five pickers, Drive roles read bridge), TASK-145.8.5.2 value-scoped legacy callback aliases (Slack transport, side PR from main), TASK-145.8.5.3 archive and /sre incident close through one response service (one Sentinel event, minimal payload). Reassigned: legacy_sre_web_client_seam and baseline line 20 to TASK-145.13 (still needed by the show, product list and schedule retro pins); update_incident_document_status to TASK-145.8.3 (its last caller); the ignore button to TASK-145.9.2; the roles backfill from Drive to TASK-145.7.12. ACs are checked as the subtasks verify them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Roles cut over with the Drive roles read bridge (TASK-145.8.5.1)
- [ ] #2 Value-scoped legacy attachment aliases in the Slack transport (TASK-145.8.5.2)
- [ ] #3 Archive and /sre incident close cut over; close_incident and incident_status.py deleted; one Sentinel event with a minimal payload (TASK-145.8.5.3)
- [x] #4 Reassignments recorded on their tasks: the seam and baseline line 20 (TASK-145.13), update_incident_document_status (TASK-145.8.3), ignore (TASK-145.9.2), the Drive roles backfill (TASK-145.7.12)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-16 (human): coordinator plan. Program-scope plan and rulings: comments of 2026-11-16 on this task (OQ1-OQ8). Order: 145.8.5.1 stacked above L6b (#1859) on stack-l/task-145.8.5.1-roles; 145.8.5.2 side PR from main (any review window, before .3); 145.8.5.3 stacked above .1; 145.7.12 side PR after .1 merges and before the TASK-145.7.8 apply. L6a (145.8.3) stacks above .3. Nothing here merges before L6b, which waits on the upgrade-job dry run.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-16: AC #1 checked (TASK-145.8.5.1 implemented, gates green, In Progress, PR to open above L6b); AC #4 checked (reassignments recorded on TASK-145.13, 145.8.3, 145.9.2, 145.7.12 and 145.10, comment on TASK-171).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): the migration.md amendment (step 4 named changes of kinds a-d, rule 1 planned legacy edits, rule 2 modules may import features/capabilities one-way, per-command 'never both', Consequences) rides with L6b; this task applies kind (a) instead of adding the bug-fix rule.

---

created: 2026-11-16T19:33:00Z

---

2026-11-16 program-scope assessment of OQ1-OQ8 (ADRs at stack-l/task-145.8.4-status 5dcf9c73, doc-11, doc-15, prior and upcoming tasks, web). Supersedes the first OQ list of the same day.

OQ1 Split. ADR: none needed; CLAUDE.md size gate, doc-15 size guide (~10 files / 400 LOC). Prior: TASK-146.1 split into 146.1.1/146.1.2 (2026-11-16); feedback "combine dark slices": dark no-consumer slices together, production-changing slices separate. Upcoming: none. Recommendation (revised): three slices. 145.8.5.1 roles (+ roles read bridge, OQ7); 145.8.5.2 value-scoped legacy callback aliases in the Slack transport (side PR from main, dark, OQ3); 145.8.5.3 archive and close. .1 and .3 stack above L6b; .2 merges before .3.

OQ2 update_incident_document_status. ADR: none. Prior: TASK-145.8.4 plan section 6 (approved): deleted with its last caller, "L6a/L7a, whichever lands last"; its docstring (incident_document.py:70) names TASK-145.8.5. Upcoming: L6a (145.8.3) removes the last caller information_update.py:313. Recommendation: the delete moves to 145.8.3 (AC added there; docstring owner updated in .3); L6a stacks above L7a. No gap.

OQ3 Archive button. ADR: transport-slack.md:39 (ids registered once; a posted legacy id is an alias of its rebuilt listener until the contract task, TASK-145.13); migration.md step 4 and "never both" per interaction (2026-11-16). Prior: TASK-36.1.2 OQ1/OQ3 (approved 2026-11-06): archive_channel's archive and ignore branches belong to TASK-145.8, schedule_retro to TASK-145.10 ("rendered by response, handled by postmortem"), which "keeps a registered legacy alias until TASK-145.13". GAP/CONFLICT: one posted callback id with buttons owned by two subdomains cannot be one alias of one listener; rebuilt listeners attach before legacy ones (server/lifespan.py:274 vs :280), so a plain alias would also swallow schedule_retro; response cannot import postmortem or legacy (contracts g, i). Research: Slack replaces attachment callback_id with Block Kit block_id/action_id per element (https://docs.slack.dev/messaging/migrating-outmoded-message-compositions-to-blocks/); Bolt runs the first listener whose matchers pass and skips the rest (slack_bolt app.py:584-605; attachment_action(callback_id, matchers) :1137), the routing seam a strangler fig needs (https://martinfowler.com/bliki/StranglerFigApplication.html, transitional architecture). Proposed ADR fix (transport-slack.md): a legacy attachment alias may be scoped to button values (legacy_callback_ids entries with values, e.g. archive_channel: archive); the provider attaches it with a value matcher, so an unscoped value falls through to the legacy listener while one remains and is acked and logged after; each owner registers its own values; new messages carry one Block Kit action id per button, owned by its subdomain; TASK-145.13 removes the aliases. This replaces the first proposal (legacy listener delegating to response with a scope opener threaded through server/lifespan.py). Scope changes: new 145.8.5.2 (registrar contract, provider, server registrar, tests); 145.8.5.3 registers incident.response.archive with alias archive_channel value archive; ignore moves to TASK-145.9.2 with the notice it rewrites (the nudge's delay; 36.1.2 ruling amended); 145.10 registers schedule_retro the same way; 145.9.2 posts the Block Kit notice; 145.13 removes the aliases. /sre incident close rebuilt on the same service (pinned first; close_incident deleted).

OQ4 Seam. ADR: testing.md seam rule (an internal seam is deleted by its owning task, baseline header). Prior: TASK-145.8 owns legacy_sre_web_client_seam (fixture docstring, baseline line 20). Upcoming: legacy /sre subcommands still pinned through it: incident show (L6a 145.8.3), incident product list (retired by 145.13), incident schedule retro (145.10, Stack M, which gates 145.13). Recommendation: owner becomes TASK-145.13; AC #1 and the title reworded; fixture docstring and baseline comment updated in .1. No gap.

OQ5 Core join and purpose. ADR: incident-management.md 2026-11-05 "writability is conversations.info, never a join" (the check); nothing on an explicit join step or reading the purpose. Prior: IncidentConversation async per reference (145.6.3); set_purpose and archive exist. Upcoming: recreate (145.8.6) may need join for a channel the bot left. Research: conversations.join on a joined channel returns ok with warning already_in_channel (https://docs.slack.dev/reference/methods/conversations.join/); public channels only. Proposed ADR line: joining is an explicit step of a write that needs membership (archive), idempotent; never part of the writability check; a private channel the bot left is refused, not joined. purpose(conversation) added for the roles line. Small gap, fixed by the ADR line.

OQ6 Roles modal. ADR: incident-management.md 2026-10-09 (five roles on the record); migration.md step 4 (an addition needs a plan ruling); parent 145.8 description (approved 2026-11-09): "the roles command offers all five; only IC and OL are required". Correction: legacy IC and OL are required input blocks (incident_roles.py), so IC and OL stay required and the three new pickers are optional (my first draft said all optional). doc-15: engagement leads are per engagement (on-call or manual, D33), not incident roles; no conflict (domain check: Incident.roles stays incident-level; an engagement lead is a field of the engagement record, E-epics). Purpose line keeps IC and OL only (pinned). Pin edits citing rulings: five placeholders (addition by the parent ruling); not-an-incident reply (kind b); roles show stub retired (kind d). No gap.

OQ7 Existing roles. ADR: incident-management.md Migration rule 1 (expand, backfill, switch reads, contract), rule 2 (one pure upgrade function shared by the read bridge and the backfill), rule 7 (optional values), "Tolerated: roles in the report's Drive properties"; 2026-11-04 line assumes the item's incident_commander/operations_lead carry the roles. CONFLICT: no legacy writer sets those attributes (only app/models/incidents.py:25-26 defaults); every role lives in Drive appProperties ic_id/ol_id. Switching reads to the record without a backfill breaks rule 1 and shows empty roles for every existing incident (show in L6a, the roles modal, postmortem facts in TASK-147). Research: Stripe online migrations backfill before switching reads (https://stripe.com/blog/online-migrations); lazy migration reads the old store on a miss and pairs with a background backfill so the bridge can be deleted (https://oneuptime.com/blog/post/2026-03-31-dapr-migrate-state-stores/view). Proposed ADR fix (Migration): an upgrade input may come from a legacy side store; for incidents, the report's Drive properties ic_id/ol_id are read through one legacy-only core adapter and mapped by the shared upgrade function as optional values (rule 7); a read bridge in core supplies them to readers of an item without record roles until the backfill reports nothing pending; both deleted by TASK-145.13; the 2026-11-04 line corrected. Scope changes: 145.8.5.1 adds the core roles read bridge (record roles, else the report's Drive properties; never writes Drive); 145.8.3 (L6a show) reads roles through it; new subtask (TASK-145.7.12, row before 18.L8) adds the Drive roles input to the job's per-item plan before the apply; 145.13 deletes both. Alternative: accept empty roles (conflicts with rule 1; not recommended).

OQ8 Sentinel event. ADR: observability.md:20 ("Sentinel receives only audit events, through the audit sink"); configuration.md 2026-10-28 (shape tolerated until TASK-171). Prior: TASK-171 (High, row Z2): rebuild on the Logs Ingestion API, not delete (human 2026-10-28), blocked on the platform owner; TASK-122 (audit capability, To Do, no doc-11 row). CONFLICT: the legacy event sends the raw Slack body (verification token, response_url) outside the audit sink. Research: OWASP Logging Cheat Sheet excludes access tokens and session identifiers (https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html); AWS prescriptive guidance the same (https://docs.aws.amazon.com/prescriptive-guidance/latest/logging-monitoring-for-application-owners/logging-best-practices.html). Recommendation: a response adapter (adapters/sentinel.py, TODO(TASK-122)) sends incident_channel_archived once, after a successful archive, with a minimal payload {incident_id, conversation_id, user_id, at} instead of the raw body (named change, kind a: recorded here as a legacy defect); the human confirms no Sentinel query reads the old message fields; TASK-171 gets a comment listing this event. Proposed ADR line (observability.md): rebuilt surfaces send named events with minimal fields, never request bodies, until the audit capability (TASK-122) owns the sink. Record failure stops the archive (commit point, L6b ADR line) and the refusal is decided by the record (parent AC #1, incident-management.md Checks): ADR-backed, no gap.

---

created: 2026-11-16T19:33:00Z

---

APPROVED 2026-11-16 (human): OQ1-OQ8 as recommended in the program-scope assessment above. TASK-176 unchanged. Split into TASK-145.8.5.1 (roles, with the roles read bridge), TASK-145.8.5.2 (value-scoped legacy callback aliases, side PR from main) and TASK-145.8.5.3 (archive and /sre incident close); new TASK-145.7.12 (job roles input) before 18.L8. Stack base: .1 and .3 stack above L6b (#1859); .2 merges before .3.

---
<!-- COMMENTS:END -->
