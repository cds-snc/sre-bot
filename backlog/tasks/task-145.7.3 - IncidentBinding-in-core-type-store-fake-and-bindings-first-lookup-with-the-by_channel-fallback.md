---
id: TASK-145.7.3
title: >-
  IncidentBinding in core: type, store, fake and bindings-first lookup with the
  by_channel fallback
status: In Progress
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-09T21:54:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.1
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 500000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L2a (approved program in TASK-145.7's plan, section 2; outline in the parent plan). core/domain.py BindingKind and IncidentBinding; core/adapters/binding_items.py; RecordIncidentStore.find_by_conversation reads by_conversation first, then channel_id/by_channel (never merged; a binding whose record is missing is not an incident; bindings-table errors are classified failures); in-memory fake; [incident_core] bindings_table. Merges only after L0 has deployed. Behaviour unchanged while the table is empty.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Lookup cases tested: binding hit, fallback to by_channel, dangling binding, archived binding ignored, tenant mismatch dropped with a warning naming both tenants, two active bindings whose records both exist fail closed (AMBIGUOUS_INCIDENT_CONVERSATION), a dangling binding beside a live one (crashed declare then retry with a new incident id) resolves to the live incident, bindings-table error classified
- [x] #2 A drift test proves the declared RecordTable keys and index equal terraform/dynamodb.tf; existing RecordIncidentStore tests pass with only their construction moved to tests/factories/incident.py record_incident_store
- [x] #3 Checks parent AC #12
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #5 IncidentBinding (frozen dataclass, kind chat_conversation) and core/adapters/binding_items.py convert it to and from the stored item: binding_key shape, conversation_id only on chat kinds, unknown kind skipped, unreadable item and key mismatch refused, a '#' in a key part rejected (tested); BindingKind and IncidentBinding are exported from core/api.py
- [x] #6 [incident_core] bindings_table (default sre_bot_incident_bindings, blank rejected, base.toml) is passed by build_incident_store to RecordIncidentStore's required keyword-only bindings argument (no default), and the in-memory fake classifies every lookup case as the real store does (parity tests)
- [x] #7 decisions/incident-management.md: dangling bindings dropped before the ambiguity rule; unknown binding kind skipped and logged, unreadable known-kind binding fails closed as INCIDENT_RECORD_UNREADABLE; :52 'the bindings store' reads as the bindings table with no reader Protocol until a consumer lists an incident's bindings; dated Changes line
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-09 (human), with the program-scope revisions R1-R4 (section 10). L2a of the approved Stack L program (TASK-145.7 plan sections 2, 3, 4 and 6). Branch stacks directly on L0 (stack-l/task-145.7.1-incident-bindings-table, PR #1841); merges only after L0 has deployed and its deploy-checks post output is recorded in TASK-145.7.1 AC #4. References read: decisions/incident-management.md (Bindings :34, Stored form :40, core owns :52, Checks :111, Migration tolerated :129, Changes :177), TASK-145.7 plan and its second OQ comment, terraform/dynamodb.tf:170-208 and iam.tf:59 (L0, on this branch), doc-11 rows 18.L0-18.L5, TASK-145.7.4, 145.7.7, 145.8.1.

## 1. Re-grounded state (path:line, branch tip 5655f976)
- Lookup today: core/store.py:150 RecordIncidentStore.find_by_conversation queries index by_channel (166), bound 10 (66, full page = ambiguous 171), skips unreadable conversation maps (178), tenant filter + warning event incident_conversation_candidate_dropped (181-192), fails closed on an unreadable candidate (176), ambiguous_conversation (286). Protocol IncidentStore.find_by_conversation: store.py:108 (signature does not change). RecordIncidentStore.__init__ takes (records, table, tenants) (133). incidents_table(name) (73) is the declaration pattern.
- Fake: core/adapters/in_memory.py:117 InMemoryIncidentStore.find_by_conversation matches on incident.conversation; seed(incident, *, open) (97).
- Single production entry to the lookup: core/api.py:305 find_incident_for_conversation -> api.py:313 store.find_by_conversation. Its production callers: scribe/service.py:260; comms/service/draft.py:117, :195, :300; comms/service/history.py:39. Store construction (the only places that must carry the new table): core/api.py:244-254 build_incident_store, called from scribe/entrypoints/slack.py:184 and comms/entrypoints/slack.py:189. No other production call of find_by_conversation. build_legacy_upgrade (api.py:272) is L2b's.
- Not callers (legacy, cut over by TASK-145.8, not touched): modules/incident/db_operations.py:201 get_incident_by_channel_id, used at incident_helper.py:443, :592, information_display.py:18, core.py:377, dev/incident.py:63, db_operations.py:74.
- Settings: common/settings.py:35-58 (incidents_table, timeline_table, status_updates_table, validator at 60); config/base.toml:196-201. Existing drift-test pattern: tests/unit/features/incident/core/test_incident_core_incident_store_table.py (reads terraform/dynamodb.tf as text).
- Tests that must keep passing unchanged: test_incident_core_incident_store_find_by_conversation.py, ..._find_by_conversation_dropped.py, ..._fake.py, test_incident_core_api_build_incident_store.py, scribe/test_incident_scribe_conversation_draft.py:116 (subclasses the fake).
- Terraform (L0): hash incident_id, range binding_key, GSI by_conversation hash conversation_id, projection ALL, GSI read 1/write 2 (same as by_channel).

## 2. Domain-model gate: IncidentBinding (evolution evidence for the entity; program-level matrix is TASK-145.7 plan section 3, approved; this section is what L2a fixes in code)
Entity: child record of the incident, key (incident_id, binding_key = "<kind>#<system>#<tenant>#<vendor_id>"). Fields: incident_id, kind (BindingKind), system, tenant, vendor_id, url (hint), primary, bound_by, bound_at, archived_at. conversation_id is a stored attribute only for chat kinds (the sparse GSI key), equal to vendor_id; it is not a domain field. Visibility is the incident's. Never deleted; a replaced place gets archived_at.
Lifecycle/ownership/visibility: owned by core (decisions :52); lifecycle bound -> archived; no reuse of ConversationReference (a reference points at one artifact; a binding adds primary/bound_by/bound_at/archived_at and a kind); the record's conversation map stays the primary binding's copy.
Name check: rg for IncidentBinding/BindingKind/class *Binding in app and decisions finds only the ADR (:34) and an unrelated tooling class (bin/check_test_seams.py:84 Binding); no i18n key. No collision.
Cardinality (zero/one/many) with what L2a does:
| relation | permitted | L2a behaviour |
| incident -> bindings | 1..n active; 0 only a Closed legacy item without channel | lookup never needs the incident's list |
| incident -> primary | exactly 1 | stored, not enforced here (create, L5, owns it) |
| conversation -> active incidents | 0..1 by rule, data allows n | n>1 fails closed AMBIGUOUS_INCIDENT_CONVERSATION (the "many" cell where code assumed one) |
| conversation id -> tenants | many (Slack team ids share channel ids) | filter by stored system and tenant, warning naming both |
| binding -> kind | chat_conversation now, backstage_page later | unknown kind skipped and logged, never routed |
Scenario walk (lookup behaviour; every row becomes a test, section 5):
1 Happy path: declared channel, one active binding, record present -> that incident.
2 Legacy item, no binding yet (table empty) -> by_channel fallback = today's behaviour (all existing tests).
3 Legacy item mid-job: binding present, item still without record_version -> found through the legacy bridge (the job puts the binding first; a crash before the marker converges).
4 Rebind (not built, TASK-165.x): old binding archived_at set, new one primary -> archived ignored; lookup on the old channel falls to by_channel and finds nothing.
5 Most likely to break: one channel bound to two incidents whose records both exist (declare cannot cause it; data allows it) -> fails closed, no fallback. 5b Crashed declare then retry with a new incident id (ADR :34: the retry converges on the channel name): one dangling and one live binding on the channel -> the dangling one is dropped before the ambiguity rule, the live incident is returned (R1).
6 Dangling binding (crash between binding put and record put) -> invisible: treated as no binding, falls to by_channel, which finds nothing -> NOT_AN_INCIDENT (parent AC #12).
7 Tenant collision: same channel id in tenant A (ours) and B -> only ours counts; B dropped with a warning naming both tenants.
8 Closed incident: bindings stay active, read commands still resolve.
9 Backstage-only incident: no conversation_id, absent from the GSI, never returned.
10 Teams later: system and tenant are in the key, so a Teams conversation id never collides with Slack.
Compatibility: no stored change (L0 table only; L2a writes nothing). An old build never reads the table. Items from L5 onward keep channel_id so a revert to this lookup still finds them. Display/taxonomy extensibility: kind is not display; an unknown kind is neither displayed nor routed (fail-closed for routing, tolerant for the rest).
Decisions (rationale in section 3): D-a bindings-first, never merged (A1 :40); D-b a bindings-table failure is a classified failure with no by_channel fallback (a fallback would answer from a different source during an outage and hide it); D-c (revised, R1) with one active binding, its record is read; with more, each active binding's record is read (bounded by the query limit of 10), bindings whose record is missing are dropped, then zero -> by_channel, one -> that incident, more -> AMBIGUOUS_INCIDENT_CONVERSATION; D-d dangling falls through to by_channel; D-e unknown kind skipped+logged, known kind with unreadable fields fails closed as INCIDENT_RECORD_UNREADABLE (a binding that cannot be checked cannot be ruled out, the rule store.py:176 already applies); D-f no separate BindingStore Protocol in L2a (no consumer: L5 create, L2b and L3 upgrades write through pure item functions and the incident store; add one when a reader of a whole incident's bindings exists).
Rejected: merging both sources (double answers, hides drift); falling back on a bindings error (silent source switch); reading the incident from the index (the bindings GSI projects binding attributes, so one GetItem on the incidents table is required).
Cascade: ADR A1 carries lookup order, cardinality and stored form (L0); this PR adds the R2 ADR edits (step 7). Consumers: 145.7.4 (job) and 145.8.1 (upgrade-on-write) call binding_item/binding_key; 145.7.7 (create) calls binding_item and the store's bindings table; none needs more.

## 3. Ordered steps (production)
1. core/domain.py: BindingKind(StrEnum) with CHAT_CONVERSATION = "chat_conversation" only (backstage_page is reserved in the ADR, not declared: an undeclared value is the unknown-kind path). IncidentBinding(frozen dataclass): fields above; __post_init__ validates kind is a BindingKind, system is a WorkplaceSystem (_require_system), non-blank incident_id/tenant/vendor_id/bound_by (_require_text), no "#" in system/tenant/vendor_id (it would make binding_key ambiguous), bound_at/archived_at timezone-aware (_require_aware). ~45 LOC.
2. core/adapters/binding_items.py (new, pure, no I/O): PARTITION_ATTRIBUTE "incident_id", SORT_ATTRIBUTE "binding_key", CONVERSATION_ATTRIBUTE "conversation_id"; binding_key(kind, system, tenant, vendor_id); binding_item(binding) (stored names = field names, times through format_stored_time from incident_items.py, url/archived_at absent when unset, conversation_id only for CHAT_CONVERSATION); parse_binding_item(item) -> IncidentBinding raising UnknownBindingKindError (kind not a BindingKind) or UnreadableBindingItemError (missing/ill-typed field, or stored binding_key differs from the recomputed one). ~110 LOC.
3. core/store.py: bindings_table(name) -> RecordTable(key incident_id + binding_key, index by_conversation = KeySchema(partition="conversation_id"), physical_name by_conversation) (~10). RecordIncidentStore.__init__ gains a required keyword-only bindings: RecordTable (R3: no default, so no construction can silently skip the bindings table; reliability.md:46 precedent). find_by_conversation becomes: blank id -> not_an_incident without any query (unchanged); query by_conversation (partition vendor_id, limit 10); failure -> _failed (the table name logged is the bindings table; NOT_FOUND becomes PERMANENT_ERROR) with no fallback; full page -> ambiguous; parse each item (unknown kind: skip + warning event incident_binding_unknown_kind with incident_id and kind; unreadable: INCIDENT_RECORD_UNREADABLE); select_active_bindings(conversation, bindings) (public helper beside ambiguous_conversation, shared with the fake): drop archived_at set, drop other system/tenant with the existing incident_conversation_candidate_dropped warning (same fields plus source="binding"); 0 active -> existing by_channel path unchanged (extracted to _find_by_channel, body untouched); >1 -> ambiguous_conversation; exactly 1 -> self.get(incident_id): success -> return (legacy items read through the existing bridge), NOT_FOUND -> fall through to _find_by_channel, other failure -> classified. Docstring of the Protocol method and class updated for the order. ~110 LOC net.
4. core/adapters/in_memory.py: InMemoryIncidentStore.bind(binding) holds bindings by (incident_id, binding_key) (a binding for an unseeded incident is dangling by construction); find_by_conversation applies the same order using select_active_bindings, then the existing conversation match as the fallback. seed() unchanged. ~35 LOC.
5. common/settings.py: bindings_table field (default "sre_bot_incident_bindings", description), added to the blank-name validator and the docstring key list. config/base.toml [incident_core]: bindings_table = "sre_bot_incident_bindings". ~10 LOC. (Table names are not environment-only values; app/.env.example is regenerated by make env-example only if the generator lists defaults: run it and keep the diff only if non-empty.)
6. core/api.py: import bindings_table, BindingKind, IncidentBinding; pass bindings=bindings_table(settings.bindings_table) in build_incident_store (254); docstring; add BindingKind and IncidentBinding to __all__ (consumers in response, L2b/L5/L9a, reach core through api.py). ~8 LOC.
Total: 7 production files (domain.py, binding_items.py, store.py, in_memory.py, settings.py, base.toml, api.py), about 320 production LOC, one subsystem (incident core with its own settings slice). Planning-only edits to backlog files ride in the same commit.

## 4. Size gate verdict
Passes: ~320 LOC (<400), 7 files (<10), one subsystem (core plus its own settings slice and config line), no mechanical refactor mixed in (the by_channel body moves into a private method unchanged: the one extraction is inside the behaviour change and diff-reviewed by the existing tests), expand-only, one git revert restores the previous lookup. No decomposition proposed. Test code is excluded from the count (~450 test lines).

## 5. AC traceability and test matrix (tests under app/tests/unit/features/incident/core/ unless noted)
- AC #1 -> steps 3, 4. test_incident_core_incident_store_find_by_conversation_bindings.py, parametrized over RecordIncidentStore and InMemoryIncidentStore (parity): binding hit (scenario 1); fallback to by_channel with empty bindings table (2); legacy item behind a binding resolves through the bridge (3); dangling binding -> NOT_AN_INCIDENT (6); archived ignored (4); two active bindings -> AMBIGUOUS_INCIDENT_CONVERSATION and no incidents-table read (5); tenant mismatch dropped, the other tenant's binding does not make ours ambiguous (7); closed incident resolves (8); binding without conversation_id never reached (9); full page of 10 -> ambiguous; blank id issues no query. Real-store only (MagicMock RecordStore, as the existing failure test): bindings query error -> classified with retry hint, generic message, by_channel never queried; NOT_FOUND from a missing index -> PERMANENT_ERROR; incident get error -> classified; unreadable incident -> INCIDENT_RECORD_UNREADABLE; unknown kind skipped with warning then fallback; known kind with a bad field fails closed. Warning test (capture_logs): event incident_conversation_candidate_dropped names stored and requested system and tenant for a binding and never the vendor id.
- AC #2 -> step 3 and 5. test_incident_core_incident_bindings_table_declaration.py: bindings_table(...) key (incident_id, binding_key) and index by_conversation (partition conversation_id) equal the aws_dynamodb_table sre_bot_incident_bindings block of terraform/dynamodb.tf (hash_key, range_key, GSI name, key_schema attribute_name, projection_type ALL) and the settings default and base.toml value equal the terraform table name. The listed existing find_by_conversation, dropped, fake and build tests pass unmodified (run first, before any change, as the red/green baseline).
- AC #3 (checks parent AC #12) -> steps 3, 4; closed by the AC #1 cases above.
- New proposed ACs (section 6) -> test_incident_core_binding_items_convert.py (key shape, round trip, conversation_id only for chat, url/archived_at absent when unset, unknown kind, unreadable field, key mismatch, "#" rejected by IncidentBinding), test_incident_core_incident_binding_validate.py (domain validation), settings load additions in test_incident_common_settings_load.py (default, env override, blank rejected), test_incident_core_api_build_incident_store.py (additive: a binding put in the configured bindings table is found through the built store; names the wiring), test_incident_core_api_surface.py (additive: exports).
- Support: tests/factories/incident.py gains binding_on(channel_id, incident_id, **overrides) -> IncidentBinding and record_incident_store(...) (R3); no new seam (RecordStore is a Protocol; MagicMock(spec=RecordStore) is the existing failure-injection pattern).
- Every step maps to an AC: 1-2 -> new AC #5; 3-4 -> #1, #3; 5 -> #2 and new AC #6; 6 -> #6.

## 6. Assumptions and doubts (each with its check)
1 L0 is deployed with its IAM grant before this merges, otherwise every command (comms, scribe) fails closed on AccessDenied. Check: TASK-145.7.1 AC #4 post output recorded; human ticks before merge; a failed grant is detectable on the first lookup log incident_store_failed table=sre_bot_incident_bindings.
2 GSI reads are eventually consistent only (AWS DynamoDB docs, secondary indexes; same property as by_channel today, RecordStore contract store.py:237); a command sent within the replication delay of a declare can miss. Not new, but now two indexes; L9a (declare) should not issue a command in the same second. Check: noted for L9a.
3 Capacity: GSI read 1 / base 2 as by_channel; each lookup adds one Query and, on a hit, one GetItem (previously one Query returning the item). Empty table = one extra empty Query. Check: no throttle in the soak; a throttle surfaces as TRANSIENT_ERROR with retry_after (tested).
4 (revised, R3) bindings is a required keyword-only argument. The 17 existing test constructions (8 files under tests/unit/features/incident/core/ and comms/test_incident_comms_status_update_security_gate.py) move to tests/factories/incident.py record_incident_store(records, *, tenants=..., table=..., bindings=...), whose default bindings table is the declared one; only the construction line changes, every assertion stays. Check: rg 'RecordIncidentStore(' finds only api.py and the factory.
5 select_active_bindings in store.py is shared with the fake so the two cannot drift; store.py grows ~110 lines to ~560. Check at review: if over the file-size convention, move the helper and the table declaration to core/bindings.py in the same PR (no behaviour change).
6 Reusing event incident_conversation_candidate_dropped with source="binding" keeps one alert/dashboard key; the existing dropped test asserts fields by name, so an added field is compatible. Check: that test runs unchanged.
7 Reusing INCIDENT_RECORD_UNREADABLE for an unreadable binding (message "A stored incident record could not be read.") avoids a new public ErrorCode (contracts change). Check: reviewer accepts; otherwise a BINDING_RECORD_UNREADABLE code is a contracts edit in this PR (+3 LOC, second subsystem is not tripped).
8 make check-package-shape accepts a new adapters/binding_items.py in core (manifest from TASK-114.3); make check-fake-coverage is unaffected (the fake is a feature core fake, out by rule). Check: run both.
9 InMemoryRecordStore.query treats an item missing the index key as outside the index (in_memory.py:134), so sparse behaviour is testable without DynamoDB. Verified by reading the code.

## 7. Blast radius and rollback
Affects every incident command (comms status update, history, draft; scribe summarize): the lookup now reads one more table. While the table is empty behaviour is the same as today (fallback), plus latency of one empty Query. Failure modes: table or IAM missing -> all lookups classified failures (assumption 1, ordering gate); throttling -> TRANSIENT with retry hint. Nothing is written, no stored data changes, so one git revert restores the previous lookup; the table stays (L0). Ordering: L0 deployed (deploy-checks post recorded) before this merges; L2b (job binding step), L5 (create) and L3 (upgrade-on-write) build on it. No terraform/CI/env change; the only config is the table name default in base.toml (settings default matches, so no environment variable is needed in any environment).

## 8. Verification
During implementation: ruff check and the targeted test files only (the unchanged existing files first, then the new ones). At the end, from app/, one after the other and once each: uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'; uv run pytest tests --ignore=tests/smoke; plus uv run lint-imports (make check-import-contracts), make check-package-shape, make check-test-seams, and make check-fake-coverage. Evidence (commands and output) goes in the implementation notes.

## 9. Open questions
None. D-d, D-e and D-f approved 2026-11-09 with the revisions below.

## 10. Revisions approved 2026-11-09 (program-scope assessment: ADRs, doc-11, doc-15, doc-16)
R1 (conflict fixed): the proposed D-c (ambiguity on active bindings before any record read) contradicted incident-management.md:34 (a crash between binding and record leaves a binding no lookup returns; a retry converges on the channel name): a retry with a new incident id would make the channel permanently ambiguous. Revised D-c above; scenario 5b and a test (crash then retry: dangling plus live -> the live incident) added; AC #1 reworded. TASK-145.7.7 AC #1 gains the retry case. Source: GSI reads are eventually consistent (AWS DynamoDB ReadConsistency, bp-indexes-gsi-replica), so a binding may briefly precede its record. doc-15: TASK-165.5 gives a child incident its own binding (n bindings per incident, not n incidents per conversation); no row shares a conversation between incidents, so failing closed on two live incidents stands.
R2 (ADR gaps closed, step 7): D-d is decided by incident-management.md:40 and :111 (prefer bindings, fall back to by_channel, never merged; a binding whose record is missing is not an incident; TASK-145.7 D5, parent AC #12). D-e is a gap (prior: TASK-145.5.4/145.5.5 INCIDENT_RECORD_UNREADABLE, store.py fail-closed candidate rule; OWASP fail safely, CWE-636). D-f mildly conflicts with :52 ("the bindings store"; prior: TASK-145.5.5 deleted per-read-path lookup Protocols).
R3 (human ruling): bindings is a required keyword-only argument now (reliability.md:46: a facade's policy is a required constructor argument with no default); test constructions move to the factory.
R4: the drift test (AC #2) and settings are unchanged; the size gate still passes: production ~335 LOC, 8 files including the ADR; test construction moves are mechanical lines in existing test files.

## 11. Step 7 (ADR, decisions/incident-management.md)
- After the :34 commit-order clause: "A binding whose record is missing is dropped from the candidates before the ambiguity rule, so a crashed declare and its retry do not make the conversation ambiguous."
- Stored form, after "a binding whose record is missing is not an incident": "A binding of an unknown kind is skipped and logged, never routed; an unreadable binding of a known kind fails the lookup closed with INCIDENT_RECORD_UNREADABLE, because it cannot be ruled out."
- :52 "and the bindings store" becomes "and its bindings table (written through IncidentStore.create and the item functions; a bindings reader Protocol arrives with the first consumer that lists an incident's bindings)".
- Changes: "- 2026-11-09: dangling bindings are dropped before the ambiguity rule; an unknown binding kind is skipped and logged, an unreadable known-kind binding fails closed as INCIDENT_RECORD_UNREADABLE; the bindings table has no reader Protocol until a consumer lists an incident's bindings (TASK-145.7.3).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09: planned, proposed, awaiting approval. Size verdict: passes the single-PR gate (about 320 production LOC, 7 production files, one subsystem, expand-only, one revert restores the previous lookup); no decomposition. Domain-model gate: IncidentBinding evidence and decisions D-a to D-f recorded in the plan (sections 2 and 6). Waits on L0 deployed (TASK-145.7.1 AC #4 recorded). Status unchanged (To Do).

2026-11-09 (human): plan approved with the program-scope revisions R1-R4 (plan section 10): D-c revised to drop dangling bindings before the ambiguity rule (conflict with incident-management.md:34 fixed; retry test and AC #1 wording); D-d, D-e, D-f accepted with ADR text in step 7 (new AC #7); bindings is a required keyword-only argument now (human ruling; reliability.md:46), test constructions move to the factory (AC #2, #6). TASK-145.7.7 AC #1 gains the retry case. Size gate still passes (~335 production LOC, 8 files).

2026-11-09 implementation. Added core/domain.py BindingKind + IncidentBinding; core/adapters/binding_items.py (binding_key, binding_item, parse_binding_item, UnknownBindingKindError, UnreadableBindingItemError); core/store.py bindings_table, select_active_bindings, RecordIncidentStore(bindings=) required keyword-only, find_by_conversation bindings-first (D-c revised: read each active binding's record, drop missing, 0 -> _find_by_channel, 1 -> that incident, >1 AMBIGUOUS); InMemoryIncidentStore.bind; [incident_core] bindings_table (settings + base.toml); api.py wiring and exports; ADR step 7 edits in decisions/incident-management.md. Tests: 4 new files (binding validate, binding items convert, bindings table declaration drift, find_by_conversation_bindings parity), additive cases in settings load, build_incident_store and api surface; 17 RecordIncidentStore constructions moved to tests/factories/incident.py record_incident_store (plus binding_on). Deviations: (1) test_incident_core_incident_store_find_by_conversation.py query-bound test asserted spy.query.call_args_list equals exactly one by_channel query; the bindings query now precedes it, so that one assertion filters the calls to the incidents table (intent unchanged); (2) a non-text stored kind is UnreadableBindingItemError (fail closed), only an unrecognised text kind is the unknown-kind skip; (3) ruff format applied to the two new test files. Gates (from app/): ruff check: All checks passed; mypy: Found 41 errors in 14 files (all pre-existing, none in touched files); pytest tests --ignore=tests/smoke: 6744 passed, 193 warnings in 190.22s; uv run lint-imports: Contracts: 13 kept, 0 broken; make check-package-shape: OK no net-new violations (3 baselined); make check-test-seams: OK (47 and 12 baselined); make check-fake-coverage: OK (4 baselined gaps). Baseline before changes: 868 passed in the incident core, scribe draft and comms security gate tests.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-09T20:27:00Z

---

Plan review notes (2026-11-09). AC changes: two ACs added (#5 type and item conversion, #6 settings wiring and fake parity); none removed or reworded. Description wording to confirm: 'store' is read as the lookup in RecordIncidentStore plus the bindings table declaration; no separate BindingStore Protocol is planned (no reader of a whole incident's bindings exists before TASK-145.8.1/145.7.7, which write through binding_item and the incident store). Decisions to confirm at approval: dangling binding falls through to by_channel (same answer in every reachable case); an unreadable binding of a known kind fails closed as INCIDENT_RECORD_UNREADABLE (no new ErrorCode); RecordIncidentStore takes bindings as an optional keyword so existing constructions pass unchanged (AC #2), with the wiring proved in build_incident_store tests. Cited practice: DynamoDB GSIs are eventually consistent only and sparse indexes are the documented way to index a subset (AWS DynamoDB developer guide, secondary index best practices), matching the existing by_channel behaviour and the ADR.

---

created: 2026-11-09T21:17:00Z

---

2026-11-09 (human approved): program-scope assessment of D-d, D-e, D-f and the optional bindings argument. ADR: D-d decided (incident-management.md:40, :111); D-e gap; D-f mild conflict with :52; optional argument gap (reliability.md:46 favours required). Conflict found: D-c vs :34 (crash + retry -> permanent ambiguity); fixed by R1. Prior: TASK-145.7 D5 and parent AC #12; TASK-145.5.4/145.5.5 (INCIDENT_RECORD_UNREADABLE, Protocols deleted); TASK-145.5.7.1 D2 (optional arg, contrasted). Upcoming: 145.7.4, 145.7.7, 145.8.1 (item functions); doc-15 TASK-165.5 (child binding: n bindings per incident, no shared conversation). Sources: docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html; .../bp-indexes-gsi-replica.html; wiki.owasp.org/index.php/Fail_safely; CWE-636.

---
<!-- COMMENTS:END -->
