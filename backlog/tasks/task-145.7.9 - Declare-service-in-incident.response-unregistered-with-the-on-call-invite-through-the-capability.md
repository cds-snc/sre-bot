---
id: TASK-145.7.9
title: >-
  Declare service in incident.response, unregistered, with the on-call invite
  through the capability
status: Done
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-20T22:06:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.2
  - TASK-145.7.5
  - TASK-145.7.6
  - TASK-145.12.1
  - TASK-145.7.7
  - TASK-146.1
  - TASK-145.8.7
  - TASK-145.8.8
references:
  - decisions/incident-management.md
  - decisions/oncall.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 513000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L9a (approved program in TASK-145.7's plan, section 2; outline in the parent plan). response/service/declare.py orchestrates the declare flow over the core Protocols (TASK-145.7 plan section 6), including TASK-146.3: invites through capabilities.oncall.api with a ScheduleSource port whose interim adapter reads the placement folder's genie_schedule through the Drive gateway (read only, tolerated with owner TASK-165.1), and the Notify management invite triggered by [incident_response] notify_management_placement_id (tolerated, owner TASK-165.1). Unregistered.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Declare writes the record first (IncidentStore.create, the id derived from the declare's idempotency key), then creates the conversation through the I1-I5 loop and attaches it (attach_conversation), then the resources; full success writes every reference; a failing conversation leaves an open incident with no surface, reported and retriable, never rolled back; each later failure leaves its reference empty and continues; the declarer, on-call people, the security group (security incident), the policy group (policy help asked) and the Notify management group (Notify placement) are invited, each group only when its id is configured, with no environment-name check (tested; checks parent ACs #2, #14 and TASK-146.3's ACs)
- [x] #2 decisions/incident-management.md lists the interim schedule adapter and the Notify placement key as tolerated with owner TASK-165.1; decisions/oncall.md Checks names the interim adapter as the one tolerated Opsgenie name (owner TASK-165.1); decisions/people-and-accounts.md tolerates chat-adapter email-to-account resolution until TASK-83.6; no umbrella module imports integrations.opsgenie
- [x] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #4 The declared record's initial status is the setting [incident_response] initial_status (typed IncidentStatus, an open status only, default Open), so changing it is a configuration change, never a code change; a non-open value fails settings load; decisions/incident-management.md records it; the list row shows that value. The declare upserts the list row (IncidentListProjection.append_row) even when the conversation or report step failed, and a retried step re-upserts (TASK-145.12.1 rulings R3, R6, 2026-11-16)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-18 (human): OQ1-OQ8 as recommended in the program-scope assessment comment, with OQ4 corrected: the initial status is a setting with a default, not a code constant. Revised the same day after that assessment. Planned against main 203aeea1 (with #1866, #1868 merged). Stack L L9a, doc-11 row 18.L9a.

## 0. Rules carried
- Record is the commit point; declare writes the record first (IncidentStore.create, put-if-not-exists, replay returns the stored record), then the conversation and attach_conversation, then resources (R4-R6, incident-management.md Bindings). Never rolled back.
- API first: the service needs no chat surface; a conversation is created only when an IncidentConversation is configured (feedback: bot runs standalone).
- Async ports only; the service never calls to_thread (comment #2). Optimistic-concurrency conflicts on set_reference recompute from the re-read record, they are not retries (outbound-clients.md 2026-11-17).
- Inert: nothing registers the service, the router or a Slack handler; 145.7.10 cuts over Slack.

## 1. Stack placement (program scope)
Recommendation: **side PR from an up-to-date main** (mode P), branch `task-145.7.9-declare-service`, not `stack-l/...` above L6a.
- L9a uses nothing L6a adds (show/update modal cutover); every port it needs is on main (145.7.5/.6/.7, 145.8.7/.8, 145.12.1, 146.1.1).
- Stacking above L6a would hold an inert PR behind L6a's restack, A5 describe, quiet-window merge and soak; L9b already waits on the L8 apply, which waits on L6a, so ordering is kept without stacking.
- Overlap with L6a (dce00bcf): decisions/incident-management.md Changes (keep both), possibly tests/factories/incident.py; no code hunk overlap. doc-16 row L9a mode S -> P; L9b stays S above whichever merges last.

## 2. Size gate
~570 production LOC over ~9 files (HTTP route moved to TASK-165.2, OQ3): trips. All of it is dark (no consumer), so per the dark-slice rule: **one PR under a size exception (rule 1 only, approved 2026-11-18)**; the production-changing slice is 145.7.10.

## 3. Changes
1. `response/service/conversation.py` (~130): `ensure_conversation(incident, *, conversations, claims, names)` implements I1-I5: I1 record names a conversation -> return it; I2 claim `incident:conversation_name:<tenant>:<name>` (IdempotencyStore), skip a name held by another incident; I3 after any non-success create (NAME_TAKEN, transient, exception, timeout) `find_own(name)` first, bind own/unbound-with-our-claim; I4 retry the same name; next suffix only when proven another incident's or not the bot's; I5 unknown outcome with nothing found -> error result, no move-on. NAME_TAKEN logged at info. Returns OperationResult[ConversationReference]; the caller attaches.
2. `response/service/declare.py` (~280): `DeclareRequest` (frozen: idempotency_key, title, security_incident, severity | None, placement | None, policy_help, declarer, source_alert | None, opened_on) and `declare(request, ports, texts) -> OperationResult[DeclareOutcome]`. Id = uuid5(namespace, idempotency_key) (namespace constant in response). Steps, each retriable and skipped when its reference is already set (a rerun with the same key is the retry):
   a. one run per incident: claim `incident:declare:<id>`; held -> DECLARE_IN_PROGRESS; released at the end so a rerun retries failed steps;
   b. IncidentStore.create with status = settings.initial_status (OQ4);
   c. conversation (1) then attach_conversation (primary, bound_by declarer); failure -> outcome reports it, incident stays open with no surface;
   d. topic/purpose, report (create_from_template in the placement) + set_reference + bookmark, video call + set_reference + bookmark, canvas, severity warning, source-alert bookmark and post;
   e. invites in one call: declarer; on-call (ScheduleReference from the placement, OnCallLookup.on_call_now; error or no reference -> nobody, said in the announcement); security group when security_incident; policy group when policy_help (#1853 carried); Notify management group when placement id == notify_management_placement_id; each group only when its id is configured, no environment check (only production.toml sets them; OQ8); declarer and duplicates removed;
   f. announcement post and next-steps post, each once (claim `incident:declare_post:<id>:<kind>`, completed on success);
   g. IncidentListProjection.append_row always, even after c/d failures; a rerun re-upserts (145.12.1 R3, R6).
   DeclareOutcome lists each step's result; texts come in from the caller (archive-service pattern), so the service has no locale.
3. `core/api.py`: `PlacementScheduleLookup.schedule_for(placement) -> OperationResult[ScheduleReference | None]` (name avoids the capability's own ScheduleSource, capabilities/oncall/interfaces.py:9); `IncidentConversation.account_ids_for(emails) -> OperationResult[tuple[str, ...]]` (on-call people carry an email; Slack invites need account ids; tolerated until TASK-83.6, OQ7).
4. `core/adapters/google_drive_schedule.py` (~50): interim adapter, folder appProperties `genie_schedule` through the Drive gateway, read only -> ScheduleReference(OPSGENIE, value) with OPSGENIE imported from capabilities.oncall.api. Tolerated, owner TASK-165.1.
5. `core/adapters/slack.py` account_ids_for (users.lookupByEmail, unknown email skipped and counted); `core/adapters/in_memory.py` fakes for both.
6. `response/settings.py`: `notify_management_placement_id` as an env_only field (default "", like handbook_id): a Drive folder id is a non-public value (configuration.md:45, :93), so it is set from the environment as INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID and only named in a base.toml comment, never in a configuration file; no terraform change here (L9a stays dark); the SSM parameter (terraform/ssm.tf) and its value ride with TASK-145.7.10, the cutover that makes the invite run (correction 2026-11-18, human); tolerated, owner 165.1 and `initial_status: IncidentStatus = IncidentStatus.OPEN` (described field; a validator refuses a status that is not open, so a bad value fails settings load at boot; base.toml carries `initial_status = "Open"` with a comment; changing it is one line in base.toml or an environment file, no code change). Test: default Open, an In Progress value loads, Closed is refused.
7. `response/providers.py`: zero-arg getters for the declare ports and an IdempotencyStore (build_conditional_write_store, FAIL_CLOSED, sre_bot_idempotency, already in production for leases).
8. ADRs: incident-management.md tolerated lines (interim schedule adapter, Notify placement key, both owner 165.1), initial status: a declare setting `[incident_response] initial_status`, one of the open statuses, default Open, invite rules (OQ8), declare-run claim, Changes line; oncall.md Checks exception for the interim adapter (owner 165.1) and Changes; people-and-accounts.md tolerated line for chat-adapter email resolution (until TASK-83.6) and Changes. READMEs (response, core).
9. DeclareRequest stays platform-neutral (declarer as the caller's platform account today, idempotency key as input) so TASK-165.2's POST /api/v1/incidents is a thin route over it.

## 4. Tests (TDD, fakes only)
- test_incident_response_conversation_ensure.py: one test per I1-I5, NAME_TAKEN at info.
- test_incident_response_declare_run.py: record before binding; full success writes every reference; conversation failure -> open incident, no surface, list row still upserted; each later failure leaves its reference empty and continues; rerun with the same key fills only missing references, posts once; on-call invite and on-call error -> nobody + notice; security/policy production-only; Notify trigger; declarer deduped; in-progress claim -> DECLARE_IN_PROGRESS.
- test_incident_core_schedule_lookup_drive.py; test_incident_core_conversation_account_ids.py.

## 5. Blast radius and revert
None at runtime: nothing registers the service; the new settings key is read by nothing that runs. One git revert.

## 6. Open questions (program-scope assessment in the 2026-11-18 comment; recommendation first)
OQ1 Size: one dark PR with a size exception (~570 / ~9). No gap.
OQ2 Stack: side PR from main, task-145.7.9-declare-service; doc-16 L9a mode S -> P. No gap.
OQ3 HTTP route: conflicts with authorization.md (TASK-131 not built), TASK-165.2 (owns the incident HTTP API base, edge test, people dependency) and the declared_by field (platform user id); ADR gap on Idempotency-Key. Recommended: (a) move AC #4 to TASK-165.2 with a reliability.md Idempotency-Key rule riding there and a dependency on TASK-131; this task keeps the service API first. Reverses R6's placement (human ruling 2026-11-10), not its intent. Alternative (b): route here, unregistered, interim scope, typed declarer.
OQ4 Initial status: APPROVED corrected (human): `[incident_response] initial_status`, typed IncidentStatus, open statuses only, default Open; recorded in incident-management.md.
OQ5 policy_help: declare input, not stored.
OQ6 Opsgenie name: conflict with oncall.md Checks; tolerated exception there and in 146.3 AC #1, owner TASK-165.1.
OQ7 Email to Slack account: gap in people-and-accounts.md tolerated list (already open in main via oncall_sync); tolerated line until TASK-83.6; IncidentConversation.account_ids_for.
OQ8 (new) Group invites follow configuration, not the environment name (cloud-portability.md 2026-11-04 precedent); production unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (TASK-145.7.7 rulings R4-R6, decisions/incident-management.md Bindings): business features are API first; bindings are chat conversations only, zero or more per incident; declare writes the record first, then the conversation and attach_conversation, then resources, each a retriable step whose failure is reported (timeline entry once TASK-145.9) and never rolled back; the incident id is derived from the declare's idempotency key (uuid5 of the Slack request or alert id; the HTTP Idempotency-Key) so a retry reuses it and the orphan-incident residual stays theoretical; the HTTP declare route is folded in here (AC #4). Supersedes the plan's OQ9 'declare unavailable only when no working surface can be bound' and AC #1's 'a failing conversation writes nothing'. Full plan: check the size gate with the route included.

2026-11-16 (TASK-146.1 rulings, human): OnCallLookup.on_call_now is async and returns OperationResult[tuple[OnCallPerson, ...]]; the declare maps an error result to inviting nobody and saying so (oncall.md:20). The reference is ScheduleReference(OPSGENIE, genie_schedule). OnCallPerson carries an email or an Account (rotations: Slack user id). Needs TASK-146.1.1 only.

2026-11-17 (TASK-145.8.6 re-plan, human-approved): recreate is retired, so this task alone owns the one-conversation loop I1-I5 (comment #1 rules), placed at response/service/conversation.py with one test per rule; TASK-165.5 (AC #2) and TASK-165.11 (rebind) reuse it.

2026-11-18: picked up (doc-11 row 18.L9a); TASK-176 asked (unchanged). Planned in full against main 203aeea1; proposed, awaiting approval (OQ1-OQ7 in the plan).

2026-11-18: plan APPROVED (human): OQ1-OQ8 as recommended in the program-scope assessment, OQ4 corrected to a configurable initial status ([incident_response] initial_status, default Open). The HTTP route (old AC #4) moved to TASK-165.2. Side PR from main on task-145.7.9-declare-service.

2026-11-18 (human): notify_management_placement_id is a non-public value (Drive folder id, configuration.md:45, :93): env_only field, named in a base.toml comment, no production.toml value; the SSM parameter and value ride with TASK-145.7.10.

2026-11-18: implementation started on task-145.7.9-declare-service (human-created from main); TASK-176 unchanged per this session's answer at planning start.

2026-11-18 implementation (TDD), on task-145.7.9-declare-service. The branch was created from the L7c head c20ce967, not from main; its tree equals origin/main 98918309 (#1869 squash-merged), so gates ran on main's code; the human rebases it with git rebase --onto origin/main c20ce967 before pushing.

What changed:
- response/service/declare.py: declare(request, ports, policy, texts) -> OperationResult[Declared]. Record first under incident_id_for(idempotency_key) (uuid5, fixed namespace); then conversation (ensure_conversation) and primary binding; on-call (PlacementScheduleLookup, then capabilities.oncall.api on_call_now); report filed in the placement + set_reference + placeholders; video call + set_reference; in the conversation: topic, purpose, canvas, report and video bookmarks and links (only when created in this run), severity warning, source alert (bookmark and post), announcement, invites in one call (declarer, on-call by account or by email through account_ids_for, security/policy/Notify management groups only when configured, no environment-name check), on_call_unavailable notice, next steps; list row last, always. One-time messages claimed per message (incident:declare_message:<id>:<kind>); one run per incident (incident:declare:<id>, released at the end; a second run is DECLARE_IN_PROGRESS, a new registered ErrorCode). DeclarePolicy.from_settings; DeclarePorts with chat None for an API-only instance.
- response/service/conversation.py: ensure_conversation, rules I1-I5; a claimed name is completed at once with the incident id; whose conversation a found one is is proven from its binding (find_incident_for_conversation), since completed claims expire (record_ttl_seconds 3600).
- response/interfaces.py: Claims (async) and DeclareTexts; response/adapters/claims.py: ThreadedClaims over IdempotencyStore (FAIL_CLOSED, each call offloaded).
- core: PlacementScheduleLookup + get_placement_schedule_lookup (api.py), GoogleDrivePlacementScheduleLookup (adapters/legacy_schedule.py, TODO(TASK-165.1)), InMemoryPlacementScheduleLookup; IncidentConversation.account_ids_for (Slack users.lookupByEmail, users_not_found skipped and logged at info; fake seeded by accounts).
- IncidentStatus.is_declarable (Open, In Progress); IncidentStore.create accepts either (was Open only, TASK-145.7.7), per OQ4.
- settings: [incident_response] initial_status (default Open, validated declarable; base.toml), notify_management_placement_id env_only (non-public, base.toml empty); app/.env.example regenerated (make env-example).
- providers: video_call, placement_schedule_lookup, oncall_lookup, claims(store), declare_policy(production=).
- ADRs: incident-management.md (initial status sentence, Declare paragraph, two tolerated lines, Changes); oncall.md (Checks exception, Changes); people-and-accounts.md (tolerated line, Changes). READMEs: umbrella and response.

Deviation to note: AC #4 says "an open status only"; IncidentStatus.is_open counts every status but Closed (Reviewed included), so the rule implemented is "Open or In Progress" (is_declarable), the two before review.

Tests (new): test_incident_response_declare_run.py (20), test_incident_response_conversation_ensure.py (12), test_incident_core_placement_schedule_drive.py (6); extended: conversation protocol parity (account_ids_for), settings load (initial status, Notify placement id), store create (In Progress accepted, Reviewed refused), api surface.

Gates: ruff check . All checks passed, format 1254 files unchanged; make check-import-contracts 14 kept 0 broken; check-settings-key-ownership OK; check-package-shape OK (3 baselined); check-test-seams OK (47/12 baselined); check-fake-coverage OK (4 baselined); mypy Found 40 errors in 13 files (baseline, none in touched files); pytest tests --ignore=tests/smoke 7735 passed.

Left for the human: parent TASK-145.7 ACs #2 and #14 (the declare's resource rules) are verified by these tests but checked by the human with the parent; nothing runs in production until TASK-145.7.10 (Slack cutover, its new Notify SSM AC) and TASK-165.2 (HTTP route).

2026-11-20: closed by the agent: PR #1870 merged 2026-11-18 (7aa3d4ce); all ACs checked.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T20:12:00Z

---

2026-11-10 scope from TASK-145.7.5 (approved by the human): conversation creation follows incident-management.md one-channel-per-incident rules I1-I5 (TASK-145.7.5 plan 1.a4). Candidates from core/conversation_names.incident_conversation_names (legacy format, Slack-safe slug, bare name then -2..-5). I1 a record that names a conversation never creates one. I2 claim each candidate name for the incident through the IdempotencyStore (key incident:conversation_name:<tenant>:<name>); skip a name another incident claimed. I3 after any non-success create (name_taken, transient, unclassified exception or timeout) call IncidentConversation.find_own(name) first; the bots own channel bound to this incident, or unbound while this incident holds the claim, is bound and reused. I4 the same name may always be retried; the next suffix only when the channel is proven another incidents or not the bots. I5 an unknown outcome with nothing found reports the error (one warning, the pinned invoker message) without moving on; recreate retries the same name. CONVERSATION_NAME_TAKEN is an expected outcome logged at info. Plan this in full at pickup, with tests for each rule.

---

created: 2026-11-10T21:00:00Z

---

2026-11-10 (human-approved, TASK-145.7.6 OQ3 R1-R3): declare awaits async ports only (IncidentStore, IncidentReport, VideoCall, IncidentConversation); adapters offload blocking SDK calls, the declare service never calls to_thread. Depends on TASK-145.8.7.

---

created: 2026-11-17T19:10:00Z

---

2026-11-17 (found at the Stack L sync, TASK-145.8.5.3 session): #1853 (fba4ff8b, merged to main, not a Stack L change) added a policy-help answer to the legacy declare: production-only invite of the policy group ([incident] policy_group_id in features/incident/response/settings.py; modules/incident/core.py and incident.py; pinned in tests/modules/incident/test_incident_core.py and test_incident.py, 15 policy tests). The declare rebuild carries it (pins rewired, not dropped) or rules it a named change at planning.

---

created: 2026-11-18T16:25:00Z

---

Program-scope OQ assessment (2026-11-18, human asked). Against decisions/ (current), doc-11, doc-15, doc-16 and the linked tasks. Proposed; nothing outside this task is edited until approval.

OQ1 Size. ADR: none needed (implementation-planning size gate). Prior: TASK-146.1 (2026-11-16, human merged the dark slices a+b). Upcoming: none. No gap. Revised estimate after OQ3: ~570 prod LOC / ~9 files, still over the gate, all dark -> one PR under a size exception (rule 1). Unchanged.

OQ2 Stack placement. ADR: none (doc-16 open decision 1: mode per layer is proposed). Prior: every independent inert layer went side PR from main (L1, L4a-c, L5r, L3c, L7a.2, L7c). Upcoming: L9b (145.7.10) needs L9a and the L8 apply (after L6a). No gap. Side PR from main on task-145.7.9-declare-service; doc-16 row L9a mode S -> P. Unchanged.

OQ3 HTTP route. CONFLICT, three ways, plus one ADR gap.
- authorization.md: features declare permissions (incident.declare); token scopes grant no feature permission. Not built: TASK-131 is To Do with no queue row in doc-11 or doc-15.
- doc-15 row 4 / TASK-165.2: owns the incident HTTP API base (AC #2), caller identity boundaries, authorization rider (AC #1), the TASK-163 edge test under /api/v1/ and the 8 KB WAF body limit (AC #6), and depends on TASK-83.4 (people). A POST /incidents built here would be an /api/v1 incident route ahead of that base, unregistered for months, then reworked.
- people-and-accounts.md / incident-management.md:32: declared_by and the five roles hold a platform user id today (domain.py:255, "Platform user id"; ADR "an email or platform account today; a person id with TASK-83"). A Backstage caller is known only by its email claim (current_user.py). An HTTP declare would write an email into a field every reader renders as a Slack mention (mixed kinds in one untyped str), which the domain-model gate rejects without a typed person reference; TASK-83.4/83.8 bring Person ids.
- Gap: no ADR states HTTP Idempotency-Key semantics (reliability.md:18 covers handler claims only; errors-and-http.md:16 gives RFC 9457 problem details). Practice: IETF draft-ietf-httpapi-idempotency-key-header-07 (400 missing, 409 still processing, 422 reused with a different payload); Stripe saves the first response per key and does not save validation failures or conflicts with a concurrent request; incident.io's create incident takes a required idempotency_key and returns the original on reuse.
Prior: TASK-145.7.7 R6 (2026-11-10, human) folded the route into this task to keep business features API first.
Revised recommendation (reverses R6's placement, keeps its intent): (a) this task ships the declare service API first: platform-neutral DeclareRequest, idempotency key as input, no Slack type in the service, so the route is thin later; AC #4 moves to TASK-165.2 as a new AC: POST /api/v1/incidents over response's declare service, Idempotency-Key per a new reliability.md rule (required on record-creating POSTs, scoped per caller, request fingerprint stored with the claim, 400/409/422 as RFC 9457 problem details, replay returns the stored incident), declared permission incident.declare (TASK-165.2 gains a dependency on TASK-131), declarer as a person reference (TASK-83.4/83.8). The reliability.md rule rides with 165.2 (planning rides with code). Alternative (b): keep the route here, unregistered, with an interim scope, a typed declarer reference and a registration task after TASK-131.

OQ4 Initial status. GAP the task's AC #5 already names (incident-management.md:40 fixes the five values, not the first). Prior: legacy record default Open (models/incidents.py:17, which every legacy item and the upgrade job read), legacy sheet In Progress; TASK-145.12.1 R3/R6; TASK-145.7.10 AC #5 already plans for a status change in the sheet. Practice: tools start in an explicit first state that is not "being worked" (incident.io's triage category; PagerDuty triggered before acknowledged). Recommendation unchanged: Open, recorded in incident-management.md; 145.7.10 AC #5 names "Open instead of In Progress" for the sheet's readers.

OQ5 policy_help. ADR: none (incident-management.md has no policy-help rule; #1853 added it to the legacy declare only, no ADR edit). Prior: #1853 pins (15 tests). Upcoming: TASK-145.9 timeline entries. No conflict. Recommendation unchanged: a declare input that triggers the policy-group invite, not a record field (policy_lead is the role); once 145.9 lands, declare may add a timeline entry, which 145.9.2 can pick up. One ADR sentence with the invite rules (OQ8).

OQ6 Opsgenie name. CONFLICT: oncall.md Checks "grep: no module outside capabilities/oncall/ names Opsgenie"; TASK-146.3 AC #1 the same. The interim adapter must build ScheduleReference(OPSGENIE, genie_schedule) (146.1 ruling 2026-11-16). Prior: TASK-145.7 OQ1 (2026-11-09) ruled the interim adapter tolerated with owner TASK-165.1, without noticing the grep. Upcoming: TASK-165.1 (doc-15 row 3) moves genie_schedule into the catalogue as data, which removes the adapter. Fix: oncall.md Checks gains "except the incident interim schedule adapter, tolerated until TASK-165.1" and a Changes line; 146.3 AC #1 reworded the same way; incident-management.md tolerated list names the adapter. Rejected: a config key holding the system string (hides the coupling instead of time-boxing it).

OQ7 Email to Slack account. GAP: people-and-accounts.md Migration tolerates email-based resolution only in legacy modules, infrastructure/directory and current_user.py; a new lookup in core/adapters/slack.py is not on that list. Prior: OnCallPerson carries an email or an Account (146.1 ruling 2026-11-16), and oncall_sync's Slack adapter already resolves emails with users.lookupByEmail (packages/oncall_sync/adapters/slack.py:93, merged #1864), so the gap already exists in main. Upcoming: TASK-83.6 imports Slack accounts linked through the IdP-asserted email, the replacement; TASK-83.11 inventories stored human references. Fix: people-and-accounts.md tolerated line "chat adapters resolving an email to a platform account for invites and usergroup sync (incident core, oncall_sync), until TASK-83.6" plus a Changes line; IncidentConversation.account_ids_for as planned; a TASK-83.11 comment naming both callers and the incident person fields.

OQ8 (new) Production-only group invites. CONFLICT with the configuration precedent: the legacy code branches on host_info().environment == "production" (core.py:184, :196); cloud-portability.md 2026-11-04 rules a configuration key of the owning slice, not an environment name. Only production.toml sets the group ids (base.toml leaves them empty). Fix: a group is invited when its id is configured, with no environment check; production behaviour unchanged; incident-management.md one sentence (invite rules: declarer, on-call, security when flagged, policy when asked, Notify management for the Notify placement, each group only when configured).

Proposed scope changes (applied on approval):
- TASK-145.7.9: AC #4 removed (moved to 165.2); AC #1 adds "each group only when configured, no environment check"; AC #2 adds the oncall.md and people-and-accounts.md tolerated lines; AC #5 states Open.
- TASK-165.2: new AC for POST /api/v1/incidents (above), dependency on TASK-131; notes cite R6 and this assessment.
- TASK-145.7.7: note that R6's route placement moved to TASK-165.2 (2026-11-18).
- TASK-146.3: AC #1 reworded (OQ6).
- TASK-145.7.10: AC #5 names Open.
- TASK-83.11: comment (OQ7).
- doc-15 row 4: note the declare route; doc-11 row 18.L9a: notes.

---
<!-- COMMENTS:END -->
