---
id: TASK-25.1.6.12
title: Fix the unquoted A1 sheet-name range in the Google Groups members report
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-02 18:52'
updated_date: '2026-09-02 19:59'
labels:
  - reports
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.1
references:
  - app/modules/reports/google_groups.py
  - app/tests/unit/modules/reports/test_google_groups_report.py
  - decisions/testing.md
  - 'https://developers.google.com/workspace/sheets/api/guides/concepts'
  - 'https://github.com/burnash/gspread/blob/master/gspread/utils.py'
parent_task_id: TASK-25.1.6
priority: high
type: bug
ordinal: 132500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while planning TASK-25.1.6.1 (see the SUSPECTED PRODUCTION DEFECT comment on that task for the full evidence). Split out as its own task rather than folded into a characterization gate or a migration PR, so a behaviour fix is reviewed as a behaviour fix.

THE DEFECT. app/modules/reports/google_groups.py:97 builds an A1 range by interpolating a Google Group DISPLAY NAME straight into f"{group_sheet_name}!A1" with no quoting, and :72 passes the same bare name as the get_sheet ranges argument. Google Sheets A1 notation requires a sheet name containing spaces or special characters to be wrapped in single quotes, with any embedded single quote doubled. Unquoted, the API rejects the request with 400 "Unable to parse range". Google Group display names routinely contain spaces.

EVIDENCE THAT THIS IS REAL, NOT SPECULATION.
(a) It is the only user-controlled sheet name in an A1 range repo-wide. Every other range is a hardcoded, space-free literal: incident_folder.py:271 Sheet1!A:A, :305 Sheet1, :318 an f-string over a Sheet1 literal, spending.py:192 Sheet1.
(b) TASK-25.1.3 relocated a live "Unable to parse range" swallow for the incidents sheet, so this application demonstrably hits that exact error class in production.
(c) tests/factories/google.py emits space-free names like group-name1, so tests built on the factory never surface it, which is likely why it survived.

LIKELY PRODUCTION SHAPE. get_sheet 400s and is swallowed by the blanket except, so sheet becomes None; the addSheet path then runs; if the sheet already exists that 400s too and is swallowed by the second except; finally batch_update_values 400s and PROPAGATES, because nothing wraps it. The /sre reports google-groups-members Slack command dies at the first affected group with no respond() at all, so the user sees nothing. The two blanket excepts are actively masking the diagnosis.

SECOND DEFECT, SAME FIX WINDOW. The 50-character truncation at :69-70 can collide two different group names onto one sheet title. The second group write then silently overwrites the first, and the resulting duplicate-title addSheet 400 is swallowed too.

VERIFY BEFORE CHANGING. The first step is to confirm the quoting rule and the exact failure against the Sheets API documentation and a targeted check, not to assume it. Quoting is valid A1 notation whether or not the API is lenient, so the fix is safe either way, but the task notes must record what was actually confirmed.

EXPLICITLY OUT OF SCOPE, to avoid colliding with TASK-25.1.6.10.
- Do NOT touch the blanket "except Exception: sheet = None" around get_sheet or the blanket except around the addSheet batch_update. TASK-25.1.6.10 AC#3 owns replacing those with classification-based handling.
- Do NOT add resilience around batch_update_values so that one bad group is skipped instead of aborting the report. Quoting removes the main cause of that abort; the remaining resilience question belongs with TASK-25.1.6.10, which is rewriting the error handling in this function anyway. It is registered there by comment.
- Do NOT migrate any call site onto an adapter. This task leaves the seam exactly where it is.

GUARDED BY TASK-25.1.6.1, which is a hard dependency. That task pins todays unquoted output in a named defect probe (a group called SRE Team producing an unquoted range) plus a failure test covering the abort-with-no-respond shape. This fix flips that probe assertion; nothing else in that file should need to change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The quoting rule and the failure mode are confirmed before any production edit, and the task notes record what was verified and how
- [x] #2 The A1 range passed to sheets.batch_update_values wraps the sheet name in single quotes with embedded single quotes doubled, so a group named with spaces, a leading digit or an apostrophe produces a valid range
- [x] #3 The ranges argument passed to sheets.get_sheet is quoted by the same rule and through the same single helper, so the two call sites cannot drift apart
- [x] #4 The derived sheet title has apostrophes removed, so no title Google receives can contain the A1 quote character; the addSheet title and the Group Name cell carry that same derived title unquoted
- [x] #5 Derived sheet titles are collision-safe and deterministic across processes: two group names that would reduce to the same title, whether by length truncation or by apostrophe removal, resolve to different titles, and the same group name resolves to the same title on every run
- [x] #6 The characterization tests are updated only where an A1 range or a derived sheet title is asserted, each change is named in the task notes, and the assertions about respond messages, the values matrix, call counts and call ordering are untouched
- [x] #7 The blanket excepts around get_sheet and the addSheet batch_update are untouched, and no call site is migrated onto an adapter, leaving TASK-25.1.6.10 scope intact
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
VERIFICATION DONE AT PLANNING TIME (AC#1 evidence; re-record in Notes at implementation time)

1. The SDK gives you nothing. Confirmed against the installed packages, not from memory:
   .venv/.../googleapiclient-stubs/_apis/sheets/v4/resources.pyi types the parameters as
   `range: str` and `ranges: str | _list[str] | None`. There is no A1 builder, quoter or
   escaper anywhere in googleapiclient or its stubs. A1 quoting is 100 percent caller-side
   responsibility, so "use the SDK helper" is not an available option here.

2. Google states the requirement but not the escape. The Sheets API concepts page says
   verbatim: "Single quotes are required for sheet names with spaces or special characters",
   and gives `'My Custom Sheet'!A:A`. It also says `'A1'` refers to a SHEET named A1 while
   bare `A1` refers to a CELL, and that with a named range called Sheet1, bare `Sheet1`
   resolves to the named range while `'Sheet1'` resolves to the sheet. So quoting is not
   merely tolerated on names that do not need it, it is the more precise reference form.
   The same page then writes `'Jon's_Data'!A1:D5` with the embedded apostrophe NOT doubled,
   which contradicts the standard escape. Google's own docs are internally inconsistent on
   exactly the apostrophe case, which is why item 3 matters.

3. gspread settles both questions empirically. burnash/gspread is the de facto Python Sheets
   client and drives every one of its values calls through one helper:
       def absolute_range_name(sheet_name, range_name=None):
           sheet_name = "'{}'".format(sheet_name.replace("'", "''"))
           return "{}!{}".format(sheet_name, range_name) if range_name else sheet_name
   Its doctests pin `absolute_range_name("Sheet1", "A1") == "'Sheet1'!A1"` (quoted even for
   a plain alphanumeric name) and `absolute_range_name("Sheet'1") == "'Sheet''1'"` (doubling).
   Its parser is the mirror image: SHEET_TITLE_RE = r"'((?:[^']|'')+)'!|([^!]+)!" and
   extract_title_from_range does .replace("''", "'"). A widely used library quoting
   unconditionally against live Google is stronger evidence than the docs example.

CONCLUSION, answering the nuance that we quote nothing today: unconditional quoting is the
safe direction, not the risky one. It cannot break a name that works unquoted (the quoted
form is documented as the sheet reference), it fixes every name that is broken today, and it
avoids inventing a "does this name need quoting" predicate, which would be a guess since
Google never enumerates its special characters. Conditional quoting is rejected.

TARGET SHAPE, app/modules/reports/google_groups.py

The root cause is one variable doing two jobs: `group_sheet_name` holds the sheet TITLE at
:72 and :84 and :96, then is reassigned to an A1 RANGE at :97. Split it, and put each job
behind its own helper.

Two module-private helpers, added above generate_report:

    _SHEET_TITLE_MAX_LENGTH = 50
    _SHEET_TITLE_DIGEST_LENGTH = 6

    def _sheet_title(group_name: str) -> str:
        # Apostrophes are stripped so no title can contain the A1 quote character.
        sanitised = group_name.replace("'", "")
        if sanitised == group_name and len(sanitised) <= _SHEET_TITLE_MAX_LENGTH:
            return sanitised
        digest = hashlib.sha256(group_name.encode("utf-8")).hexdigest()[:_SHEET_TITLE_DIGEST_LENGTH]
        keep = _SHEET_TITLE_MAX_LENGTH - _SHEET_TITLE_DIGEST_LENGTH - 1
        return f"{sanitised[:keep]}-{digest}"

    def _a1_range(sheet_title: str, cell: str = "") -> str:
        quoted = "'{}'".format(sheet_title.replace("'", "''"))
        return f"{quoted}!{cell}" if cell else quoted

Notes on the design, so review does not have to reconstruct it:
- hashlib.sha256, never the builtin hash(). str.__hash__ is salted per process
  (PYTHONHASHSEED), so a builtin-hash suffix would give a different sheet title on every
  container restart and the report would silently create duplicate sheets. sha256 is also
  what keeps ruff's S rules quiet; md5/sha1 would trip S324.
- The suffix fires only when the title actually had to be derived (too long, or an
  apostrophe removed). A short apostrophe-free name is returned byte for byte as today, so
  the common path is untouched and most characterization assertions are unaffected.
- _a1_range keeps the doubling even though _sheet_title now guarantees no apostrophe
  reaches it. That is deliberate: it makes _a1_range a correct general A1 quoter matching
  gspread's semantics, so a future caller that passes a raw name is still safe. It is one
  .replace, and it is the behaviour AC#2 asks for.

Call-site rewiring inside the group loop (today's :66-106):
  - `sheet_title = _sheet_title(group["name"])`, replacing the f-string plus the
    len>50 truncate block at :66-70.
  - `log.info("processing_group_sheet", group=sheet_title)` unchanged in intent.
  - `sheets.get_sheet(file["id"], _a1_range(sheet_title))` at :72.
  - addSheet properties title stays `sheet_title`, UNQUOTED. A sheet title is a literal
    title, not A1 notation; quoting it would create a sheet whose name literally contains
    apostrophes.
  - `values = [["Group Name", sheet_title], ["Email", "Role"]]` unchanged in intent.
  - `sheets.batch_update_values(file["id"], _a1_range(sheet_title, "A1"), values)`,
    replacing the `group_sheet_name = f"{group_sheet_name}!A1"` reassignment at :97.
  - `log.info("sheet_updated", sheet=sheet_title)` now logs the title rather than the
    range, a side effect of removing the variable reuse. No test asserts it.

No other line in the file changes. `import hashlib` is the only new import.

ORDERED STEPS

1. Re-run the two verification checks above and write the result into the task Notes
   (AC#1): the stub signatures from the installed venv, the concepts-page quotes including
   the inconsistent apostrophe example, and gspread's absolute_range_name plus its two
   doctests. Do not skip this because the plan already records it; AC#1 asks for what was
   verified at implementation time.
2. Update the tests first (they are the specification here, and TASK-25.1.6.1 already shipped
   the harness). In app/tests/unit/modules/reports/test_google_groups_report.py, change
   exactly these six assertions and add four:
   CHANGED
     a. TestGenerateGroupMembersReportBehaviour::test_should_exclude_groups_whose_name_
        contains_aws_prefix -- write range "GroupOne!A1" becomes "'GroupOne'!A1".
     b. ...::test_should_truncate_sheet_name_to_fifty_characters_in_cell_and_range --
        rename to test_should_derive_a_bounded_sheet_title_for_an_overlong_group_name; the
        60-G name now yields a 50-char title of 43 Gs, a hyphen and the 6-hex sha256 prefix
        of the full name; assert cell_range == _a1_range(expected_title, "A1") shape and
        values[0] == ["Group Name", expected_title]. Compute the digest in the test with
        hashlib rather than hardcoding a hex literal.
     c. ...::test_should_leave_sheet_names_containing_spaces_unquoted_in_ranges -- rename to
        test_should_quote_sheet_names_containing_spaces_in_ranges; the defect probe flips:
        _sheets_read == [(_FILE_ID, "'SRE Team'")] and write range "'SRE Team'!A1". Drop the
        pinned-not-endorsed comment. Add to this test that the addSheet title is still the
        bare "SRE Team", which is the assertion that proves quoting was applied at the range
        and only at the range.
     d. TestGenerateGroupMembersReportBoundary::test_should_read_and_create_sheets_with_the_
        group_sheet_name -- read range becomes "'GroupOne'"; the _sheet_create_requests
        assertion stays exactly as it is, title "GroupOne".
     e. ...::test_should_write_values_positionally_with_file_id_and_range -- cell_range
        becomes "'GroupOne'!A1".
     f. TestGenerateGroupMembersReportFailureModes::test_should_propagate_a_mid_loop_write_
        failure_leaving_the_first_sheet_written -- ranges become ["'GroupOne'!A1",
        "'GroupTwo'!A1"].
   ADDED (all pytest.mark.unit, all through the existing report_deps fixture and accessors)
     g. Behaviour: a group named "Jon's Team" produces addSheet title "Jons Team", cell
        value "Jons Team", and range "'Jons Team'!A1" -- the apostrophe never reaches Google
        in either position. Because the title was derived, it also carries the digest
        suffix; assert the exact string the helper produces.
     h. Behaviour: two groups whose names share their first 50 characters produce two
        DIFFERENT sheet titles and two different write ranges (AC#5 collision case).
     i. Behaviour: "Jon's Team" and "Jons Team" as two groups in one run also produce two
        different titles (the apostrophe-removal collision case).
     j. Determinism: invoke generate_group_members_report twice with the same overlong group
        and assert the two runs produced identical write ranges. This is the regression
        guard against anyone swapping sha256 for the builtin hash(); it must be a
        same-process double invocation, since PYTHONHASHSEED is fixed within one process --
        state that limitation in the test docstring rather than pretending it proves more.
   UNTOUCHED, and verify at review that they are: the three respond-message assertions, the
   values-matrix ordering test, the sleep test, the file lookup and creation tests, the
   list-groups call-count test and all seven failure-mode behaviours other than (f).
3. Implement the two helpers and rewire the six usages of group_sheet_name as described in
   TARGET SHAPE. Do not touch anything else in the file.
4. Validate: cd app && uv run pytest tests/unit/modules/reports -q, then uv run ruff check .,
   then uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' confirming zero errors mention
   modules/reports or tests/unit/modules/reports (the repo carries a ~94-error pre-existing
   mypy baseline; do not read a green whole-tree run as the bar), then the Makefile split
   make test-new and make test-legacy rather than a single whole-tree pytest run.
5. Write the Notes: the AC#1 verification record, and the explicit list of the six changed
   plus four added test assertions, satisfying AC#6's "each change is named".
6. Post-merge, update the two pre-registered sibling comments if implementation deviated
   from the helper names _sheet_title and _a1_range.

AC TRACEABILITY
- AC#1 -> step 1, plus the VERIFICATION DONE section above.
- AC#2 -> _a1_range's doubling, exercised by step 2 items c, g.
- AC#3 -> both call sites go through _a1_range; step 2 items c, d assert the get_sheet side.
- AC#4 -> _sheet_title's apostrophe strip; step 2 item g asserts title, cell and range together.
- AC#5 -> _sheet_title's sha256 suffix; step 2 items b, h, i, j.
- AC#6 -> step 2's explicit changed/added/untouched split, recorded in Notes at step 5.
- AC#7 -> step 3's "do not touch anything else"; verified by git diff at review.

TEST MATRIX
| Case | Class | Asserts |
| plain name quoted | Behaviour | 'GroupOne'!A1 write, 'GroupOne' read, GroupOne addSheet title |
| name with a space | Behaviour | 'SRE Team'!A1 write, bare SRE Team addSheet title |
| overlong name | Behaviour | 43 chars + hyphen + 6 hex, same title in cell and range |
| name with an apostrophe | Behaviour | apostrophe absent from title and cell, range quoted |
| 50-char prefix collision | Behaviour | two distinct titles, two distinct ranges |
| apostrophe collision | Behaviour | two distinct titles |
| determinism across runs | Behaviour | two invocations, identical ranges |
| mid-loop write failure | FailureModes | quoted ranges, still propagates, still no respond |

ASSUMPTIONS AND DOUBTS
- RESOLVED by research, was the plan's main open question: quote unconditionally. Evidence in
  VERIFICATION DONE items 1-3. Conditional quoting is rejected because the predicate would be
  a guess about Google's unenumerated special-character set.
- RESOLVED by the human: strip apostrophes from derived titles rather than rely solely on
  doubling. The doubling in _a1_range is retained anyway as the correct general primitive.
  A reviewer who considers that redundant can delete the .replace in _a1_range without
  changing observable behaviour, since no title can reach it with an apostrophe -- flagging
  this explicitly rather than defending it as load-bearing.
- NOT A CONCERN, verified: the derived-title change cannot orphan existing production sheets.
  The spreadsheet filename is date-derived (groups_report_YYYY-MM-DD at :35), so a new file is
  created each day and sheets are created fresh inside it. Within a day, re-running resolves
  to the same file and the same deterministic titles.
- OPEN, for the reviewer, deliberately not decided here: the Group Name cell at :96 carries
  the DERIVED title, so for an overlong or apostrophe-bearing group the human-readable cell
  now shows a hash suffix, which is worse to read than today's plain truncation. Putting the
  FULL group["name"] in that cell and keeping the derived value only for the sheet title and
  the range would be strictly more useful, but it is a behaviour change nobody asked for and
  it would change one more characterization assertion. Left as-is; say yes and it is a
  two-line follow-up.
- NOT VERIFIED, and cannot be from here: that a group display name containing an apostrophe
  actually exists in the tenant. The fix is correct regardless.
- The 50-character bound is inherited, not chosen. Google Sheets allows longer titles; the
  plan keeps 50 because widening it is out of scope and would change more assertions.

BLAST RADIUS AND ROLLBACK
One production file, app/modules/reports/google_groups.py: two new helpers, two constants,
one new import, and six rewired usages inside one loop. Roughly 25 to 35 production LOC.
One test file. No settings, terraform, CI, dependency or migration-ordering change. The only
consumer is the /sre reports google-groups-members Slack command. A single git revert restores
today's behaviour, and the TASK-25.1.6.1 harness would then go red on the six assertions,
which is the intended signal.

SIZE GATE VERDICT: FITS ONE PR. One production file, one subsystem, well under the 400 LOC
and 10 file thresholds, no mechanical migration mixed in with the behaviour change (that
separation is exactly why this task exists apart from TASK-25.1.6.10). No decomposition.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTED as planned. One production file changed: app/modules/reports/google_groups.py.

AC#1 VERIFICATION RECORD (re-run at implementation time, 2026-09-02)
- Installed stubs, .venv/lib/python3.14/site-packages/googleapiclient-stubs/_apis/sheets/v4/resources.pyi:
  values().get/update type the parameter as `range: str` (line ~133) and spreadsheets().get types
  `ranges: str | _list[str] | None = ...` (line ~186). Confirmed by grep against the installed venv,
  not from memory. There is no A1 builder, quoter or escaper anywhere in googleapiclient or its stubs,
  so quoting is entirely caller-side. "Defer to an SDK helper" is not an available option.
- Sheets API concepts page: "Single quotes are required for sheet names with spaces or special
  characters" ('My Custom Sheet'!A:A); 'Sheet1' is the precise SHEET reference while bare Sheet1 can
  resolve to a named range. The same page writes 'Jon's_Data'!A1:D5 with the apostrophe NOT doubled,
  i.e. Google's docs are internally inconsistent on exactly the apostrophe case.
- gspread (not installed in this venv; evidence is the upstream source cited in the task references)
  settles it: absolute_range_name() quotes UNCONDITIONALLY and doubles embedded quotes, doctests pin
  "'Sheet1'!A1" and "'Sheet''1'", and its parser mirrors that with '((?:[^']|'')+)'! plus
  .replace("''", "'").
- CONCLUSION UNCHANGED: quote unconditionally. Not verified and not verifiable from here: that a live
  400 "Unable to parse range" occurs for a specific tenant group name. The fix is valid A1 notation
  either way.

PRODUCTION CHANGE
- New import: hashlib. New constants _SHEET_TITLE_MAX_LENGTH = 50, _SHEET_TITLE_DIGEST_LENGTH = 6.
- New module-private _sheet_title(group_name): strips apostrophes; returns the name byte-for-byte when
  it was already apostrophe-free and <= 50 chars; otherwise truncates to 43 and appends "-" plus the
  6-hex sha256 prefix of the FULL original name. sha256 not builtin hash(), which is PYTHONHASHSEED
  salted and would yield a different title after every container restart.
- New module-private _a1_range(sheet_title, cell=""): wraps in single quotes, doubling embedded quotes,
  and appends "!<cell>" when a cell is given.
- Rewired the six uses of the old dual-purpose group_sheet_name variable: title derivation replaces the
  f-string + len>50 truncate block; get_sheet takes _a1_range(sheet_title); the addSheet properties
  title and the "Group Name" cell carry the bare derived title; batch_update_values takes
  _a1_range(sheet_title, "A1"), replacing the in-place reassignment to an A1 range. sheet_updated now
  logs the title rather than the range (no test asserts it).

AC#7 HELD: both blanket excepts are byte-identical to before; no call site moved onto an adapter.
TASK-25.1.6.10 scope intact.

AC#6 TEST DELTA, app/tests/unit/modules/reports/test_google_groups_report.py
CHANGED (6, all A1-range or derived-title assertions only)
 1. Behaviour::test_should_exclude_groups_whose_name_contains_aws_prefix - write range
    "GroupOne!A1" -> "'GroupOne'!A1".
 2. Behaviour::test_should_truncate_sheet_name_to_fifty_characters_in_cell_and_range renamed to
    test_should_derive_a_bounded_sheet_title_for_an_overlong_group_name - 60-G name now yields
    43 Gs + "-" + 6 hex; digest computed in-test with hashlib, not hardcoded.
 3. Behaviour::test_should_leave_sheet_names_containing_spaces_unquoted_in_ranges renamed to
    test_should_quote_sheet_names_containing_spaces_in_ranges - the defect probe flips to
    read (_FILE_ID, "'SRE Team'") and write "'SRE Team'!A1", plus a new assertion that the addSheet
    title is still the bare "SRE Team". Pinned-not-endorsed comment dropped.
 4. Boundary::test_should_read_and_create_sheets_with_the_group_sheet_name - read range -> "'GroupOne'";
    _sheet_create_requests assertion unchanged, title still "GroupOne".
 5. Boundary::test_should_write_values_positionally_with_file_id_and_range - "'GroupOne'!A1".
 6. FailureModes::test_should_propagate_a_mid_loop_write_failure_leaving_the_first_sheet_written -
    ranges -> ["'GroupOne'!A1", "'GroupTwo'!A1"].
ADDED (4)
 7. test_should_strip_apostrophes_from_the_title_google_receives - "Jon's Team": apostrophe absent from
    addSheet title and from the Group Name cell, range quoted.
 8. test_should_derive_distinct_titles_for_group_names_sharing_a_fifty_character_prefix - AC#5 length
    collision: two distinct titles and two distinct ranges.
 9. test_should_derive_distinct_titles_when_apostrophe_removal_would_collide - "Jon's Team" vs
    "Jons Team" resolve to two distinct titles.
10. test_should_derive_the_same_title_on_every_run_for_the_same_group_name - same-process double
    invocation yields identical ranges. Docstring states the limitation: PYTHONHASHSEED is fixed within
    one process, so this guards against a per-run derivation, not against the salted builtin hash().
UNTOUCHED as required: the three respond-message assertions, the values-matrix ordering test, the sleep
test, the file lookup/creation/reuse tests, the list-groups call-count test, and the six failure-mode
behaviours other than item 6.

TEST EVIDENCE
- uv run pytest tests/unit/modules/reports -q: 25 passed.
- uv run ruff check .: All checks passed.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)': zero errors matching reports/google_groups (grep -c
  returned 0). The repo carries a pre-existing ~94-error baseline elsewhere; that baseline is unchanged.
- make test (whole suite, run manually by the human): green.

LEFT FOR HUMAN VERIFICATION / DoD
- Reviewer confirmation via git diff that AC#7 holds (excepts untouched, no adapter migration).
- The plan's OPEN question, deliberately not decided: the "Group Name" cell now shows the DERIVED title,
  so for an overlong or apostrophe-bearing group it carries a hash suffix, which reads worse than
  today's plain truncation. Putting the full group["name"] in that cell while keeping the derived value
  for the sheet title and range is a two-line follow-up if wanted; it is registered on TASK-25.1.6.10.
- Post-merge, update the two pre-registered sibling comments if reviewers rename _sheet_title/_a1_range.
- No behaviour confirmed against live Google; this was not exercised against the real Sheets API.

CLARIFICATION ON THE gspread EVIDENCE (added after review, to prevent confusion in this codebase)
gspread is a THIRD-PARTY, community-maintained Sheets client (burnash/gspread). It is NOT the Google
Python API client (google-api-python-client / googleapiclient) and NOT googleapiclient-stubs. This
repository does NOT depend on gspread, does not import it, and this task adds no such dependency; it
is not installed in the venv. It was cited purely as CORROBORATING PRIOR ART for the A1 quoting rule -
a widely used library that quotes unconditionally and doubles embedded quotes against live Google -
because the official Google documentation is self-contradictory on the apostrophe case and the
official client we DO use exposes no A1 helper at all.

The binding evidence for our implementation is therefore: (1) the installed googleapiclient-stubs
signatures showing `range: str` / `ranges: str | list[str] | None`, i.e. no SDK-side quoting exists,
and (2) the Sheets API concepts page requiring single quotes. gspread's absolute_range_name() is
referenced as a sanity check on the escape form only. Our _a1_range() is our own implementation in
app/modules/reports/google_groups.py; it is not copied from, vendored from, or coupled to gspread.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-02 19:39
---
AC SET REPLACED 2026-09-02 (task-planner, human-directed research outcome). Recording the replacement explicitly per the backlog-task-workflow rule against silently reshaping ACs. Six criteria became seven; nothing was dropped from scope.

WHY. The human asked that the quoting strategy be settled by researching the Google Python client and its stubs rather than by picking the option with the smallest test diff, and separately chose to strip apostrophes from derived sheet titles. Both answers changed what the ACs need to say.

WHAT THE RESEARCH FOUND. (1) googleapiclient and googleapiclient-stubs offer NO A1 helper at all - the installed sheets/v4 stub types the parameters as plain `range: str` / `ranges: str | list[str] | None`, so quoting is entirely caller-side and there is no SDK primitive to defer to. (2) The Sheets concepts page requires quotes for names with spaces or special characters, documents `'Sheet1'` as the precise sheet reference (bare `Sheet1` can resolve to a named range instead), and then writes `'Jon's_Data'!A1:D5` WITHOUT doubling the embedded apostrophe - Google's own docs are inconsistent on exactly the apostrophe case. (3) gspread, the de facto Python Sheets client, resolves both: absolute_range_name() quotes UNCONDITIONALLY and doubles embedded quotes, with doctests pinning "'Sheet1'!A1" for a plain alphanumeric name and "'Sheet''1'" for an apostrophe, and its parser mirrors that with `'((?:[^']|'')+)'!` plus .replace("''", "'"). A library doing this against live Google at scale outweighs the docs example.

SO: quote unconditionally. The nuance that we quote nothing today cuts toward unconditional, not away from it - the quoted form is the documented sheet reference, so it cannot break a name that works unquoted, while a conditional predicate would be our own guess at Google's unenumerated special-character set.

CHANGES, criterion by criterion.
- #1 unchanged in substance; dropped the phrase "against the Sheets A1 notation documentation" because the decisive evidence turned out to be the SDK stubs and gspread, not the docs alone.
- #2 and #3 unchanged.
- #4 NEW: derived sheet titles have apostrophes removed, and the addSheet title plus the Group Name cell carry that same derived title unquoted. This is the human's decision, and it also pins the thing that is easy to get wrong - a sheet title is a literal title, not A1 notation, so quoting it would create a sheet whose name contains apostrophes.
- #5 was the old #4 (collision-safe truncation), WIDENED. Apostrophe removal is a second way two different group names can collapse onto one title, so the criterion now covers both causes, and it adds the determinism requirement: the same group name must resolve to the same title on every run. That rules out the builtin hash(), which is salted per process and would silently produce a different sheet title after every container restart.
- #6 REPLACED the old #5. The old text said the defect-probe assertion flips and "no other assertion needs to change". That is not achievable and was written before the research: unconditional quoting changes six range assertions, and the collision-safe title changes the truncation assertion. The new text draws the honest line - only A1-range and derived-title assertions change, each one is named in the Notes, and the respond messages, values matrix, call counts and call ordering stay untouched. That is still a checkable bar, and it is the bar that actually protects TASK-25.1.6.4/.8/.10.
- #7 was the old #6, unchanged.
---

created: 2026-09-02 19:45
---
PLAN APPROVED AS IS 2026-09-02 (human). Unconditional quoting, apostrophe-stripped derived titles, sha256-suffixed collision safety, and the replaced seven-criterion AC set all stand as written. Ready for tests-creation / implementation; status stays To Do until that work starts.

REASSESSMENT NOTE ATTACHED BY THE SAME APPROVAL. Revisit this fix when app/modules/reports/google_groups.py's consumer moves to the app/packages/<feature>/ architecture. Two things change shape at that point and neither is in scope now:

1. WHERE THE HELPERS LIVE. _sheet_title and _a1_range are module-private in a legacy app/modules/ file today purely because that is where the call site is. In the package world the natural home is the feature's Sheets adapter under app/packages/<feature>/adapters/, alongside the try/except plus classify_google_error boundary. If a second feature ever needs A1 quoting, _a1_range is the shared primitive to lift; _sheet_title is report-specific domain logic and should stay with the feature. Neither ever belongs in app/integrations/google_workspace/ - that is the deviation TASK-25.1.6 exists to close.

2. WHETHER THE DERIVED TITLE IS STILL THE RIGHT MODEL. The 50-character bound, the hash suffix and the apostrophe strip are all compensations for using a user-controlled display name as a sheet identifier. A feature package with a real domain type for a group could carry a stable identifier separately from the display label, which would make the suffix unnecessary and would let the Group Name cell show the full untruncated name - the open question already flagged in the plan and registered on TASK-25.1.6.10.

No task owns the reports-to-package migration today (grep of backlog/ finds none), so this is recorded here and on TASK-25.1.6.10 rather than filed as work. Whoever picks up that migration should read this before re-deriving the quoting rules from scratch; the evidence set (no A1 helper in googleapiclient or its stubs, the Sheets concepts page, gspread's absolute_range_name) is in this task's plan and references.
---
<!-- COMMENTS:END -->
