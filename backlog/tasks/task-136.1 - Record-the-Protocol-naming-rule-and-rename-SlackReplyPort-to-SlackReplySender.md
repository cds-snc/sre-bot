---
id: TASK-136.1
title: Record the Protocol naming rule and rename SlackReplyPort to SlackReplySender
status: In Progress
assignee: []
created_date: '2026-10-02 00:37'
updated_date: '2026-10-02 00:47'
labels:
  - plugin-architecture
  - naming
milestone: m-7
dependencies: []
references:
  - .claude/skills/type-model-boundaries/SKILL.md
  - decisions/feature-packages.md
  - decisions/transport-slack.md
  - app/contracts/slack/reply.py
parent_task_id: TASK-136
priority: medium
ordinal: 298000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-136. Records the rule that a Protocol is named for the role it plays and never carries the Port suffix, and that docstrings and decision prose say 'interface' (keeping 'port' only where a record discusses ports-and-adapters itself). The rule goes in .claude/skills/type-model-boundaries/SKILL.md and decisions/feature-packages.md, the record that owns package structure (no record owns Protocol naming today). Applies it to contracts/slack: SlackReplyPort becomes SlackReplySender, with every importer rewritten and no alias or re-export at the old name. Mechanical rename only; the IncidentDocumentPort slice is TASK-136.2 and the access slice is TASK-136.3. Decided by the human in chat on 2026-10-02.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The naming rule (Protocols named for their role, no Port suffix, 'interface' in docstrings and decision prose, 'port' kept only where a record discusses ports-and-adapters itself) is recorded in .claude/skills/type-model-boundaries/SKILL.md and in decisions/feature-packages.md, with a dated line in the record's Changes log
- [x] #2 SlackReplyPort is renamed to SlackReplySender in contracts/slack/reply.py and every importer (contracts, integrations, rant, user_rotations, incident_draft, tests) is rewritten; rg finds no 'SlackReplyPort' in app/, decisions/ or .claude/, and no alias or re-export exists at the old name
- [x] #3 Docstrings and comments in the files this slice touches that describe the reply interface say 'interface' instead of 'port' (reply.py, registrar.py, integrations/slack/provider.py, the rant, user_rotations and incident_draft handlers, the touched tests); the out-of-scope IncidentChannelPort and get_incident_channel_port names are untouched
- [x] #4 No behaviour change: the TASK-36 legacy_surface suite is green with no assertion change
- [x] #5 Full CI sequence from app/ passes: ruff check, make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test, and mypy shows no new errors in touched files
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Applies decisions/feature-packages.md (package structure, Protocols injected through constructors) and the type-model-boundaries skill. Mechanical rename plus the recorded rule; no decision record owns Protocol naming today, so the rule goes in the skill and in feature-packages.md (decided 2026-10-02).

Decisions (settled in chat 2026-10-02, not reopened here):
- SlackReplyPort becomes SlackReplySender. No alias, no re-export at the old name.
- The rule: a Protocol is named for the role it plays (Reader, Lookup, Store, Provider, Registrar, Sender), never for the pattern; 'Port' stays out of class, function and variable names; docstrings and decision prose say 'interface', keeping 'port' only where a record discusses ports-and-adapters itself.
- Rule home: .claude/skills/type-model-boundaries/SKILL.md and decisions/feature-packages.md. Other records that discuss ports-and-adapters (platform-entrypoints.md:14-16, cloud-portability.md:21, service-accounts.md, platform-transports.md) keep the word and are not edited.
- IncidentChannelPort and get_incident_channel_port stay (TASK-135 owns them). IncidentDocumentPort is TASK-136.2, the access Protocols TASK-136.3.

Found call sites (rg SlackReplyPort, 2026-10-02; 18 occurrences, 9 files, no other reference in app/, Makefile, .github, pyproject, app/bin, decisions/ or .claude/):
- Production (7 files): contracts/slack/reply.py:15 (class) and its module docstring line 3 ('only through this port'); contracts/slack/registrar.py:13 (import), :20 (return type), :17 class docstring ('exposes the reply port'), :21 ('Port handlers use to post messages and open views'); integrations/slack/provider.py:40 (docstring naming the class), :659 (reply property docstring 'Get the reply port ...'); packages/rant/platforms/slack.py:7 (import), :43 (annotation), :21 (docstring 'reply port'), :61 ('reply: Port used to post the customized message.'); packages/user_rotations/platforms/slack.py:10 (import), :65 (annotation); packages/incident_draft/platforms/slack.py:30 (import), :112 and :172 (annotations), :14 (docstring 'registrar's reply port'), :127 ('reply: Port used to post the progress notice.').
- Tests (4 files): tests/factories/slack.py:8 (import), :49 (return type), :42 (docstring 'fake reply port'); tests/unit/contracts/slack/test_slack_contracts_registrar_protocol.py:20, :31, :70 and test name :69 (test_reply_port_methods_take_keyword_only_arguments); tests/unit/integrations/slack/test_slack_provider_reply_classifies_errors.py:21, :49, module docstring :1 and :7 ('the port must classify'), test name :47 (..._reply_is_a_reply_port); tests/unit/packages/rant/test_rant_slack.py:128 (docstring 'reply port').
- Prose: decisions/transport-slack.md says 'outbound messaging Protocol' and never names SlackReplyPort, so it needs no edit. decisions/feature-packages.md uses 'port' at :17 ('each carries its own port'), :64 ('purpose-shaped ports') and :118 ('its own channel port'); no code string, baseline, Makefile or CI file names any of the old identifiers.
- Out of scope in the touched files: incident_draft/platforms/slack.py also holds IncidentChannelPort (:38, :113, :265, :292, :345, :415, :450) and get_incident_channel_port (:33, :83, :86); they are not touched, nor is the docstring at :128 ('channel: Port reading the incident channel') which belongs to TASK-136.2.

Steps:
1. Tests first: tests/unit/contracts/slack/test_slack_contracts_registrar_protocol.py and the integrations/slack test are rewritten in place to import SlackReplySender (they fail at import until step 3), and test names lose 'port' (test_reply_sender_methods_take_keyword_only_arguments, ..._reply_is_a_reply_sender). Add tests/unit/contracts/slack/test_slack_contracts_reply_sender_name.py: contracts.slack.reply exposes SlackReplySender with post_message, post_ephemeral and open_view, and has no attribute SlackReplyPort (no alias). No behaviour test is added.
2. tests/factories/slack.py and test_rant_slack.py: import, return type and docstring wording ('reply interface').
3. contracts/slack/reply.py: rename the class and reword the docstring ('only through this interface'); registrar.py: import, return type, docstrings. integrations/slack/provider.py: the two docstrings.
4. Handlers: rant, user_rotations and incident_draft platforms/slack.py import and annotations; docstring words at the lines above ('Interface used to post ...').
5. Record the rule. .claude/skills/type-model-boundaries/SKILL.md: a Rules bullet (role names, no Port suffix, 'interface' in prose, port kept only for ports-and-adapters discussion) and an anti-pattern line. decisions/feature-packages.md: a bullet under Dependency rules; 'port' prose at :17, :64 and :118 reworded to 'interface'; a dated line in the Changes log.
6. rg 'SlackReplyPort' app decisions .claude must be empty. Run the gates.

Test matrix: existing suites are the behaviour guard (registrar protocol shape, provider reply classification, rant, user_rotations and incident_draft handler tests, tests/integration/legacy_surface); the one new test pins the public name and the absence of the old one. No happy/failure matrix is added because nothing behavioural changes.

Verify (from app/): uv run ruff check .; make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test; mypy on the touched files (no new errors); rg -n 'SlackReplyPort' /workspace/app /workspace/decisions /workspace/.claude (empty); pytest tests/integration/legacy_surface green with no assertion edited.

AC map: #1 step 5 (read both files; rg 'Port suffix' in the skill and record); #2 steps 1-4 + the new name test + rg; #3 steps 2-5 (rg -i '\bport\b' over the touched files shows only IncidentChannelPort-related lines, whose names are untouched); #4 legacy_surface unchanged; #5 gates.

Size: 7 production files, about 25 changed lines; 2 documentation files, about 15 lines; 4 existing test files edited plus 1 new. Two surfaces (code rename, docs) but both mechanical and one subsystem family (contracts and its consumers); under the gate.
Behaviour: none. The runtime object (SlackWebReply) is unchanged and satisfies the Protocol structurally, so nothing resolves by name at runtime.
Blast radius: import errors at collection or startup if an importer is missed; mypy and the full test run catch it. Rollback: git revert.
Ordering: TASK-136.2 edits incident_draft/platforms/slack.py too (lines 10 and 128, adjacent to this slice's 127), so it merges after this one.

Doubts to verify: (1) nothing outside app/ (terraform, docs/, scripts, README) names SlackReplyPort (rg over /workspace excluding backlog/ found none on 2026-10-02; re-run). (2) No test patches or patches-by-string the old name (rg found none). (3) Packages other than the three listed accept the registrar's reply only through registrar.reply, not by annotation (rg 'registrar.reply' app/packages).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented on plan/task-136-protocol-role-names (uncommitted; the human cuts the PR branch), tests first.

What changed:
- contracts/slack/reply.py: SlackReplyPort is now SlackReplySender; no alias. contracts/slack/registrar.py, integrations/slack/provider.py and the rant, user_rotations and incident_draft platforms/slack.py modules import and annotate with the new name. Docstrings in those files say 'interface' where they said 'port'.
- Rule recorded: .claude/skills/type-model-boundaries/SKILL.md (two Rules bullets, one anti-pattern) and decisions/feature-packages.md (a bullet under Dependency rules, 'port' reworded to 'interface' in three places, a 2026-10-02 Changes line).
- Left for TASK-136.2 as planned: incident_draft/platforms/slack.py:10 ('the document port') and :128 ('channel: Port reading the incident channel'). IncidentChannelPort and get_incident_channel_port are untouched.

Tests:
- New tests/unit/contracts/slack/test_slack_contracts_reply_sender_name.py (2 tests): the module exposes the SlackReplySender Protocol with its three methods and has no SlackReplyPort attribute. It failed at import before the rename.
- Edited in place, names and wording only: tests/factories/slack.py, test_slack_contracts_registrar_protocol.py (test renamed ..._reply_sender_methods_...), test_slack_provider_reply_classifies_errors.py (test renamed ..._is_a_reply_sender), test_rant_slack.py (docstring).

Gates (from app/, full ci_code.yml sequence): ruff check clean; make fmt-ci 782 files already formatted; check-sdk-typing, check-vendor-package-contract, check-aws-platform-seam and check-runtime-imports OK; lint-imports 8 kept, 0 broken, ignore counts unchanged ((a) 11, (b) 44, (d) 11, (e) 34, (f) 3); mypy 65 errors in 22 files repo-wide, the same count as before the change, 0 in touched files; make test 2856 passed then 760 passed; tests/integration/legacy_surface green with no file in it edited.

Verified: rg 'SlackReplyPort' over app/, decisions/ and .claude/ finds one line only, the string in the new test's absence assertion.

Size: 6 production files (not 7: reply.py, registrar.py, provider.py and three handlers), about 19 changed lines; 2 documentation files; 4 test files edited, 1 new.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 00:41
---
Plan approved 2026-10-02 (Guillaume Charest, in session), as written.
---
<!-- COMMENTS:END -->
