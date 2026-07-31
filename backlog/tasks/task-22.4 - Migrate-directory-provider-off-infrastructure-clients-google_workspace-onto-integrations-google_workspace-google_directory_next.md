---
id: TASK-22.4
title: >-
  Migrate directory provider off infrastructure/clients/google_workspace onto
  integrations/google_workspace/google_directory_next
status: To Do
assignee: []
created_date: '2026-07-29 21:11'
updated_date: '2026-07-31 17:50'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.3
  - TASK-70
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/infrastructure/directory/factory.py
  - app/infrastructure/directory/google.py
parent_task_id: TASK-22
priority: high
ordinal: 107000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-22 (parent). Repoint the Google Workspace directory consumers off the deprecated GoogleWorkspaceClients facade onto integrations/google_workspace/google_directory_next.

Call sites: infrastructure/directory/factory.py:6 (GoogleWorkspaceClients, get_google_workspace_clients) and infrastructure/directory/google.py:7 (GoogleWorkspaceClients). GoogleDirectoryProvider calls self._directory.<method> at 11 sites (google.py lines 287-705): health_check, get_user, list_users, list_members, get_batch_group_members, get_group, add_member, remove_member, has_member, list_groups, list_user_groups. google_directory_next.py covers most as MODULE-LEVEL OperationResult functions. VERIFY GAP: confirm a health_check equivalent exists in google_directory_next/google_service_next; if absent, add a minimal OperationResult health_check there (behavior-parity with the deprecated one) as part of this slice. Rework factory.py so GoogleDirectoryProvider no longer receives a GoogleWorkspaceClients facade. Preserve all OperationResult outcomes and payload normalization exactly. Wire to _next as-is (no rename = TASK-23; no raise/classify = TASK-25).

Test migration: relocate app/tests/integrations/google_workspace/test_google_directory_next.py and test_google_service_next.py to app/tests/unit/integrations/google_workspace/; keep directory provider tests in tests/unit/infrastructure/directory/, updating mock target paths. Legacy tests/integrations/ count must drop.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/directory/factory.py and google.py no longer import infrastructure.clients.google_workspace; GoogleDirectoryProvider is backed by a Google Directory adapter that calls the discovery Resource directly (built by a factory with cache_discovery=False, static_discovery=True that RAISES, and whose return is annotated with the google-api-python-client-stubs-provided Resource type, e.g. AdminDirectoryResource, imported under TYPE_CHECKING per decisions/sdk-typing.md item 3) and translates responses into typed domain dataclasses via classify_google_error - the execute_google_api_call dispatcher and the get_google_api_command_parameters docstring scraper are NOT on the directory path
- [ ] #2 A health_check equivalent returning OperationResult exists in integrations/google_workspace and is used by GoogleDirectoryProvider with behavior parity
- [ ] #3 All tests/unit/infrastructure/directory/ tests pass behavior-neutral (identical OperationResult outcomes + payload normalization across the 11 provider calls); classify_google_error has coverage under tests/unit/integrations/google_workspace/; google_directory_next/google_service_next are left for TASK-23 deletion; touched vendor tests land under tests/unit (legacy tests/integrations/ count does not grow)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: directory provider OperationResult outcomes identical; PR references decisions/layers.md, decisions/outbound-clients.md, and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
RESEQUENCED (2026-07-31, decisions/sdk-typing.md): migrates the Google directory provider DIRECTLY onto the target shape - a factory-built discovery Resource that RAISES + an adapter that calls it directly and classifies - deleting the execute_google_api_call dispatcher and the __doc__-scraping param filter for the directory surface. Absorbs the Google-directory portions of the old TASK-23 (rename) and TASK-25 (raise/classify) so the provider is touched ONCE.

GROUNDING (re-verify at implementation): infrastructure/directory/factory.py:6 imports GoogleWorkspaceClients/get_google_workspace_clients; google.py:7 imports GoogleWorkspaceClients. GoogleDirectoryProvider calls self._directory.<method> at 11 sites (google.py ~287-705): health_check, get_user, list_users, list_members, get_batch_group_members, get_group, add_member, remove_member, has_member, list_groups, list_user_groups. Today those resolve through google_directory_next -> execute_google_api_call (google_service_next), which walks the discovery tree by string and scrapes method docstrings for valid params (get_google_api_command_parameters) - the exact anti-patterns decisions/sdk-typing.md retires.

RESEQUENCED AGAIN (2026-07-31, same day, second pass): google-api-python-client is still maintenance-mode, but its discovery Resource is NO LONGER treated as permanently untyped. TASK-70 (updated) adds google-api-python-client-stubs, a dev-only community stub package that types discovery.build()'s return per service+version the same way types-boto3 types a boto3 client. So the factory in this task both (a) builds the Resource so it RAISES (no OperationResult, no retry loop, no docstring scraping) AND (b) annotates that return with the stub-provided type (e.g. `service: AdminDirectoryResource = build("admin", "directory_v1", ...)`, importing `AdminDirectoryResource` from `googleapiclient._apis.admin_directory_v1` only under `if TYPE_CHECKING:`). The adapter's 11 direct Resource calls get real method/parameter completion and mypy checking as a result - typing is no longer deferred entirely to the translated dataclass at the far end, though that translation step (domain dataclass via classify_google_error) is unchanged and still required (the stub's types don't exist at runtime). This task now explicitly depends on TASK-70 in addition to TASK-22.3.

TARGET SHAPE (decisions/outbound-clients.md + sdk-typing.md item 3):
1. Factory: a get_google_service(...) (retain/trim the existing one) that builds the Admin Directory Resource with cache_discovery=False, static_discovery=True, service-account + delegated subject + scopes, and RAISES (no OperationResult, no retry loop, no docstring scraping) - AND annotates its return with the google-api-python-client-stubs type (`AdminDirectoryResource` from `googleapiclient._apis.admin_directory_v1`, imported under `if TYPE_CHECKING:`; explicit annotation is required per the stub's own performance guidance, not just inferred, since `build()` has a separate overload per service+version). SDK-native retry is request.execute(num_retries=...) where needed.
2. classify_google_error(exc) -> (OperationStatus, error_code, retry_after): map EXPECTED HttpError families (404 -> NOT_FOUND; 403 -> UNAUTHORIZED; 429/5xx -> TRANSIENT_ERROR honoring Retry-After) plus the get_user/get_member/get_group "not found" non-critical cases the current _handle_final_error treats as warnings; unmapped exceptions PROPAGATE. Extract from google_service._handle_final_error.
3. A Google Directory adapter (the boundary) that, for each of the 11 operations, calls the Resource directly (e.g. service.users().get(userKey=...).execute(), service.members().list(...).execute() with the SDK's own list_next pagination) inside try/except+classify_google_error, and translates each dict response into a typed domain dataclass (or the existing normalized shape the provider already returns) - OUTCOMES IDENTICAL to today. Add a health_check returning OperationResult with parity to the deprecated one (AC#2).
4. Rework factory.py so GoogleDirectoryProvider no longer receives a GoogleWorkspaceClients facade. Do NOT touch gmail_next or delete google_service_next/google_directory_next here (dispatcher deletion is TASK-23); this slice just stops the DIRECTORY path from using them and deletes the docstring-scraper path it owns.

STEPS:
1. Add/trim the factory + classify_google_error in integrations/google_workspace (place beside the canonical google_directory module; keep google_service_next untouched for TASK-23). Annotate the factory's return with the stub-provided `AdminDirectoryResource` type (requires TASK-70's google-api-python-client-stubs dev dependency to already be installed). Unit tests under tests/unit/integrations/google_workspace/ (classify families incl. non-critical not-found; factory builds with cache_discovery=False/static_discovery=True; mypy resolves the annotated return type).
2. Rework the directory adapter/provider surface: convert the 11 calls to direct Resource calls + try/except+classify + domain-dataclass translation; implement health_check parity; own pagination via the SDK list_next idiom (not the dispatcher's paginate=True).
3. Rework infrastructure/directory/factory.py + google.py: drop GoogleWorkspaceClients; resolve the Resource via the factory; keep the provider constructor injectable (tests pass a fake Resource/adapter).
4. Keep tests/unit/infrastructure/directory assertions unchanged; update mock targets (patch the Resource/adapter, not the facade). Relocate touched google_workspace vendor tests into tests/unit.

AC-TO-STEP: AC#1 -> Steps 1-3 (no infrastructure.clients.google_workspace import; direct Resource + classify; factory return annotated with the stub type; no dispatcher/scraper on the directory path - grep get_google_api_command_parameters unused by directory). AC#2 -> Step 2 (health_check parity). AC#3 -> Steps 1,4 (classify coverage; _next left for TASK-23; test locations). DoD#1 -> full suite + ruff/mypy + PR citing the three records.

TEST MATRIX: happy (each of 11 provider ops returns the same OperationResult/payload as today); pagination (list_members/list_users/list_groups aggregate via list_next identically); not-found (get_user/get_group 404 -> NOT_FOUND, non-critical warn preserved); health_check parity; classify (HttpError families -> status/error_code/retry_after honoring Retry-After; unmapped propagates); typing (mypy resolves the factory's annotated Resource return and at least the users()/groups()/members() method chains with no `Any` leakage). Commands: cd app && uv run pytest tests/unit/infrastructure/directory tests/unit/integrations/google_workspace -v; then tests --ignore=tests/smoke; then ruff check . and mypy.

BLAST RADIUS / ROLLBACK: contained to the directory provider/adapter + factory + a Google classify/factory in integrations; the DirectoryService Protocol and other consumers are untouched. Single git revert restores the facade-backed provider. gmail_next / google_service_next are NOT deleted here.

SIZE GATE: one provider/adapter surface + factory + classify + tests. Single vendor surface, one reviewable PR. If the 11-call conversion + translation exceeds the gate, split by operation group (users / groups / members) into two PRs under this slice.

DOUBTS (verify at impl): (a) whether the existing get_google_service already sets static_discovery/cache_discovery correctly (google_service.py uses cache_discovery=False; confirm static_discovery default); (b) exact domain shape the provider returns today for each op (preserve it - the translation target is the provider's current normalized output, not a brand-new dataclass unless one already exists); (c) num_retries usage - only where the deprecated path retried (429/5xx), to keep behavior parity without a hand-rolled loop; (d) confirm TASK-70 has landed google-api-python-client-stubs and that `googleapiclient._apis.admin_directory_v1.AdminDirectoryResource` (or the stub's actual generated name - verify via reveal_type, the exact name may differ) resolves in mypy before relying on the annotation in Step 1.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-31 17:06
---
RESEQUENCED per decisions/sdk-typing.md (2026-07-31). The Google directory path is the deepest anti-pattern: execute_google_api_call walks the discovery tree by string and get_google_api_command_parameters SCRAPES method docstrings to validate params. Original plan wired the provider onto google_directory_next (that dispatcher) and deferred rename/contract to TASK-23/25. New plan migrates ONCE, directly onto a factory-built Resource the adapter calls directly, deleting the dispatcher+scraper path for the directory surface and typing at the adapter via domain dataclasses (the discovery Resource is untyped by design - google-api-python-client is maintenance-mode; see sdk-typing.md item 3).

AC CHANGES (human review at task-breakdown checkpoint): AC#1 retargeted from "backed by google_directory_next" to "adapter calls the discovery Resource directly + classify_google_error; no dispatcher/docstring-scraper on the directory path". AC#3 retargeted from "relocate google_directory_next/google_service_next tests" to "classify_google_error coverage; those _next modules left for TASK-23 deletion". AC#2 (health_check parity) unchanged. DoD#1 gains decisions/sdk-typing.md.
---

created: 2026-07-31 17:50
---
RESEQUENCED (2026-07-31, second pass) after decisions/sdk-typing.md's Google-stub revision (TASK-70 now also delivers google-api-python-client-stubs, not just types-boto3). This supersedes this task's "TARGET SHAPE step 1" factory description below: the factory does not just build a RAISING Resource - it also ANNOTATES that Resource's return type using the stub-provided type (e.g. AdminDirectoryResource from googleapiclient._apis.admin_directory_v1, imported under TYPE_CHECKING), giving the adapter's 11 direct Resource calls (service.users().get(...), service.groups().list(...), etc.) real IDE completion and mypy checking - not just the translated dataclass at the far end. This was previously believed impossible (google-api-python-client's discovery Resource is dynamic by design) until the stub package was found during planning; see decisions/sdk-typing.md's "Revised finding" paragraph and item 3.

Practical effect on this task's plan: STEP 1 ("Add/trim the factory + classify_google_error") gains one clause - the factory's get_google_service(...)-equivalent must declare its return type explicitly (`service: AdminDirectoryResource = build("admin", "directory_v1", ...)`), not just call build() untyped. STEP 2's 11 direct Resource calls are typed as a consequence, with zero extra adapter-side work. AC#1 and the task's dependency list were updated accordingly (this task now explicitly depends on TASK-70 in addition to TASK-22.3, since TASK-70 is the task that adds google-api-python-client-stubs as a dev dependency - previously an implicit transitive dependency via 22.3->22.2->70, now made explicit since TASK-70's Google half is a distinct deliverable this task directly consumes).
---
<!-- COMMENTS:END -->
