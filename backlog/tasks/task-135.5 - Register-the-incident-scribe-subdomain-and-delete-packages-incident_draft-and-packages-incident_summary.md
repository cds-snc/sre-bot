---
id: TASK-135.5
title: >-
  Register the incident scribe subdomain and delete packages/incident_draft and
  packages/incident_summary
status: Done
assignee: []
created_date: '2026-10-02 18:00'
updated_date: '2026-10-08 15:44'
labels:
  - plugin-architecture
  - features
  - slack
milestone: m-7
dependencies:
  - TASK-135.4
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - decisions/incident-management.md
parent_task_id: TASK-135
priority: medium
ordinal: 315000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 of TASK-135 (contract), split out of TASK-135.4 on 2026-10-02 (human) to keep each PR reviewable: TASK-135.4 adds packages/incident/scribe/ unregistered, and this slice makes it the registered home of both commands and deletes the two top-level packages.

THIS SLICE
- packages/incident/scribe/__init__.py gains the one pair of hookimpls: register_slack_commands (both commands) and register_i18n_resources (the shared locales directory).
- packages/incident_draft and packages/incident_summary are deleted with their unit tests (the moved copies landed in TASK-135.4). Every remaining importer, mock patch string and import-linter entry is rewritten in the same PR; no re-export shim.
- The six import-linter ignore entries naming the two packages and the two temporary feature-independence entries added by TASK-135.2 and TASK-135.3 are removed; both packages leave the feature-independence modules list.
- No behaviour change: command names, arguments, replies, i18n domains and keys, settings environment variable names and log event names are unchanged.

Whether IncidentDocumentStore and IncidentReportLinkLookup belong in core/ is decided by the TASK-97 packet (TASK-38.2) and is not changed here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 /sre incident draft and /sre incident summarize are registered by one pair of hookimpls in packages/incident/scribe; the subdomain imports packages.incident.core only through core/api.py
- [x] #2 packages/incident_draft and packages/incident_summary no longer exist; rg -n 'incident_draft|incident_summary' over app/ finds no package path or import, and every hit is classified in the notes
- [x] #3 The two temporary feature-independence ignore entries and the six entries naming the two packages are removed; no import-linter ignore entry is added by this slice
- [x] #4 No function body changes in packages/incident/scribe beyond its __init__.py; the old unit tests are deleted and one registration test is added under tests/unit/packages/incident/scribe/
- [x] #5 Command names, arguments and replies are unchanged: the legacy_surface suite is green with no assertion change
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; import-linter ignore entries only shrank against main at the start of TASK-135
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Split (human, 2026-10-02): the plan below was approved for TASK-135.4 as one PR. After implementation the human split it in two for review size. TASK-135.4 took step 1, step 2, the copy half of step 6 and a temporary pyproject state (scribe added to the umbrella layer, four scribe ignore entries beside the six originals). This task takes step 3, step 4, the final pyproject of step 5, the deletion half of step 6, and steps 7 to 9. Step 0 was run once, before the split, and is recorded as a comment on TASK-135.4.

ORIGINAL PLAN (TASK-135.4, approved 2026-10-02)

Subdomain name: scribe (TASK-97, decisions/incident-management.md, 2026-10-02). Unblocked.

Size: a mechanical move of two packages (16 production modules, 4 locale files, 2 READMEs) into one, plus app/pyproject.toml. Outside pure moves and import-path rewrites the hand-written change is about 150 production LOC (one merged __init__.py, name-collision renames, pyproject). Over the file count, but doc-2 requires a move to rewrite every importer in the same PR with no re-export shim, so it cannot be cut further. No behaviour change.

STEPS
0. Re-verify before starting, because TASK-25.10, TASK-134 and TASK-110 may have merged since this plan was written (2026-10-02 at c8de7643): re-run rg -n 'incident_draft|incident_summary' over the repo outside backlog/, re-read both service modules' imports, and check pyproject for entry points. Record the differences as a comment on this task before editing.
1. Create app/packages/incident/scribe/ and move, keeping git history as renames where a file moves whole:
   - incident_draft/domain.py -> domain.py
   - incident_draft/adapters/google_docs.py and adapters/slack.py (SlackIncidentReportLinkLookup) -> adapters/
   - incident_draft/providers.py -> providers.py
   - incident_draft/locales/* and incident_summary/locales/* -> locales/ (file names incident_draft.<locale>.yml and incident_summary.<locale>.yml unchanged)
   - both settings.py -> one settings.py holding IncidentDraftSettings and IncidentSummarySettings with their INCIDENT_DRAFT__* and INCIDENT_SUMMARY__* aliases unchanged; drop the deprecated 'from __future__ import annotations' line from both (:9)
   - both service.py -> one service.py (human decision 2026-10-02): draft's module with summary's functions appended
   - both platforms/slack.py -> one platforms/slack.py with both handlers and both registrations
   - both README.md -> one README.md
2. Resolve the name collisions the merge creates, and nothing else:
   - platforms/slack.py: _DOMAIN (two values) -> _DRAFT_DOMAIN and _SUMMARY_DOMAIN; register_commands (two) -> one function making both registrar.register_command calls; _error_response (two, different messages) -> _draft_error_response and _summary_error_response; the --limit coercion helper is kept once.
   - service.py: EMPTY_HISTORY_CODE (same value in both) kept once; logger kept once; the two limit-resolution helpers stay separate functions over their own settings, renamed by use case, so no logic is unified in a move PR.
3. app/packages/incident/scribe/__init__.py: one register_slack_commands hookimpl calling the merged register_commands, and one register_i18n_resources hookimpl registering two I18nResourceSpec values (domains incident_draft and incident_summary unchanged, owner 'packages.incident.scribe', the shared locales path). No re-exports beyond what tests import.
4. Delete app/packages/incident_draft/ and app/packages/incident_summary/.
5. app/pyproject.toml:
   - no-host-imports ignore_imports (:289-292): four entries become three under the new paths (google_docs -> infrastructure.configuration.integrations.google, google_docs -> infrastructure.drive, platforms.slack -> infrastructure.i18n);
   - integrations-via-adapters ignore_imports (:341-342): two entries become one for the merged service, or none if TASK-25.10 has already moved the summarizer behind the capability;
   - feature-independence: remove packages.incident_draft and packages.incident_summary from modules (:354-355) and remove the two temporary ignore entries added by TASK-135.2 and TASK-135.3;
   - incident-umbrella layers: first layer becomes "documents | drive | meet | scheduling | scribe".
6. Tests move with their modules to app/tests/unit/packages/incident/scribe/, files renamed to the test_incident_scribe_<entity>_<action>.py pattern, with every import and patch string rewritten. Known patch strings on 2026-10-02 (re-grep at step 0): packages.incident_draft.adapters.google_docs.get_google_resources_config, ...google_docs.google_workspace_client, packages.incident_draft.platforms.slack.handle_draft_command, packages.incident_summary.platforms.slack.handle_summarize_command (2), plus those TASK-135.2 and TASK-135.3 introduce on the service and providers modules. Test bodies and assertions are not edited.
7. app/tests/integration/legacy_surface/: conftest.py imports the one subdomain module in place of the two packages (:30-31, :52-53) and patches get_incident_transcript_reader once, on the merged service module, and get_incident_report_link_lookup on the merged providers module; test_slack_command_registration_surface.py imports (:21-24) and the four setattr targets point at the merged modules, with no assert line changed; INVENTORY.md:115-116 paths updated.
8. Records and sibling tasks:
   - decisions/feature-packages.md: Context (:13, :14, :17) and 'Tolerated until then' (:117, :119) no longer list the two packages; add a dated Changes line.
   - decisions/dependency-injection.md:16, configuration.md:16, interaction-toolkits.md:45 and i18n.md:17 name the packages by path: update the names.
   - Through the backlog CLI, bring the paths in TASK-124.5, TASK-25.10 and TASK-134 up to date if they are still open.
9. Gates from app/: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (0 errors in touched files) ; uv run lint-imports ; uv run pytest tests --ignore=tests/smoke. Then rg -n 'incident_draft|incident_summary' app/ and classify every hit (expect only i18n domains and keys, settings aliases and class names, log event names, locale file names), and rg -n 'Port\b|_port\b|_PORT\b|\bport\b' app/packages/incident app/tests/unit/packages/incident app/tests/integration/legacy_surface (expect nothing).

AC MAP
- #1 -> steps 1, 2, 3; the moved handler and registration tests; lint-imports (umbrella contract).
- #2 -> steps 4, 9 (first rg, hits classified in notes).
- #3 -> step 5; lint-imports output and the pyproject diff.
- #4 -> steps 1, 2, 6; review of the diff with moved-line detection; collision renames listed in step 2 are the only edits to function bodies.
- #5 -> step 7; pytest tests/integration/legacy_surface recorded before and after.
- #6 -> steps 5, 9; ignore-entry count before and after against the count at c8de7643 (6 entries naming the two packages).

TEST MATRIX
- No new behaviour, so no new behaviour tests. The moved unit suites (about 250 tests on 2026-10-02) and the four legacy_surface incident tests must pass unchanged in body.
- One addition: the registration test asserts the single package registers both commands under sre.incident and both i18n domains.

ASSUMPTIONS AND HOW TO VERIFY
- The i18n loader reads <domain>.<locale>.yml files (infrastructure/i18n/loader.py:53), so two domains can share one locales directory. Verify with the two locale parity tests and by rendering one translated reply per command in the legacy_surface suite.
- Plugin discovery walks packages/ recursively (server/plugins/base.py:46), as it does for packages/access/*, so the nested subdomain registers without a host change. If TASK-110 has landed, the two entry points become one named incident.scribe (umbrella rule 6).
- Nothing outside app/ and decisions/ names the two packages (rg over the repo on 2026-10-02: no hit in app/bin, terraform, workflows or the Makefile).
- The subdomain name, and whether IncidentDocumentStore or IncidentReportLinkLookup move to core/, come from the TASK-97 packet; if the packet moves either, that is its own task, not this move.

BLAST RADIUS AND ROLLBACK
- Both commands. The risk is a missed importer or patch string, which fails at import time in CI, not in production. Settings variable names, i18n keys and replies are unchanged, so there is no deployment step.
- A single git revert restores both packages.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented as layer 5 of Stack G on stack-g/task-135.5-incident-scribe-switch, committed as 5c5bcd37 on top of 6178aa7e (TASK-135.4). Status stays In Progress; a human moves it to Done.

WHAT CHANGED (48 files, +130 / -7734)
- app/packages/incident/scribe/__init__.py: one register_slack_commands hookimpl calling the merged register_commands and one register_i18n_resources hookimpl.
- app/packages/incident_draft/, app/packages/incident_summary/ and their two unit test directories are deleted. No re-export shim.
- app/pyproject.toml: the six ignore entries naming the two packages and both temporary feature-independence entries are removed; the two packages leave the feature-independence modules list. Against main at the start of TASK-135 the ignore list went from 6 entries naming the two packages to 4 naming the subdomain.
- legacy_surface: conftest registers the one hookimpl module (seven modules, was eight) and patches get_incident_transcript_reader once on the merged service and get_incident_report_link_lookup on the merged providers; the registration test's imports and four setattr targets point at the merged service, no assert line changed; INVENTORY.md lines 115-116 updated.
- New tests/unit/packages/incident/scribe/test_incident_scribe_plugin_registration.py (3 tests): both commands registered under sre.incident, one i18n registration owned by the subdomain, and both i18n domains loadable from the registered path in en-US and fr-FR.
- Records: decisions/feature-packages.md (Context, Tolerated list, a dated Changes line), dependency-injection.md, configuration.md, interaction-toolkits.md, i18n.md and outbound-clients.md name the subdomain. TASK-25.10 and TASK-134 carry the new paths.

DEVIATIONS FROM THE ORIGINAL PLAN, FOR REVIEW
1. One I18nResourceSpec, not two (plan step 3). The i18n registry deduplicates on path and would drop a second spec for the shared locales directory with a warning at every boot; the loader reads every <domain>.<locale>.yml under the path, so one registration loads both catalogues. The spec's domain field (only logged) is 'incident_scribe'; the i18n domains in the keys, incident_draft and incident_summary, are unchanged.
2. decisions/outbound-clients.md:66 named incident_draft and was not in the plan's list; it is updated with the others.

AC #2 CLASSIFICATION: rg -n 'incident_draft|incident_summary' app/ -> 88 hits, none a package path or import
- i18n domain names (the two _DOMAIN constants, locale catalogue root keys, locale test lookups, README and docstring mentions of the two domains), INCIDENT_DRAFT__* / INCIDENT_SUMMARY__* aliases, log event names, locale file names;
- kept because renaming them is not part of a move: the settings getters get_incident_draft_settings and get_incident_summary_settings; the Google Docs named-range prefix 'incident_draft::' (an identifier written into documents) and the log context value command="incident_draft"; test function names (legacy_surface test_incident_draft_*, INVENTORY's -k incident_draft, and two legacy modules/incident tests).

GATES (from app/ at 5c5bcd37, 2026-10-02)
- uv run ruff check . -> All checks passed!
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 65 errors in 22 files (baseline count); 0 in packages/incident/scribe, its tests or legacy_surface.
- uv run lint-imports -> Contracts: 9 kept, 0 broken.
- uv run pytest tests/integration/legacy_surface -> 17 passed, no assertion changed.
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3678 passed. The 6 are the known TASK-90 order leaks (test_webhooks_aws_sns.py x3, directory/test_google.py x3).
- rg -n 'Port\b|_port\b|_PORT\b|\bport\b' app/packages/incident app/tests/unit/packages/incident app/tests/integration/legacy_surface -> no match.
- Plugin discovery checked for real: auto_discover_plugins over packages registers packages.incident.scribe and the i18n registry holds one spec for it.

NOT CHANGED, WORTH KNOWING
- app/packages/incident/__init__.py still says the umbrella registers no plugin hooks. That is true of the umbrella module itself, but the scribe subdomain under it now does.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 18:01
---
2026-10-02 (human, in session): TASK-135.4 as implemented was too large for one PR, so it was split after implementation into TASK-135.4 (add packages/incident/scribe, unregistered; 6178aa7e) and this task (register it and delete the two packages; 5c5bcd37). The human made the two commits. The plan here is the plan approved for TASK-135.4, with a note saying which steps each task took.
---
<!-- COMMENTS:END -->
