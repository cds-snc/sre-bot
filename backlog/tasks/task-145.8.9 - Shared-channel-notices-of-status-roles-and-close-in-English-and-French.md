---
id: TASK-145.8.9
title: Shared-channel notices of status, roles and close in English and French
status: To Do
assignee: []
created_date: '2026-11-17T20:55:00Z'
updated_date: '2026-11-25T19:10:00Z'
labels:
  - incident
  - i18n
  - slack
dependencies:
  - TASK-145.8.3
  - TASK-193
references:
  - decisions/i18n.md
parent_task_id: TASK-145.8
priority: low
ordinal: 528000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
i18n.md 2026-11-17 (TASK-145.8.3 OQ3, human): a message posted to a shared conversation is in English and French, each line from its own catalogue; private replies follow the actor's locale. The update modal's field notice (TASK-145.8.3, N14) is the first consumer. This task aligns the existing single-locale channel notices of the rebuilt response surfaces: change_status's notice (TASK-145.8.4, approved AC #6 used the invoker's locale), the roles announcement (TASK-145.8.5.1) and /sre incident close's archived notice (TASK-145.8.5.3; the archive button is already bilingual). Each is a named change of kind (b) (migration.md step 4) with its pin assertion edited citing i18n.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 change_status's channel notice, the roles announcement and /sre incident close's archived notice are posted in English and French from their catalogues (one line per language, no second copy of a string)
- [ ] #2 Private replies of the same surfaces stay in the actor's locale
- [ ] #3 Each changed pin assertion cites i18n.md 2026-11-17 as a named change of kind (b), listed in the PR body
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SUPERSEDED 2026-11-25 (human D1-D6, see comments): re-plan after TASK-193. Previous proposal kept below as evidence.

Goal: the three single-locale notices still posted to an incident channel by rebuilt response surfaces follow i18n.md:31 (2026-11-17): a post to a shared conversation is in English then French, one line per language from its own catalogue; private replies stay in the actor's locale. No catalogue string changes (both languages already exist, parity-checked); only which locales are rendered.

Current state (call sites)
- Status: entrypoints/slack.py:143 notice = _t("notice", locale, ...) with locale = payload.user_locale (:134); posted by service/status.py:149-156 channel_stage. Keys incident_response.status.notice (en/fr :10).
- Roles: entrypoints/slack_roles.py:161-166 announce lambda in the modal's private_metadata locale (:145); posted once per changed role by service/roles.py:137-147. Keys roles.announcement (:43) and roles.name.<role>.
- Close: entrypoints/slack_archive.py:84 locales = (payload.user_locale,) feeds _archive (:132-148), which renders status_notice (status.notice) and archived_notice (archive.notice, :56) in that one locale. The archive button already passes _NO_LOCALE (:41, bilingual, TASK-145.8.5.3).
- Already bilingual: the update modal's field notice (slack_show.py:72 _BOTH, :297-303 _notice; N14), so a status change from the modal is bilingual while /sre incident status update is not; the archive button is bilingual while /sre incident close is not. This task removes both inconsistencies.
- Two copies of the locale pair exist (slack_show.py:72 _BOTH, slack_archive.py:41 _NO_LOCALE) and upcoming tasks add more shared posts (145.9.2 stale notice, 145.10.x postmortem posts (D6), 192 reminders, 145.7.10 declare's DeclareTexts).

Steps
1. Pins first (red on main): edit the three legacy pins to the bilingual notice, each assertion with a comment citing "decisions/migration.md step 4 kind (b): i18n.md 2026-11-17, a post to a shared conversation is in English and French (TASK-145.8.9 named change)":
   - tests/integration/legacy_surface/test_incident_status_command_surface.py:138 (status notice EN -> EN+FR)
   - tests/integration/legacy_surface/test_incident_roles_surface.py:180-181, :191 (announcement EN -> EN+FR per role)
   - tests/integration/legacy_surface/test_incident_close_command_surface.py:127-128 (status and archived notices EN -> EN+FR)
   Plus a private-reply assertion in each pin's French case where one exists, or a unit test (step 4), showing the reply stays one language.
2. Core helper (OQ1): features/incident/core/adapters/i18n.py gains OFFICIAL_LOCALES (tuple derived from infrastructure.i18n Locale, en-US first) and in_official_languages(line: Callable[[str], str]) -> str ("\n".join(line(locale) for locale in OFFICIAL_LOCALES)); re-exported by core/api.py beside translate. The adapter stays the umbrella's one import of infrastructure.i18n. The order is the Locale enum's (English first: CDS issues from Ottawa, TBS Directive 6.1.1); the docstring names TASK-118 as the owner of the configurable order (OQ2).
3. Entry points:
   - slack.py:143 notice = in_official_languages(lambda loc: _t("notice", loc, user=..., status=...)); replies keep locale.
   - slack_roles.py:161-166 announce renders both lines, the role name translated per line; replies keep locale.
   - slack_archive.py: _archive renders both notices with OFFICIAL_LOCALES and drops its locales parameter; the command path keeps (payload.user_locale,) for its refusal and stage lines only; _NO_LOCALE replaced by OFFICIAL_LOCALES.
   - slack_show.py:72 _BOTH replaced by OFFICIAL_LOCALES (mechanical, ~3 lines, named in the PR body).
4. Unit and integration tests edited to the bilingual notice, French replies kept French:
   - tests/unit/features/incident/response/test_incident_response_status_entrypoint.py:92, :105 (FR invoker: notice EN+FR, reply FR)
   - tests/integration/features/incident/response/test_incident_response_status_dispatch.py:110
   - tests/unit/features/incident/response/test_incident_response_roles_entrypoint.py:246-248, :259 (FR submitter: announcement EN+FR, ephemeral FR), :295-296 unchanged
   - tests/integration/features/incident/response/test_incident_response_roles_dispatch.py:148-149
   - tests/unit/features/incident/response/test_incident_response_archive_entrypoint.py:152-153, :164-165 (FR invoker: notices EN+FR, reply FR); button tests :59/:61 unchanged
   - new tests/unit/features/incident/core/test_incident_core_official_languages_render.py: in_official_languages renders English then French, one line each, each line from its own locale; OFFICIAL_LOCALES matches the catalogue locales (the parity gate's set).
   - Service-level tests (status_change :40, archive_service :45-46, fields_update :34) take the notice as an argument: unchanged.
5. Docs riding with the code: tests/integration/legacy_surface/INVENTORY.md rows for status (:124), roles (:125), close (:128) name the TASK-145.8.9 named change (b); features/incident/response/README.md :13, :52-57, :116-117 (channel notices English then French on every surface; replies in the invoker's locale); decisions/i18n.md (OQ5): Decision gains the order rule and the render rule; Checks extend the existing entrypoints grep to locale tuples; Migration names TASK-118 for the contract operation and the order setting; Changes line for TASK-145.8.9.

AC -> step -> test
- AC #1 -> steps 2, 3 -> pins (step 1), status/roles/archive entrypoint and dispatch tests, core helper test. "No second copy of a string": no catalogue edit; every line comes from translate per locale.
- AC #2 -> step 3 (reply locale untouched) -> the French-invoker unit tests of status, roles, close (step 4).
- AC #3 -> step 1 comments + PR body list -> the three edited pins.
- AC #4 -> gates: ruff, lint-imports (make check-import-contracts), make check-settings-key-ownership, check-package-shape, check-test-seams; mypy then pytest once each at the end.

Test matrix
- happy: EN invoker and FR invoker each get EN+FR notices (status, each role, close's two notices).
- boundary: roles with several changed roles: one bilingual post per role; close where the status notice is skipped (channel not writable) still reports the stage line in the invoker's locale.
- failure: post failure stage lines (status.channel_failed, roles.announcements_failed, archive.notice_failed) stay in the invoker's locale (existing tests, unchanged expectations).
- authorization/idempotency: unchanged (no new path).

Named changes (PR body)
- (b) /sre incident status update's channel notice in English and French (legacy: English only; TASK-145.8.4 AC #6: invoker's locale). Revert target: the squash commit.
- (b) the roles announcement in English and French (TASK-145.8.5.1: submitter's locale).
- (b) /sre incident close's status and archived notices in English and French (TASK-145.8.5.3: invoker's locale; the button already bilingual).

Size: production ~45 LOC over 6 files (core adapters/i18n.py, core/api.py, slack.py, slack_roles.py, slack_archive.py, slack_show.py); tests ~9 files; docs 3. One subsystem (incident response). Under the gate.

Domain-model gate: not applicable (no entity, port or stored shape changes; the service ports already take rendered text).

Assumptions to verify at implementation
- A1 Slack renders "\n" in a chat.postMessage text as a line break (already true for the field notice and the button notices in production since #1867/#1857).
- A2 infrastructure.i18n Locale has exactly en-US and fr-FR (models.py:11-17); the helper test pins the order.

Blast radius and rollback: the text of three channel posts in every incident (two lines instead of one). Nothing stored, no ids, no buttons. Wrong ship: a malformed line (missing key shows the key, the neutral fallback). One git revert restores the single-locale notices. No ordering constraint; no terraform, no settings.

Open questions, assessed at program scope (re-assessed 2026-11-25 on request: decisions/, doc-11, doc-15, doc-16, doc-17, prior and upcoming tasks, cited practice)

OQ1 Where the bilingual render lives.
- ADR: i18n.md Decision: the translator is a framework service, its contract in app/contracts/, implementation in app/server/; Checks: "no dict keyed by locale or language (en-US, fr-FR tables) in any entrypoints/ module" (the existing _BOTH, slack_show.py:72, and _NO_LOCALE, slack_archive.py:41, are locale tables in entrypoints, against the Check's intent). Migration tolerates features importing infrastructure/i18n directly until the contract exists. incident-management.md:48: core/ reached only through core/api.py.
- Prior: four copies of the pair: server/slack/tenant_guard.py:35 NOTICE_LOCALES, slack_archive.py:41, slack_show.py:72, legacy modules/incident/incident_conversation.py:383. TASK-145.2 put the umbrella's one translator import in core/adapters/i18n.py, re-exported by core/api.
- Upcoming: TASK-118 (doc-11 P7/C5; To Do; waits 117, 72, 109) defines the contract and repoints every importer; no AC on rendering several locales. Consumers of a bilingual render inside the incident umbrella: 145.9.2 (stale notice, ignore reply), 145.7.10 (declare's channel posts, L9b), Stack M (doc-17) M3/M4 postmortem posts (145.10 D6 "English first line", 145.10.6 AC #3 "bilingual posts"), 192 (reminders), and doc-15's 165.x posts (engagement, workstreams, audiences: no locale line in any 165.x task; i18n.md applies to them by default).
- Practice: frameworks keep one translator and render a message in another language by overriding the active locale per call (Django translation.override, https://docs.djangoproject.com/en/5.2/topics/i18n/translation/); a message in several languages is one render per locale, never a second copy of the string.
- Gap: the contract (TASK-118) does not yet offer the operation; the incident umbrella needs it now.
- Recommend: in_official_languages in core/adapters/i18n.py through core/api (one subsystem; postmortem and the coordinated subdomains reach it through core/api), replace _BOTH and _NO_LOCALE here, and add to TASK-118 an AC: the translator contract renders a line in every official language in the configured order; the incident core helper and server/slack/tenant_guard.py NOTICE_LOCALES repointed to it. Alternative A: put it in infrastructure/i18n now (platform-wide at once, but grows a module TASK-118 deletes, and repointing tenant_guard makes three subsystems). Alternative B: local tuples per entry point (two more copies against the i18n.md Check).

OQ2 Line order, and whether the language set or order is a setting.
- ADR: i18n.md says "English and French" but never the order. GAP. Prior: every bilingual surface puts English first (tenant guard, archive button, field notice; 145.10 D6 ruled "English first line" for postmortem only).
- Practice: TBS Directive on Official Languages for Communications and Services 6.1.1: when both languages are used, French comes first when the issuing office is in Quebec (https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=26164); otherwise English comes first; where requirements conflict the department's head of communications decides (FIP design standard, https://www.canada.ca/en/treasury-board-secretariat/services/government-communications/design-standard/treatment-official-languages-design-standard-fip.html). Short bilingual communications may be top-bottom with equal prominence (TBS HR guide); both versions complete, same quality, released together (rescinded 2012 electronic communications directive, https://tbs-sct.gc.ca/pol/doc-eng.aspx?id=12527).
- So the set of languages is fixed by law and by the parity gate (i18n.md:29): a constant derived from the catalogue Locale set. The order depends on the deploying office: a policy value, so a typed setting with a default (standing rule: policy values are settings unless they must never change).
- Owner: the order is platform-wide (the tenant guard's notice is a server/ surface), so the setting belongs to the host translator (TASK-118), not incident common/settings.py.
- Recommend: i18n.md Decision gains: "Lines in both official languages are one message, top-bottom, each complete from its own catalogue, in the order of the TBS Directive 6.1.1: French first where the issuing office is in Quebec, otherwise English first; the deployment sets the order in one host setting (default English first)." This task uses the Locale enum order (English first, CDS in Ottawa). TASK-118 gains the AC: "[i18n] official-language order is a typed host setting, default en-US then fr-FR, validated against the catalogue locales at boot". Alternative: add the setting now in an incident slice (wrong owner, tenant guard not covered, moved again by 118).

OQ3 TASK-189 (closing UX design session, To Do, may replace /sre incident close and the archive button). ADR: i18n.md applies to any redesigned close that posts to the channel. Not a conflict: the change is two render calls in slack_archive.py. Recommend: keep close in scope; TASK-189 gets no edit.

OQ4 Upcoming shared posts outside this task. ADR: i18n.md:31 already rules; no gap. Upcoming tasks that post to shared conversations without a locale line: 145.7.10 (declare's DeclareTexts: announcement, severity warning, next steps, on-call notice; its locale toggle sets the modal and private replies only), 165 (doc-15: engagement, workstreams, audiences). Tasks already bilingual: 145.9.2, 145.10/145.10.6 (Stack M), 192. Recommend comments, no AC changes: 145.7.10 (channel posts through core.api in_official_languages; private replies in the toggle/opener locale), 165 parent (shared posts through the same render), 145.9.2, 145.10 and 192 (use the helper; order per i18n.md). Stack M's doc-17 needs no edit (M3/M4 planning reads the task comment).

OQ5 ADR edits riding with this PR. i18n.md: Decision (OQ2 order rule; "a shared-conversation post renders through the translator's official-languages operation"), Checks (extend the entrypoints grep: no locale tuple such as ("en-US", "fr-FR") in entrypoints/; bilingual lines through the render), Migration (TASK-118 owns the contract operation and the order setting; the incident core helper is tolerated until then), Changes 2026-11-25. No incident-management.md edit.

OQ6 AC #4 reworded to the current gate list: "ruff, mypy (no new errors in touched files), make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams and pytest tests --ignore=tests/smoke pass". New AC #5: "No locale tuple remains in incident/response entrypoints; shared-channel lines render through core.api in_official_languages".

Task edits applied only after approval: 145.8.9 AC #4 reworded and AC #5 added; TASK-118 two ACs (OQ1, OQ2); comments on 145.7.10, 165, 145.9.2, 145.10, 192; doc-11 row 18.L6c.

User announcement: yes (end users see two-line notices); written at implementation per delivery-session user-announcement.md.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-17T20:57:00Z

---

2026-11-17: created from TASK-145.8.3 OQ3 (human: shared-conversation posts bilingual). Plan in full at pickup; doc-11 row 18.L6c.

---

created: 2026-11-25T18:51:00Z

---

2026-11-25 (human, OQ2 at program scope): D1-D6 approved and D3 clarified (TASK-193 description). This task now waits on TASK-193 (instance language policy, contract and multilingual message, no visible change; doc-11 row 18.L6c.0). The plan of 2026-11-25 is superseded: OQ1 and OQ2 are answered by TASK-193; re-plan after TASK-193's plan is approved: the status, roles and close notices take the multilingual message in the instance languages (the only visible change), private replies in the user's language of choice; OQ3 (close kept despite TASK-189), OQ4 (comments on 145.7.10, 165, 145.9.2, 145.10, 192, reworded to use the policy contract and the multilingual message) and OQ6 (AC #4 gate list) carry over.

---

created: 2026-11-25T19:10:00Z

---

2026-11-25 (human, TASK-193 approved): re-plan on TASK-193's contract: the status, roles and close notices are MultilingualText from LanguagePolicy.shared_languages; private replies through reply_languages (user's language of choice, primary-subtag match).

---
<!-- COMMENTS:END -->
