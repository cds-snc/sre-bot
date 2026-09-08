---
id: TASK-25.1.6.7
title: >-
  Build the incident Google Docs adapter and move modules incident Docs call
  sites onto it
status: Done
assignee: []
created_date: '2026-09-02 15:02'
updated_date: '2026-09-08 18:33'
labels:
  - clients
  - phase-3
  - architecture
milestone: m-3
dependencies:
  - TASK-25.1.6.6
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - decisions/layers.md
  - decisions/migration.md
  - app/integrations/google_workspace/google_docs.py
  - app/modules/incident/incident_document.py
  - app/packages/incident/scheduling/availability.py
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 138000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First of the legacy-incident adapter slices, and the one that makes the architectural choice the rest inherit.

CONSUMERS (grep-confirmed): app/modules/incident/incident_document.py, incident_status.py, incident_conversation.py, information_update.py all call integrations.google_workspace.google_docs.create / batch_update / get_document directly. None has a try/except of its own; all rely on the vendor package's execute_google_api_request. These are legacy app/modules/* files with NO adapter tier, which is precisely why TASK-25.1.1 through .5 could not inline classification and had to leave the deviation in place.

THE DECISION THIS SLICE MUST MAKE FIRST, because .8 (Drive), .9 (Calendar/Meet) and .10 (Sheets) all follow it: where does the incident feature's Google boundary live? The options are (a) a real app/packages/incident/adapters/ file, which means starting the incident feature package - a strangler move with scope well beyond Docs; (b) an adapter module inside app/modules/incident/ that satisfies the boundary contract (own factory call, own try/except + classify, own typed results) without yet claiming to be a package; (c) reuse or extend an existing package adapter. decisions/copilot-instructions treats app/modules as legacy and not an architectural reference, and decisions/feature-packages.md governs (a). Pick one, write the rationale into the notes, and state it in the PR - do not leave the next three slices to re-litigate it.

SCOPE ONCE DECIDED: the chosen adapter builds a stub-typed DocsResource from integrations.google_workspace.client.get_docs_service, calls documents().create / .batchUpdate / .get directly, does its own try/except + classify_google_error, translates responses into typed results (decisions/sdk-typing.md item 3), and the four modules/incident files call the adapter instead of the vendor module. integrations/google_workspace/google_docs.py is then deleted (TASK-25.1.6.6 removes its only other consumer) along with extract_google_doc_id's relocation from TASK-25.1.6.2.

DO NOT reproduce the vendor module's create/batch_update/get_document signatures in the adapter. They are SDK mirrors; the adapter's methods should express what the incident feature actually needs (create an incident document, replace a section, read the current body), not what the Docs API endpoints are named. Reproducing the mirror one layer up would defeat the entire exercise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The architectural decision for where the incident feature's Google boundary lives is made, written into the task notes with its rationale, and stated in the PR description; TASK-25.1.6.8/.9/.10 reference it rather than re-deciding
- [x] #2 The adapter builds a stub-typed DocsResource via get_docs_service and performs its own try/except + classify_google_error around documents().get/.batchUpdate calls; documents().create has zero production callers today and is not reimplemented (google_docs.create is dead code, deleted not ported)
- [x] #3 The adapter's public functions are expressed in incident-domain terms and return typed results, not SDK-shaped passthroughs mirroring create/batch_update/get_document
- [x] #4 All four consumers (incident_document.py, incident_status.py, incident_conversation.py, information_update.py) call the adapter or its relocated domain helper; none imports integrations.google_workspace
- [x] #5 app/integrations/google_workspace/google_docs.py is deleted with its test file, grep-verified zero references repo-wide outside backlog/ and tmp/
- [x] #6 Existing incident tests pass, with any intentional behaviour change (in particular what each consumer now does on a classified Docs failure, which today is an unhandled propagation) named explicitly in the notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Decision (see 2026-09-08 comment for full rationale)

New umbrella subdomain `app/packages/incident/documents/` (second subdomain alongside
the already-shipped `packages/incident/scheduling/`), rule-5 lighter path (no
hookimpl/entry-point — `app/modules/incident` stays the registered capability):

- `packages/incident/documents/__init__.py` — empty, namespace only (mirrors
  `scheduling/__init__.py`).
- `packages/incident/documents/domain.py` — `extract_google_doc_id`, relocated verbatim
  (pure regex, no I/O).
- `packages/incident/documents/adapters/__init__.py` — empty.
- `packages/incident/documents/adapters/google_docs.py` — the only file importing
  `integrations.google_workspace`; builds `DocsResource` via `get_docs_service`, its own
  try/except `HttpError` -> `classify_google_error`, no `execute_google_api_request`.

Adapter's public functions (module-level, not a class — no Protocol/service exists yet
to inject one into; matches `scheduling/availability.py`'s plain-function shape rather
than inventing an unused abstraction):

```python
def replace_placeholders(document_id: str, replacements: Mapping[str, str], match_case: bool = True) -> bool:
    """Replace each key with its value via replaceAllText. Returns whether any occurrence changed."""

def fetch_document_content(document_id: str) -> list[dict[str, Any]] | None:
    """Return the document body's structural-element list, or None on failure/not-found."""

def apply_document_edits(document_id: str, requests: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply a batchUpdate request list; returns the raw reply dict, or {} on failure."""
```

Naming rationale (AC#3): `update_boilerplate_text`'s 6 replaceAllText ops and
`update_incident_document_status`'s N replaceAllText ops are the same operation
(placeholder-style text substitution) with different `matchCase` — collapsed into one
`replace_placeholders` instead of two near-identical `batch_update` passthroughs.
`get_timeline_section`/`replace_text_between_headings` need the raw structural-element
list to walk headings/links/indices themselves (that walking logic is
incident-document-specific business logic, out of this task's scope to redesign) —
`fetch_document_content` names the real need (read the body to find sections) rather
than mirroring `get_document`. `replace_text_between_headings`'s insert/delete/style
request list is genuinely low-level document editing with no clean single-purpose name
available without a deeper rewrite; `apply_document_edits` is the most honest name
available without expanding scope into rewriting that construction logic.

Error-handling behaviour change (AC#6, matches the TASK-25.1.6.6/TASK-25.1.5.1
precedent): today, `incident_document.py` has no try/except at all — any Google API
failure propagates uncaught (via `execute_google_api_request`'s unconditional
`raise`). After this change, a *classified* `HttpError` is caught in the adapter,
logged (`incident_document_placeholder_replace_failed` /
`incident_document_fetch_failed` / `incident_document_edit_failed`), and degrades:
`replace_placeholders` -> `False`, `fetch_document_content` -> `None`,
`apply_document_edits` -> `{}`. Callers need small adjustments for the new `None`
case: `get_timeline_section`/`replace_text_between_headings` must treat
`fetch_document_content(...) is None` the same as their existing "content not found"
path (return `None` / log-and-return, no new branch shape). Unclassified/unmapped
exceptions still propagate raw (`classify_google_error`'s own contract) — unchanged
for that subset.

## Steps

1. Create `packages/incident/documents/{__init__.py,domain.py,adapters/__init__.py,adapters/google_docs.py}`
   per the design above. `domain.py` gets `extract_google_doc_id` moved verbatim (same
   body, same docstring) from `integrations/google_workspace/google_docs.py`.
2. `modules/incident/incident_document.py`: replace
   `from integrations.google_workspace import google_docs, google_drive` with
   `from integrations.google_workspace import google_drive` (Drive stays, out of scope)
   plus `from packages.incident.documents.adapters import google_docs as incident_docs`
   (or a plain `from packages.incident.documents.adapters.google_docs import
   replace_placeholders, fetch_document_content, apply_document_edits` — pick whichever
   reads more clearly at the 5 call sites; both are equally compliant). Rewrite the 5
   call sites:
   - `update_boilerplate_text`: build the 6-entry `{marker: value}` mapping instead of
     the `replaceAllText` request list; call `replace_placeholders(document_id,
     mapping, match_case=True)`.
   - `update_incident_document_status`: build the `{f"Status: {status}": f"Status:
     {new_status}"}` mapping; call `replace_placeholders(document_id, mapping,
     match_case=False)`; its `bool` return becomes the function's return directly
     (drop the `result.get("replies", [])` parsing — that shape is now internal to the
     adapter).
   - `get_timeline_section`: call `fetch_document_content(document_id)`; if `None`,
     return `None` immediately (mirrors the existing "not found" early-return shape);
     else use the returned list as today's `content`.
   - `replace_text_between_headings` (2 call sites: the initial fetch and the final
     `google_docs.batch_update(doc_id, requests)`): fetch via
     `fetch_document_content(doc_id)` (handle `None` the same way as above); apply via
     `apply_document_edits(doc_id, requests)` (return value already unused today, no
     further change needed).
3. `modules/incident/incident_status.py`, `incident_conversation.py`,
   `information_update.py`: change the single `extract_google_doc_id` import source
   from `integrations.google_workspace.google_docs` to
   `packages.incident.documents.domain`; call sites are unchanged (same function
   signature, same behaviour, pure relocation).
4. Delete `app/integrations/google_workspace/google_docs.py` and
   `app/tests/integrations/google_workspace/test_google_docs.py`. Grep-verify zero
   remaining references repo-wide outside `backlog/` and `tmp/`.
5. Rewrite `tests/modules/incident/test_incident_document.py`: replace
   `@patch("modules.incident.incident_document.google_docs")` with patches on the new
   adapter functions (`@patch("modules.incident.incident_document.replace_placeholders")`
   etc., or patch the imported module object if step 2 used the module-alias import
   style — keep whichever import style step 2 chose, patch that same name). Every
   existing assertion's *intent* (which requests were built, what a given API response
   drives) is preserved; only the mocked seam moves from the deleted vendor module to
   the new adapter functions. Add a couple of new cases per AC#6: a classified failure
   from each of the 3 adapter functions degrades as designed (no crash), matching the
   sibling-slice convention.
6. Update `tests/modules/incident/test_incident_status.py` (6 patch-path renames),
   `test_incident_conversation.py` (3, already fully-qualified strings — just the
   dotted path changes), `test_information_update.py` (1) — mechanical, no assertion
   changes.
7. New `tests/unit/packages/incident/documents/test_incident_documents_adapter.py` —
   unit tests for `replace_placeholders`/`fetch_document_content`/`apply_document_edits`
   against a MagicMock `DocsResource` (mirrors the `_drive_resource_fake` /
   `_docs_resource_fake` pattern already left behind by TASK-25.1.5.1 for the sibling
   Docs half — reuse that shape, a fresh per-file helper per this repo's established
   convention, not a shared fixture). Cover: success path per function, HttpError ->
   classified degrade per function, one unmapped-exception-propagates case.
8. New `tests/unit/packages/incident/documents/test_incident_documents_boundaries.py` —
   mirrors `scheduling/test_incident_scheduling_boundaries.py`: asserts
   `extract_google_doc_id` is exposed by `packages.incident.documents.domain`, is absent
   from `app/integrations/google_workspace/` sources, and that
   `packages/incident/documents/` ships no hookimpls (`"hookimpl"` string absent from
   every `.py` under the subdomain).
9. Fix `tests/unit/packages/incident/scheduling/test_incident_scheduling_boundaries.py::
   test_extract_google_doc_id_stays_in_google_docs` — this test currently pins
   `extract_google_doc_id` living in `google_docs` (that module is deleted by step 4).
   Delete this one test function (its replacement assertion is step 8's boundary test);
   leave every other test in that file untouched — they test the scheduling subdomain,
   unrelated to this task.
10. Repo-wide grep for `google_docs` (excluding `backlog/`, `tmp/`) to confirm the only
    remaining hits are the new `packages/incident/documents/adapters/google_docs.py`
    module name and its own tests/imports.

## AC-to-step traceability

- AC#1 (decision recorded) -> this comment + plan header; no code step.
- AC#2 (adapter construction/classification) -> step 1.
- AC#3 (domain-named methods) -> step 1 (design section).
- AC#4 (no consumer imports integrations.google_workspace) -> steps 2-3, verified by
  step 10.
- AC#5 (google_docs.py deleted, zero refs) -> step 4, verified by step 10.
- AC#6 (tests pass, behaviour change named) -> steps 5-9; the degrade-on-failure change
  is named in the Decision section above, not just in code comments.

## Test matrix

| Layer | File | What |
|---|---|---|
| Unit | tests/unit/packages/incident/documents/test_incident_documents_adapter.py | adapter functions: success, classified-HttpError degrade, unmapped-exception propagates |
| Unit | tests/unit/packages/incident/documents/test_incident_documents_boundaries.py | relocation + no-hookimpl boundary (mirrors scheduling's) |
| Legacy/unit | tests/modules/incident/test_incident_document.py | existing behaviour preserved at the new seam + new degrade cases |
| Legacy/unit | tests/modules/incident/{test_incident_status,test_incident_conversation,test_information_update}.py | import-path rename only, zero behaviour change |

## Assumptions / doubts for human review

1. Adapter shape is plain functions, not a class implementing a Protocol (no service
   layer exists in `packages/incident/documents/` yet to inject one into, and
   `scheduling/availability.py` sets the same plain-function precedent) — flagged in
   case the reviewer wants a Protocol seam pre-built for whenever incident's full
   migration lands.
2. `fetch_document_content`'s return stays a raw structural-element `list[dict]`, not a
   new frozen dataclass — modelling Google Docs' structural elements fully is out of
   proportion to this slice (the walking/parsing logic in `get_timeline_section`/
   `replace_text_between_headings` stays exactly as complex as it is today, just fed by
   the adapter instead of the vendor module).
3. `apply_document_edits`'s name is the best available without rewriting
   `replace_text_between_headings`'s request-construction logic (out of scope) — flagged
   as the one place AC#3's "not an SDK passthrough" bar is met more weakly than the other
   two methods.

## Blast radius / rollback

Single subsystem (the incident feature's Google Docs boundary), ~9 production files (4
new, mostly small; 4 one-line-import-change modules; 1 deletion), test-only changes
otherwise. No terraform/CI/settings changes. Fully reversible by a single revert — no
data migration, no schema change, no new external dependency.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-03 14:21
---
SCOPE NARROWING from TASK-25.1.6.2 planning (2026-09-03, task-planner). TASK-25.1.6.2's plan removes the `from integrations.google_workspace import google_docs` import from incident_conversation.py, incident_status.py and information_update.py entirely — grep-confirmed each file's ONLY use of google_docs was extract_google_doc_id (now relocated to modules/incident/utils.py), none of the three calls create/batch_update/get_document. So once TASK-25.1.6.2 lands, this task's AC#4 ("none imports integrations.google_workspace") is already true for 3 of the 4 named consumers before this task starts — only incident_document.py will still import google_docs (for batch_update/get_document), and it is therefore the only file this task's adapter migration needs to repoint for the "none imports" half of AC#4. The adapter itself, its try/except+classify_google_error, and the create/batchUpdate/get typed-result work are unaffected and still needed exactly as scoped.
---

created: 2026-09-03 15:10
---
CORRECTION to the 2026-09-03 comment above (task-planner). That comment claimed TASK-25.1.6.2 would remove the google_docs import from incident_conversation.py, incident_status.py and information_update.py entirely. That is no longer accurate: TASK-25.1.6.2 was re-scoped mid-planning to defer extract_google_doc_id's relocation to THIS task, specifically because this task is the one deciding where the incident feature's Google-boundary package lives, and creating a second, unrelated new package name for extract_google_doc_id in TASK-25.1.6.2 risked colliding with that undecided shape. TASK-25.1.6.2 now only relocates the 4 Calendar-availability helpers (to a new app/packages/incident_scheduling/ package, per decisions/migration.md's new rule 5). extract_google_doc_id stays in app/integrations/google_workspace/google_docs.py untouched, and all 4 named consumers (incident_document.py, incident_status.py, incident_conversation.py, information_update.py) still import google_docs exactly as today. This task's own scope (AC#4/#5) is unchanged by TASK-25.1.6.2 after all — disregard the narrowing claimed in the prior comment.
---

created: 2026-09-03 15:10
---
ACTIONABLE FOR THIS TASK: extract_google_doc_id itself is not a Google SDK call (pure regex over a URL string) - it does not belong in whatever adapter this task builds for create/batchUpdate/get. When this task deletes google_docs.py, it must also decide extract_google_doc_id's destination. It qualifies for decisions/migration.md's new rule 5 lighter path (no hookimpl/entry-point needed) the same way TASK-25.1.6.2's app/packages/incident_scheduling/ does - likely its own small package or a domain.py inside whichever package this task creates for the incident Docs boundary.
---

created: 2026-09-08 17:23
---
FRAMING CORRECTION + DECISION MADE (2026-09-08, task-planner, planning pass). The
Description's option (a) ("a real app/packages/incident/adapters/ file... a strangler
move with scope well beyond Docs") is now stale. `app/packages/incident/` already exists
as an empty-`__init__.py` umbrella namespace with one live subdomain,
`packages/incident/scheduling/` (shipped by TASK-25.1.6.2, confirmed via
`modules/incident/schedule_retro.py` already importing
`packages.incident.scheduling.availability` in production). Starting a *second*
subdomain under that umbrella is not "starting the incident feature package from
scratch" — the package boundary, empty `__init__.py`, and no-hookimpl precedent are
already established and working.

DECISION: option (a), refined. New subdomain `packages/incident/documents/` (bounded
context: incident document construction/editing artifacts), empty `__init__.py`
per the umbrella rule, holding:
- `adapters/google_docs.py` — the only file importing `integrations.google_workspace`,
  building a stub-typed `DocsResource` via `get_docs_service`, with its own
  try/except `HttpError` -> `classify_google_error` (no `execute_google_api_request`,
  matching TASK-25.1.6.6/TASK-25.1.5.1's already-approved shape, not TASK-25.1.6.11's
  target either way).
- `domain.py` — `extract_google_doc_id`, relocated per decisions/migration.md rule 5
  (host-surface-free pure logic, no hookimpl/entry-point). This is the destination the
  task's own 2026-09-03 15:10 comment anticipated ("its own small package or a domain.py
  inside whichever package this task creates").

Ships zero hookimpls/entry-point line, same as `scheduling/` — `app/modules/incident`
stays the registered incident capability; this is not a capability migration under
rule 1's freeze, it is the rule-5 lighter path applied to a second concern.

REJECTED: option (b) (adapter inside app/modules/incident/) — copilot-instructions
treats app/modules as legacy/non-normative, and layers.md names
`app/packages/<feature>/adapters/<provider>.py` as the only sanctioned Path-B location;
inventing a second, unblessed adapter shape inside a frozen module when a correctly-shaped
umbrella home already exists has no justification. Option (c) (extend
`packages/incident_draft/adapters/google_docs.py`) — rejected: that adapter's domain is
AI-draft generation specifically, not general incident-document editing; forcing
unrelated status/timeline/boilerplate editing through it would blur a feature-scoped
adapter's purpose, and incident_draft is itself a named flat-naming deviation pending
TASK-38, not a home to grow.

TASK-76 CHECKED (per human instruction) for scope impact: zero file overlap
(infrastructure/directory + packages/access only; nothing under modules/incident,
packages/incident, or integrations/google_workspace/google_docs.py). Its
TASK-76.2 precedent (`packages/access/common/` as a shared-kernel umbrella subdomain,
generic-infra/feature-owned-policy split) corroborates the same umbrella pattern applied
here, but does not change this task's file scope.

AC#2 CORRECTED (bulk --acceptance-criteria replace): dropped its `.create` mention —
`google_docs.create` has zero production callers (grep-confirmed, only its own vendor
test calls it) and is deleted, not ported; reimplementing an unused method would be
scope creep. Wording now covers only `.get`/`.batchUpdate`, the two calls
`incident_document.py` actually makes.
---

created: 2026-09-08 18:27
---
POST-REVIEW RENAME (2026-09-08): packages/incident/documents/domain.py renamed to utils.py. decisions/feature-packages.md reserves domain.py for frozen dataclasses/enums/invariants; extract_google_doc_id is a stateless parsing helper with no domain modeling, so domain.py was a misnomer (matches the utils.py precedent set by not naming it after a reserved slot). Docstring reworded to drop the confusing Google-API mention and instead flag the forward-looking migration expectation, now tracked in TASK-80: if Google Docs is ever promoted to a core DocumentProvider infrastructure Protocol (mirroring DirectoryProvider/TASK-22.4), this helper migrates with it. All consumer imports (incident_status.py, incident_conversation.py, information_update.py) and their tests updated; information_update.py's pre-existing modules.incident.utils import aliased to incident_utils to avoid a name collision with the new packages.incident.documents.utils import.
---
<!-- COMMENTS:END -->
