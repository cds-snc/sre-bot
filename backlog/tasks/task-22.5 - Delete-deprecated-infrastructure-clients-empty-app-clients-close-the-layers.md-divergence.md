---
id: TASK-22.5
title: >-
  Delete deprecated infrastructure/clients + empty app/clients; close the
  layers.md divergence
status: Done
assignee:
  - '@me'
created_date: '2026-07-29 21:11'
updated_date: '2026-08-31 15:44'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.4
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - app/tests/unit/infrastructure/services/test_narrow_slice_providers.py
parent_task_id: TASK-22
priority: high
ordinal: 108000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 (final) of TASK-22 (parent). After slices 22.1-22.4 have migrated all six production consumers, remove the deprecated trees and close the tolerated divergence.

Steps:
1. Verify zero production consumers remain: grep -rn 'infrastructure.clients' app --include='*.py' returns only deleted-in-this-PR test files. Run make audit-client-usage-matrix and confirm zero infrastructure/clients consumers.
2. Delete app/infrastructure/clients/ entirely (aws, google_workspace, maxmind = 72 files) and the empty app/clients/ directory.
3. Delete the deprecated-tree tests under app/tests/unit/infrastructure/clients/ (already unit-located).
4. Repoint app/tests/unit/infrastructure/services/test_narrow_slice_providers.py:13 (currently imports infrastructure.clients.maxmind.client.MaxMindClient) onto the ported integrations/maxmind client from slice 22.1, or delete that specific narrow-slice assertion if it no longer applies.
5. If TASK-19's freeze-check baseline exists by now, empty the deprecated-import baseline; if TASK-19 has not landed, note it (baseline is a no-op until then).
6. Update decisions/layers.md Migration section: remove 'infrastructure/clients/ consumers' from the tolerated-divergences list; confirm the Checks item 'No directory named clients/ exists under app/' now passes.

Do NOT resolve _next twins (TASK-23) or apply the raise/classify contract (TASK-25) here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/infrastructure/clients/ and app/clients/ no longer exist; decisions/layers.md check 'no directory named clients/ under app/' passes
- [x] #2 make audit-client-usage-matrix reports zero consumers of infrastructure/clients/
- [x] #3 test_narrow_slice_providers.py no longer imports the deleted infrastructure.clients.maxmind; deprecated-tree tests under tests/unit/infrastructure/clients/ removed
- [x] #4 decisions/layers.md Migration section no longer lists infrastructure/clients/ consumers as a tolerated divergence; full test suite green
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Behavior-neutral overall; deprecated-import baseline emptied if TASK-19 landed; PR references decisions/layers.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDED 2026-08-31 (TASK-22.1-22.4 all Done; TASK-19 Done so the freeze-check baseline exists).

VERIFIED CURRENT STATE (re-derived from source, not the task's own stale prose):
- Zero production consumers of `infrastructure.clients` remain anywhere in `app/` (fresh
  repo-wide grep). The 6 baseline production entries (infrastructure/directory/factory.py,
  infrastructure/directory/google.py, infrastructure/storage/service.py,
  packages/access/sync/adapters/aws_identity_center.py, packages/access/sync/providers.py,
  packages/geolocate/service.py) are all migrated already, confirmed by running
  `python3 bin/check_deprecated_infra_client_imports.py` directly: it prints all 6 as
  "INFO: baseline entries no longer importing ... (safe to remove)" and reports
  "24 baselined consumer(s) remain" - all 24 are test files.
- `app/infrastructure/clients/` currently holds 24 real .py files (aws:12,
  google_workspace:10, maxmind:2), NOT 72 as the task's Description states (stale count from
  before slices ported logic out incrementally) - correct the actual deletion inventory to 24,
  not 72.
- `app/clients/` does NOT exist at all (confirmed via file_search/find) - it was already fully
  removed at some earlier point, not merely "empty" as the task text assumes. AC#1's `app/clients/`
  clause is already satisfied; no action needed for it, just verify-and-confirm in the PR.
- `app/tests/unit/infrastructure/clients/` holds exactly 30 .py source files (aws: 18 incl.
  conftest.py, google_workspace: 11 incl. conftest.py/__init__.py, plus top-level
  test_maxmind.py). All 30 exercise the deprecated tree directly or via its fixtures
  (confirmed per-file: the 5 files NOT listed in the baseline txt - test_dynamodb.py,
  test_factory.py, test_identity_store_unit.py, test_organizations_unit.py,
  test_sso_admin_unit.py - still depend on it, either via `importlib.import_module(
  "infrastructure.clients.aws...")` string calls the AST-based baseline checker can't see,
  or via the `aws_factory` fixture in aws/conftest.py which does a static import). All 30 must
  be deleted alongside the source tree; none can be salvaged.
- `app/tests/unit/packages/geolocate/test_service_import_boundaries.py` and
  `app/tests/unit/bin/test_check_deprecated_infra_client_imports.py` are NOT deprecated-tree
  tests (the former asserts the boundary is already clean via AST parse of service.py; the
  latter tests the checker script itself using monkeypatched tmp_path baselines, never the
  real baseline file) - leave both untouched.
- `integrations/maxmind/client.py::MaxMindClient.__init__(self, maxmind_settings: MaxMindSettings)`
  (shipped by TASK-22.1) has an IDENTICAL constructor signature to the deprecated
  `infrastructure/clients/maxmind/client.py::MaxMindClient` - the AC#3 repoint is a pure
  one-line import-path swap in test_narrow_slice_providers.py, zero assertion changes.

CRITICAL FINDING (verified by direct execution, not inspection - this would otherwise silently
break AC#2's own verification command): `app/bin/generate_client_usage_matrix.sh` runs under
`set -euo pipefail` and its first real command is
`find app/infrastructure/clients app/integrations -type f -name '*.py' ... | sort > ...`.
Confirmed via a live repro (`find <missing-path> app/integrations ...`) that `find` exits 1
when one of several path arguments doesn't exist (even though it still lists the ones that do),
and under `set -e` that nonzero exit ABORTS the script immediately - it does not run to
completion and print a "zero consumers" report, it crashes with
"find: 'app/infrastructure/clients': No such file or directory" and a nonzero exit. Once this
task deletes `app/infrastructure/clients/`, running `make audit-client-usage-matrix` as-is would
therefore FAIL, not pass, making AC#2 unverifiable unless the script itself is fixed in this same
PR. Required fix: drop `app/infrastructure/clients` from that `find` invocation (scan
`app/integrations` only - the tree that still needs matrix-tracking, e.g. for TASK-23's `_next`
twin work). The script's `external_usage_file` loop also has an inert
`grep -v '^app/infrastructure/clients/'` exclusion line that becomes permanently-vacuous after
this task; harmless to leave, optional to remove (implementer's choice, not required for AC#2).

STEPS (single PR, pure-subtractive + two guardrail-artifact fixes + decision-record bookkeeping):

1. Delete `app/infrastructure/clients/` entirely (24 files: aws/{config,cost_explorer,dynamodb,
   executor,facade,guard_duty,health,identity_store,__init__,organizations,session_provider,
   sso_admin}.py; google_workspace/{batch_executor,directory,docs,drive,executor,facade,gmail,
   __init__,session_provider,sheets}.py; maxmind/{client,__init__}.py). Do not touch
   `app/infrastructure/directory/`, `app/infrastructure/storage/`, or any `packages/` file - all
   already migrated off this tree by 22.1-22.4.
2. Confirm `app/clients/` still does not exist (no-op; already gone).
3. Delete `app/tests/unit/infrastructure/clients/` entirely (all 30 files listed above, including
   both conftest.py files and the google_workspace `__init__.py`).
4. Edit `app/tests/unit/infrastructure/services/test_narrow_slice_providers.py`: change
   `from infrastructure.clients.maxmind.client import MaxMindClient` to
   `from integrations.maxmind.client import MaxMindClient`. No other change - the constructor
   contract and all assertions in `TestMaxMindClientNarrowSlice` are identical on the new import.
5. Fix `app/bin/generate_client_usage_matrix.sh`: remove `app/infrastructure/clients` from the
   `find` target on the `all_modules_file` line so the script does not crash post-deletion (see
   CRITICAL FINDING above). This is required for AC#2 to be verifiable at all, not cosmetic.
6. Empty `app/bin/baselines/deprecated_infra_client_imports.txt`: remove all consumer path
   entries (both the 6 stale production lines and the 24 test lines), keep the explanatory
   header comment block only. After this, `find_current_consumers()` returns an empty set
   (the deprecated tree and all its consumers are gone) and `load_baseline()` also returns an
   empty set, so `check-deprecated-client-imports` passes trivially ("0 baselined consumer(s)
   remain") - matches decisions/migration.md's own "Done means: ... the deprecated-client
   baseline empty" vocabulary exactly. Do NOT delete the checker script, its Makefile targets, or
   its CI step in this task - the script's own docstring ("delete this script and its baseline
   once baseline is empty") describes a FUTURE full-retirement action that is a separate,
   larger decision (touches CI wiring + Makefile + decisions/toolchain.md's guardrail entry) and
   is out of this task's literal Step 5 wording ("empty the baseline"); flagged below as an open
   question for the human reviewer rather than decided unilaterally here.
7. Update `decisions/layers.md`:
   - Migration section (required by AC#4): remove "`infrastructure/clients/` consumers (held by
     the deprecated-import guardrail baseline)" from the "Tolerated divergences until closed"
     list, leaving `_next.py` twins, Slack content in `integrations/slack/`, the upward
     integrations->infrastructure imports, and the non-tier top-level directories.
   - Context "Current state" sentence (line 14, NOT explicitly named by the task's Step 6, but
     left stale/directly contradicted by this same PR if untouched - flagged as a recommended
     same-file addition): reword away from "three generations... `app/clients/` empty,
     `app/infrastructure/clients/` deprecated, `app/integrations/` current with `_next.py`
     twins" to reflect that only `app/integrations/` remains, still carrying the `_next.py`
     twin generation internally pending TASK-23.
8. Update `decisions/outbound-clients.md` Migration section (also NOT explicitly named by Step 6,
   same "sibling stale bookkeeping" category as item 7's Context-line fix - flagged as an open
   question, not silently done): remove "the seven baselined deprecated-client consumers" from
   its "Tolerated until closed" list (the count was already stale - 6, not 7 - independent of
   this task), leaving only "shield-shaped AWS client" (closed later by TASK-25.5).
9. Run `make check-deprecated-client-imports` (expect "OK: no net-new ... (0 baselined
   consumer(s) remain)"), `make audit-client-usage-matrix` (expect it to complete and show zero
   `infrastructure/clients` rows), and the full test suite (`cd app && uv run pytest tests
   --ignore=tests/smoke`) to confirm green with the 30+ deleted test files gone from collection
   and no import errors from the narrow-slice repoint.

AC-TO-STEP TRACEABILITY:
- AC#1 (app/infrastructure/clients/ and app/clients/ gone; layers.md check passes) <- Steps 1, 2, 7.
- AC#2 (audit-client-usage-matrix reports zero consumers) <- Steps 1, 5, 9.
- AC#3 (test_narrow_slice_providers.py repointed; deprecated-tree tests removed) <- Steps 3, 4.
- AC#4 (layers.md Migration section updated; full suite green) <- Steps 7, 9.
- DoD#1 (behavior-neutral; baseline emptied; PR references layers.md) <- Steps 1-9 (pure deletion
  + two guardrail-artifact fixes + doc bookkeeping, no runtime behavior change).

BLAST RADIUS / ROLLBACK: entirely subtractive (84 dead files: 24 source + 30 test + nothing else
touches runtime code) plus 2 one-line/small script-and-data fixes and 2 decision-record edits.
Zero production consumers exist today (verified above), so there is no runtime behavior change
possible from deleting the tree itself. Single `git revert` fully restores prior state. No
terraform/CI-workflow changes (the CI step keeps running the same Makefile target, only its
input data file's content changes).

SIZE-GATE VERDICT: FITS ONE PR. 84 file deletions with zero surviving logic changes, 2 tiny
guardrail-tooling fixes needed to keep the ACs' own verification commands from crashing, and a
handful of decision-record lines - same reasoning as TASK-5.4.2's "deletion-heavy contract slices
don't trip the size gate the way net-new-logic slices do" precedent. No decomposition needed.

OPEN QUESTIONS FOR HUMAN REVIEWER (not decided unilaterally):
(a) Should this PR also fully retire `check_deprecated_infra_client_imports.py` +
    `app/bin/baselines/` + the `check-deprecated-client-imports` Makefile target + its CI step in
    ci_code.yml, now that the baseline is permanently empty (source tree gone forever) - or keep
    the now-always-passing guardrail live as a defensive backstop until a future explicit
    retirement decision? Step 6 above chose "keep it, just empty the data file" as the more
    literal reading of the task's own Step 5 wording ("empty the baseline") and decisions/
    migration.md's "Done means: ... baseline empty" phrasing (not "script deleted").
(b) Should the decisions/layers.md Context-line reword (Step 7's second bullet) and the
    decisions/outbound-clients.md Migration-line edit (Step 8) be included in this PR, or held
    back as a separate docs-only follow-up? Both are same-file/low-risk and directly resolve
    facts this exact PR changes, but neither is literally named by the task's own Step 6 text
    (which only names layers.md's "Migration section").
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Removed app/infrastructure/clients/ and its 30 dedicated unit tests; app/clients/ was already absent. Repointed the narrow-slice MaxMind provider test to integrations.maxmind.client. Updated the usage-matrix source scan, emptied the deprecated-import baseline, and removed the closed infrastructure/clients migration divergence from decisions/layers.md. Evidence: focused retirement and provider tests passed (9 passed); make check-deprecated-client-imports passed with 0 baselined consumers; make audit-client-usage-matrix completed; ruff check passed; full non-smoke suite manually verified green. All acceptance criteria are verified. DoD remains for human verification; task left In Progress.
<!-- SECTION:NOTES:END -->
