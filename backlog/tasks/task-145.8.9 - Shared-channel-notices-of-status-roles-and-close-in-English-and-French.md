---
id: TASK-145.8.9
title: Shared-channel notices of status, roles and close in the instance languages
status: Done
assignee: []
created_date: '2026-11-17T20:55:00Z'
updated_date: '2026-11-26T13:28:00Z'
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
- [x] #1 change_status's channel notice, the roles announcement and /sre incident close's status and archived notices are posted as MultilingualText in the conversation's shared_languages, in order, each line from its own catalogue (no second copy of a string)
- [x] #2 Private replies of the same surfaces use reply_languages for the user's locale
- [x] #3 Each changed pin assertion cites decisions/languages.md 2026-11-25 (i18n.md 2026-11-17) as a named change of kind (b), listed in the PR body
- [x] #4 ruff, mypy (no new errors in touched files), make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #5 No language tag literal and no notice_languages override remain in incident/response entrypoints; decisions/languages.md no longer tolerates the three notices
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-26 against main 876f7f7f, on the merged TASK-193 contract (#1887). The 2026-11-25 plan (a core in_official_languages helper) is superseded by TASK-193 D1-D6; its text stays in git history (task file at 87471ee9).

Goal: the three incident channel notices that still follow the invoker (decisions/languages.md Migration, "tolerated until then", line 2) go out in the instance languages, in order: a MultilingualText built from LanguagePolicy.shared_languages for the incident's conversation. Private replies of the same surfaces use LanguagePolicy.reply_languages, as show and archive already do. No catalogue string changes; only which languages are rendered and in what order.

Current state (call sites, main 876f7f7f)
- Contract: contracts/languages.py (MultilingualText.of(languages, line), plain_text(); LanguagePolicy.shared_languages(system, tenant, conversation_id), reply_languages(user_locale)). Response helpers: entrypoints/scope.py:27 language_policy(scopes), :33 shared_languages(policy, conversation). Posts: IncidentConversation.post accepts str | MultilingualText (core/api.py:246, adapters/slack.py:405-415, laid out with plain_text()).
- Status: entrypoints/slack.py:134 locale = payload.user_locale or "en-US"; :143 notice = _t("notice", locale, ...) (str) passed to change_status (service/status.py:83, already str | MultilingualText; posted by channel_stage :150). Replies _refusal/_outcome take one locale. handle_status_command :115 (help, bare pointer) also uses or "en-US".
- Roles: entrypoints/slack_roles.py:107 locale = payload.user_locale or "en-US" (modal, replies); :143 locale = metadata locale or "en-US" at submission; :161-166 announce lambda renders one locale; service/roles.py:75 and :141 announce: Callable[[IncidentRole, str], str], posted at :147.
- Close: entrypoints/slack_archive.py:81-85 handle_close_command passes notice_languages=reply_languages(payload.user_locale) to _archive (:134-162), under a marker comment naming this task; the archive button already uses shared_languages (no notice_languages). Replies already via reply_languages (_render :206).
- Default instance languages: [languages] shared = (en-US, fr-FR) (server/languages/settings.py:27, base.toml:25); no override in local/ci/production toml. CommandPayload.user_locale defaults to "en-US" (contracts/slack/models.py:143), and the Slack provider normalises it to en-US or fr-FR (integrations/slack/provider.py:915-971).

Steps (TDD: pins and tests red first, then code)
1. Pins (named change, kind (b)): edit each assertion to the two-line notice, with a comment citing "decisions/migration.md step 4 kind (b): decisions/languages.md 2026-11-25 (i18n.md 2026-11-17), a post to a shared conversation is in the instance languages, in order (TASK-145.8.9 named change)":
   - tests/integration/legacy_surface/test_incident_status_command_surface.py:138 (EN -> EN\nFR)
   - tests/integration/legacy_surface/test_incident_roles_surface.py:172-191 (each announcement EN -> EN\nFR, one post per changed role)
   - tests/integration/legacy_surface/test_incident_close_command_surface.py:126-129 (status and archived notices EN -> EN\nFR)
2. Unit and integration tests edited to the bilingual notice, replies unchanged:
   - tests/unit/features/incident/response/test_incident_response_status_entrypoint.py:92, :105 (FR invoker: notice EN\nFR, reply FR)
   - tests/integration/features/incident/response/test_incident_response_status_dispatch.py:110
   - tests/unit/features/incident/response/test_incident_response_roles_entrypoint.py:246-250, :254-259 (renamed: the announcements are in the instance languages and the submitter's notice in theirs; FR submitter: EN\nFR post, French ephemeral)
   - tests/integration/features/incident/response/test_incident_response_roles_dispatch.py:147
   - tests/unit/features/incident/response/test_incident_response_archive_entrypoint.py:152-171 (close: notices EN\nFR for EN and FR invokers; FR reply stays French); button tests :59, :226 unchanged
   - New cases (same files): an instance configured fr-FR then en-US (incident_scopes with a ConfiguredLanguagePolicy override, tests/factories/incident.py:134) puts French first in the status notice, each roles announcement and both close notices; an instance configured with one language posts one line. A user locale outside the supported set (en-GB) gets the instance's first language in the status and roles replies.
3. Status (entrypoints/slack.py): handle_status_update_command and handle_status_command take languages = reply_languages(payload.user_locale) for replies (render one line per reply language, like slack_archive._render); the notice is built inside incident_scope: MultilingualText.of(shared_languages(policy, conversation), lambda language: _t("notice", language, user=..., status=...)). The two `or "en-US"` defaults go. handle_status_command gains the scopes argument (registration wiring updated in register_*; the help path reads no store).
4. Roles (entrypoints/slack_roles.py, service/roles.py): announce becomes Callable[[IncidentRole, str], str | MultilingualText] in service/roles.py (:75, :141, docstring :85 "in the conversation's shared languages"); the entry point builds MultilingualText.of(shared_languages(policy, conversation), lambda language: _t("announcement", language, user=..., role=_t(f"name.{role.value}", language))). The modal and replies use reply_languages: the command takes its first reply language for the modal and stores it in private_metadata as today; the submission reads reply_languages(metadata locale) for the field error and the private notice. The `or "en-US"` defaults go.
5. Close (entrypoints/slack_archive.py): handle_close_command calls _archive without notice_languages; _archive drops the notice_languages parameter and the marker comment, so both paths take shared_languages. Replies unchanged.
6. Docs riding with the code:
   - decisions/languages.md: Context current state (:16) drops the "still post ... (TASK-145.8.9)" sentence; Migration drops the tolerated line "three incident channel notices in the invoker's language" and TASK-145.8.9 from Tickets; Changes line 2026-11-26.
   - tests/integration/legacy_surface/INVENTORY.md rows :124 (status), :125 (roles), :128 (close) name the TASK-145.8.9 named change (b).
   - features/incident/response/README.md: channel notices in the instance languages on every surface, replies in the user's language of choice.

AC -> step -> test
- AC #1 -> steps 3, 4, 5 -> the three pins (step 1), status/roles/archive entrypoint and dispatch tests, the French-first and one-language cases (step 2).
- AC #2 -> steps 3, 4 (replies via reply_languages), 5 (unchanged) -> the French-invoker tests and the en-GB case (step 2).
- AC #3 -> step 1 comments and the PR body list -> the three edited pins.
- AC #4 -> gates at the end.
- AC #5 (new) -> steps 3-5 -> grep evidence in the notes.

Test matrix
- happy: EN and FR invokers each get EN\nFR notices (status, each changed role, both close notices); replies in the invoker's language.
- boundary: instance order fr-FR, en-US puts French first; one configured language posts one line; several changed roles give one two-line post per role; unchanged roles post nothing.
- failure: refusals and stage lines (status.channel_failed, roles.announcements_failed, archive.notice_failed, not writable) stay in the reply language (existing tests, unchanged expectations); a user locale outside the supported set is answered in the instance's first language.
- authorization and idempotency: unchanged (no new path, no new write).

Named changes (PR body, kind (b), revert target the squash commit)
- /sre incident status update's channel notice in the instance languages (legacy: English; TASK-145.8.4 AC #6: the invoker's language).
- The roles announcement in the instance languages (TASK-145.8.5.1: the submitter's language).
- /sre incident close's status and archived notices in the instance languages (TASK-145.8.5.3: the invoker's language; the archive button already uses them).
With the default configuration a status change, a role change and a close now read the same from the modal, the button and the commands.

Size: production about 50 LOC over 4 Python files (entrypoints/slack.py, slack_roles.py, slack_archive.py, service/roles.py) plus 3 docs (languages.md, INVENTORY.md, response README.md); tests about 7 files. One subsystem (incident response). Under the gate.

Domain-model gate: not applicable (no entity, port, stored shape or setting changes; post already takes MultilingualText; the roles announce callable widens its return type only).

Assumptions to verify at implementation
- A1 Slack shows the "\n" of plain_text() as a line break (true for the field notice and archive button since #1867/#1887).
- A2 No other caller of handle_status_command or of the roles announce callable outside response (rg at implementation).

Blast radius and rollback: the text of three channel posts in every incident (one line per instance language instead of the invoker's); nothing stored, no ids, no buttons, no settings, no terraform. Wrong ship: a malformed line (a missing key shows the key, the neutral fallback). One git revert restores the old notices. No ordering constraint with other open PRs (#1888 and Lane B's W1 touch none of these files). If production's [languages] shared order changes later (separate config PR), these notices follow it with no code change.

Open questions (assessed at program scope: decisions/languages.md, i18n.md, migration.md; doc-11 rows 18.L6c.0, 18.L9b, 18.L10b, doc-15 165.x, doc-17)
- OQ1 Replies of status and roles onto reply_languages. ADR: languages.md Decision (direct interactions in the user's language of choice, matched by the policy) and Checks (no language tag literals in app/features/). Today slack.py and slack_roles.py default to a literal "en-US". Prior: show and archive already moved (TASK-193). Recommend: move them here (steps 3, 4); no visible change with the default config and normalised Slack locales; one more test case. Alternative: leave them (keeps four "en-US" literals the ADR's grep forbids, owned by no task).
- OQ2 TASK-189 (closing UX design session, To Do). languages.md applies to any redesigned close; the change here is one removed parameter. Recommend: keep close in scope (carried from 2026-11-25); no edit to TASK-189.
- OQ3 The D3 gap on TASK-118 (provider maps fr-CA and any other Slack locale to en-US before an entry point sees it). Weighed: passing the raw locale through here would change every slash command in every feature, not only incident; most features still call t(key, locale) directly, and t() has no primary-subtag fallback, so a raw fr-CA would reach users as the key (TASK-193 finding). The fix needs the translator move TASK-118 owns (decisions/languages.md Migration, line 3). Recommend: out of scope; TASK-118 keeps it as a named, user-visible change with its own announcement. This PR is correct for fr-CA users once TASK-118 lands, because the notices no longer depend on the invoker and the replies go through reply_languages.
- OQ4 Comments on upcoming shared posts (145.7.10, 165, 145.9.2, 145.10, 192): TASK-193 already left them on 2026-11-25 (use LanguagePolicy and MultilingualText). Recommend: no further comments.
- OQ5 AC #4 reworded to the current gate list; AC #1/#2 reworded from "English and French"/"actor's locale" to the instance languages and reply languages; new AC #5. Title "in English and French" -> "in the instance languages". Applied after approval.

AC changes proposed (after approval)
- #1 change_status's channel notice, the roles announcement and /sre incident close's status and archived notices are posted as MultilingualText in the conversation's shared_languages, in order, each line from its own catalogue (no second copy of a string)
- #2 Private replies of the same surfaces use reply_languages for the user's locale
- #4 ruff, mypy (no new errors in touched files), make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams and pytest tests --ignore=tests/smoke pass
- #5 (new) No language tag literal and no notice_languages override remain in incident/response entrypoints; decisions/languages.md no longer tolerates the three notices

User announcement: yes (every incident channel sees two-line notices on status update, role changes and close); written at implementation per delivery-session user-announcement.md. No developer change notice (no API, setting or contract change).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-26 implemented (TDD) on task-145.8.9-bilingual-channel-notices, plan approved as recommended (OQ1-OQ5).
What landed:
- entrypoints/slack.py: the status notice is MultilingualText.of(shared_languages(policy, conversation), ...) built inside incident_scope; replies through reply_languages (_render, one line per reply language); handle_status_command takes the scope opener (registered through a closure like status update); the two "en-US" defaults removed.
- entrypoints/slack_roles.py: each announcement is MultilingualText in the conversation's shared languages; the modal opens in the first reply language (stored in private_metadata as before); the field error and private notice use reply_languages of the metadata locale; the two "en-US" defaults removed. service/roles.py: announce returns str | MultilingualText.
- entrypoints/slack_archive.py: the command's notice_languages override and its marker comment removed; both close paths take shared_languages.
- Docs: decisions/languages.md (current state, the tolerated line and the ticket removed, Changes 2026-11-26); legacy_surface INVENTORY.md rows for status, roles and close name the TASK-145.8.9 named change (b); response README (every channel post in the shared languages).
- Pins edited citing decisions/migration.md step 4 kind (b): status command surface (5 statuses), roles surface (2 tests), close command surface (1 test). New cases: French-first order, one-language instance, unsupported locale (de-DE) answered in the instance's first language, French submitter's private notice stays French, close command on a French-first instance.
AC #5 evidence: rg '"en-US"|"fr-FR"' features/incident/response --type py: no match; notice_languages remains only as slack_show's local name for shared_languages (not an override).
Size: 4 production Python files, about 50 net production LOC; one subsystem.
Evidence (from app/): uv run ruff check . -> All checks passed!; make check-import-contracts -> Contracts: 15 kept, 0 broken; check-settings-key-ownership -> OK; check-package-shape -> OK (2 baselined); check-test-seams -> OK (47 strict, 12 legacy pin baselined); uv run mypy . -> Found 33 errors in 11 files (pre-existing count as on TASK-193; mypy features/incident/response: no issues in 23 files); uv run pytest tests --ignore=tests/smoke -> 8075 passed.
User-visible: announcement and screenshot list in the PR body. No change notice. In Progress until the PR merges.
<!-- SECTION:NOTES:END -->

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

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Status, roles and close channel notices post in the instance languages (MultilingualText from shared_languages); status and roles replies and the roles modal use reply_languages; three pins edited as kind (b) named changes; decisions/languages.md no longer tolerates them. Ships with the delivery-session change notice and the task-close-with-PR rule.
<!-- SECTION:FINAL_SUMMARY:END -->
