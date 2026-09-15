---
id: TASK-25.2.4.4
title: Migrate spending.py onto the Organizations and Cost Explorer adapters
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-15 15:26'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.1
  - TASK-25.2.4.2
references:
  - app/modules/aws/spending.py
  - app/tests/unit/modules/aws/test_spending_handler.py
  - app/modules/aws/aws.py
  - app/jobs/scheduled_tasks.py
  - app/packages/aws_platform/adapters/organizations.py
  - app/packages/aws_platform/adapters/cost_explorer.py
  - app/tests/unit/modules/aws/test_aws_command_handler.py
  - app/tests/unit/jobs/test_scheduled_tasks.py
  - >-
    backlog/tasks/task-93 -
    Replace-spending.pys-hard-coded-USD-to-CAD-rates-with-AWS-invoice-exchange-rates.md
parent_task_id: TASK-25.2.4
priority: high
ordinal: 203000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2b of TASK-25.2.4. Migrate modules/aws/spending.py off the legacy integrations.aws.organizations and integrations.aws.cost_explorer mirrors onto the adapters landed by TASK-25.2.4.1/.2 (build_organizations_adapter(), build_cost_explorer_adapter() from packages/aws_platform/adapters/), following the caller idiom landed by TASK-25.2.4.3 in modules/aws/ops_group_assignment.py (explicit non-success branch logging status/error_code/error). No adapter or providers.py changes.

Call sites (read 2026-09-15):
- organizations.list_organization_accounts() (spending.py:40): a False return crashes the list comprehension (TypeError, pinned by TASK-25.2.1).
- organizations.get_account_details(id) (spending.py:61): a False return crashes `details["Tags"] = ...` (TypeError).
- organizations.get_account_tags(id) (spending.py:62): a False return crashes format_account_details' tag loop (TypeError).
- cost_explorer.get_cost_and_usage(...) (spending.py:79): a False return crashes `response.get("ResultsByTime")` (AttributeError). The adapter follows NextPageToken and returns the concatenated ResultsByTime list as data.

Error policy (human decision 2026-09-15): Sheet1 is fully replaced on every write, so a partial report must never overwrite it. Any non-success from list_organization_accounts, get_account_details or get_cost_and_usage (any month) aborts the run: logged, generate_spending_data returns None, nothing is written. A non-success from get_account_tags degrades that account to Product/Business Unit "Unknown" (the existing untagged fallback), logged, and its costs stay in the report.

Bugs in touched code, fixed simply (human decisions 2026-09-15):
(a) Cost Explorer TimePeriod.End is exclusive; End = last day of month drops each month's last day. Use the first day of the next month.
(b) An empty account list or empty spending data makes pd.merge(on="Linked account") raise KeyError (verified). Return an empty DataFrame instead.
(c) The nightly scheduler job (jobs/scheduled_tasks.py:108-111) calls spending.generate_spending_data(logger=logger): TypeError every night (the function takes no args), swallowed by safe_run, and it would never write the sheet anyway. Confirmed in production logs: safe_run_error "generate_spending_data() got an unexpected keyword argument 'logger'" (function=wrapped, arguments={logger: ...}) at 2026-09-14T00:00:00Z. Point it at spending.execute_spending_data_update_job with no kwargs, keeping the lease key.
(d) The `/aws spending` Slack command (modules/aws/aws.py:101-111) ignores update_spending_data's bool and always replies "updated". Reply with a bilingual failure message when the write fails, and treat an empty DataFrame like None so an empty report never wipes the sheet.

Out of scope: replacing the hard-coded `rates` table (last entry 2025-03, fallback rate used since) with AWS invoice exchange rates is tracked separately in TASK-93 (human decision 2026-09-15: this task stays focused on leaving the legacy mirrors).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/spending.py no longer imports integrations.aws.organizations or integrations.aws.cost_explorer; list_organization_accounts, get_account_details, get_account_tags and get_cost_and_usage are called through build_organizations_adapter() / build_cost_explorer_adapter() and branch on OperationResult explicitly
- [ ] #2 A non-success result from list_organization_accounts, get_account_details or get_cost_and_usage (any month) is logged with status, error_code and error and makes generate_spending_data return None without raising; execute_spending_data_update_job logs a failed run and writes nothing. The four pinned crash tests in tests/unit/modules/aws/test_spending_handler.py are replaced by tests of this behaviour
- [ ] #3 A non-success result from get_account_tags is logged and that account is kept with Product and Business Unit set to Unknown
- [ ] #4 Cost Explorer is queried with End set to the first day of the following month (exclusive end), and an empty account list or empty spending data yields an empty DataFrame instead of a KeyError
- [ ] #5 The nightly scheduler entry runs spending.execute_spending_data_update_job with no extra kwargs under the existing scheduler:spending_generate_spending_data lease key
- [ ] #6 The /aws spending Slack command replies with a bilingual failure message when generate_spending_data returns None or an empty DataFrame, or when update_spending_data returns False
- [ ] #7 Per-call-site error-path behaviour (one line per call site) is recorded in the task notes for review
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-15): app/modules/aws/spending.py (225 LOC); its production callers app/modules/aws/aws.py:101-111 (/aws spending) and app/jobs/scheduled_tasks.py:108-111 (nightly Tier-2 job); app/packages/aws_platform/adapters/organizations.py (list_organization_accounts -> OperationResult[list[dict]] :97, get_account_details -> OperationResult[dict] :101, get_account_tags -> OperationResult[list[dict]] :110) and cost_explorer.py (get_cost_and_usage -> OperationResult[list[dict]] with NextPageToken followed internally, kwarg filter_expression, :75); the landed TASK-25.2.4.3 caller idiom in app/modules/aws/ops_group_assignment.py:49-61; app/tests/unit/modules/aws/test_spending_handler.py (15 tests, 4 pinned crash tests at :320-385); test_aws_command_handler.py:186-229; test_scheduled_tasks.py:340-362. Verified empirically: pd.merge on an empty accounts or spending DataFrame raises KeyError('Linked account'); Timestamp + MonthBegin(1) gives the first day of the next month, including February and December.

ALIGNMENT WITH SIBLINGS
- Use only the landed factories (no adapter, providers.py or settings changes). Build each adapter once per run inside generate_spending_data (eager AssumeRole, never at import) and pass it into the helpers, so a 12-month run does one AssumeRole per service instead of one per account or month.
- Same logging shape as .3: event name plus status=result.status.value, error_code, error=result.message.
- Unmapped ClientErrors, programmer errors and AssumeRole failures at build time propagate, as in .3. The scheduler's safe_run logs them, and the Slack command raises as today for build-time failures (pre-existing pattern).
- .5 (aws_account_health.py) and .6 are untouched. .7 still deletes the mirrors: after this task, aws_account_health.py is the only user of the organizations and cost_explorer mirrors.

STEPS
1. Tests first (red), app/tests/unit/modules/aws/test_spending_handler.py:
   - Re-stub test_should_generate_spending_data_successfully: patch modules.aws.spending.build_organizations_adapter / build_cost_explorer_adapter (MagicMock adapters returning OperationResult.success) instead of the removed module attributes.
   - Replace the 4 crash tests and add new ones (see TEST MATRIX).
   - app/tests/unit/modules/aws/test_aws_command_handler.py: add update-failure and empty-DataFrame reply tests.
   - app/tests/unit/jobs/test_scheduled_tasks.py: assert the spending lease key wraps spending.execute_spending_data_update_job and that its .do() call gets no kwargs.
2. app/modules/aws/spending.py (AC#1-#4):
   - Imports: drop `from integrations.aws import cost_explorer, organizations`. Add build_organizations_adapter, build_cost_explorer_adapter (and the adapter classes for type hints).
   - generate_spending_data() -> DataFrame | None: build both adapters. On a non-success list_organization_accounts, log aws_accounts_list_failed and return None. Then accounts = get_accounts_details(organizations_adapter, ids) and spending = get_accounts_spending(cost_explorer_adapter, year, month); if either is None, return None. If accounts is empty or spending_df is empty, log a warning and return pd.DataFrame(), skipping the merge (bug b). Otherwise merge and convert as today.
   - get_accounts_details(adapter, ids) -> list[dict] | None: on a non-success get_account_details, log aws_account_details_failed (account_id, status, error_code, error) and return None (abort). On a non-success get_account_tags, log aws_account_tags_failed and use Tags=[], which gives Unknown/Unknown through format_account_details. Build a new dict ({**details, "Tags": tags}) rather than mutating result.data.
   - get_accounts_spending(adapter, year, month, span=12) -> list[dict] | None: End = (start_date + pd.offsets.MonthBegin(1)) (bug a). Call adapter.get_cost_and_usage(same args). On non-success, log aws_cost_and_usage_failed (start, end, status, error_code, error) and return None. Otherwise results.extend(result.data or []). spending_to_df already iterates every entry's Groups, so a TimePeriod repeated across pages is fine.
   - execute_spending_data_update_job: if spending_data is None, log warning status="failed", message="Spending data generation failed", and return before the existing empty check.
3. app/jobs/scheduled_tasks.py:108-111 (AC#5): `schedule.every().day.at("00:00").do(safe_run(_tier2("scheduler:spending_generate_spending_data", spending.execute_spending_data_update_job)))`. Drop `logger=logger`. Keep the lease key so a rolling deploy can't run the job twice across replicas, and so the existing key-set test is unchanged.
4. app/modules/aws/aws.py:101-111 (AC#6): `if spending_df is None or spending_df.empty:` gives the existing failure reply. Then `if not spending.update_spending_data(spending_df):` gives a bilingual failure reply ("Failed to update spending data. Please try again later.\nÉchec de la mise à jour des données de dépenses. Veuillez réessayer plus tard.") and returns. Otherwise the success reply as today.
5. Gates from app/: ruff, mypy (baseline 87 errors in 31 files, none added in touched files), pytest tests --ignore=tests/smoke (known 6 order-dependent failures in SNS/google-directory).
6. Notes (AC#7): one line per call site, plus the gate evidence. Check ACs one by one as each is verified.

TEST MATRIX (test_spending_handler.py unless noted; adapter factories patched with MagicMocks returning OperationResult, following the .3 precedent; Stubber stays reserved for adapter tests)
- Happy: generate_spending_data merges accounts and spending into a non-empty DataFrame with Converted Cost (re-stubbed existing test). [AC#1]
- Failure: list_organization_accounts non-success -> returns None, logs aws_accounts_list_failed with status/error_code/error, get_account_details and get_cost_and_usage not called. Replaces test_should_raise_when_list_organization_accounts_returns_false. [AC#2]
- Failure: get_account_details non-success -> get_accounts_details returns None and logs; generate_spending_data returns None and never calls Cost Explorer. Replaces the get_account_details crash test. [AC#2]
- Failure: get_cost_and_usage non-success on the second month -> get_accounts_spending returns None after exactly 2 calls; generate_spending_data returns None. Replaces the cost_and_usage crash test. [AC#2]
- Failure: execute_spending_data_update_job with generate returning None -> logs status="failed", update_spending_data not called. [AC#2]
- Degrade: get_account_tags non-success -> the account is returned with Product="Unknown" and Business Unit="Unknown", and the failure is logged. Replaces the get_account_tags crash test. [AC#3]
- Boundary: get_accounts_spending(adapter, "2025", "01", span=2) passes time_period {Start 2025-01-01, End 2025-02-01} then {Start 2024-12-01, End 2025-01-01}; also February End 2024-03-01. [AC#4]
- Boundary: result.data from several entries (same TimePeriod, different Groups) is concatenated and flattened into one row per group. [AC#4]
- Boundary (parametrized): no accounts / no spending rows -> generate_spending_data returns an empty DataFrame, no KeyError. [AC#4]
- Scheduler regression (test_scheduled_tasks.py): the _tier2 call with the spending lease key receives spending.execute_spending_data_update_job. Invoking the callable registered through .do() with the exact args/kwargs .do() received (spending.execute_spending_data_update_job patched, lease store faked so the job runs) calls the job once with no arguments and logs no safe_run_error. This reproduces the production log "generate_spending_data() got an unexpected keyword argument 'logger'" and fails on today's code. [AC#5]
- Slack (test_aws_command_handler.py): update_spending_data returns False -> second respond says "Failed", no "has been updated" reply; generate returns an empty DataFrame -> failure reply, update not called. The existing None test stays. [AC#6]

ASSUMPTIONS / DOUBTS (verify during implementation)
- Cost Explorer accepts an End in the future for the current month (today's code already sends month-end, which is also in the future, so the risk is unchanged). Verify against the GetCostAndUsage docs.
- Only aws.py and scheduled_tasks.py call spending helpers in production. Re-grep `rg -n "get_accounts_details|get_accounts_spending|generate_spending_data" app --glob '!**/.venv/**'` before changing signatures.
- Enabling the nightly job assumes the scheduler runtime has the same organizations/ce role access and spending_sheet_id config as the Slack command. If spending_sheet_id is empty, update_spending_data already logs and returns False (harmless).

BLAST RADIUS AND ROLLBACK
- Behaviour change on merge: the nightly 00:00 job starts overwriting Sheet1 with 12 months of data every night (12 GetCostAndUsage calls at about $0.01 each, plus 2 Organizations calls per account). Before, it silently did nothing. The abort-on-failure policy prevents a partial overwrite.
- Worst case if wrong: the sheet is not refreshed (logged), or the Slack command replies "failed" for a run that did write. There is no data loss beyond today's full Sheet1 replacement.
- A single git revert restores prior behaviour. No settings, env, terraform or ordering constraints.

SIZE ESTIMATE AND GATE VERDICT
- Production: 3 files (spending.py about 50 changed LOC, aws.py about 8, scheduled_tasks.py about 3), about 60 LOC, one subsystem (legacy modules/aws plus its scheduler wiring). No mechanical refactor is mixed in: the helper signature changes are part of the behaviour change and have no outside callers.
- Tests: 3 files (not gated).
- VERDICT: well under the gate. One PR.

OPEN QUESTIONS FOR HUMAN REVIEW
None. The error policy, tags degradation, scheduler fix and Slack reply fix were decided 2026-09-15.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Candidate bugs verified 2026-09-14 during TASK-25.2.4.1 planning (organizations/sso_admin scope); these are owned by .4.4 (spending.py), not .1:

1. CONFIRMED - Cost Explorer TimePeriod.End is exclusive (AWS docs: 'The end date is exclusive... retrieves cost and usage data up to, but not including, end'). spending.py:73-77 sets end_date = start_date + pd.offsets.MonthEnd(1) (the last calendar day of the month) as TimePeriod.End, so the last day of every month's cost is silently dropped from the report. Simple fix when migrating onto the Cost Explorer adapter: pass end_date + 1 day (first day of the next month) as End.

2. CONFIRMED - spending.py:40 `account_ids = [account["Id"] for account in organizations.list_organization_accounts()]` crashes with TypeError if list_organization_accounts() returns the legacy False-on-error sentinel (handle_aws_api_errors). Already covered by TASK-25.2.4 AC#4 (crash-on-False sites); citing the exact line here for traceability - handle it as one of the 4 spending.py sites when migrating onto the Organizations adapter's OperationResult.

3. CONFIRMED - spending.py:61-63 `details = organizations.get_account_details(id); account_tags = organizations.get_account_tags(id); details["Tags"] = account_tags` mutates `details` without checking it for False first; if get_account_details errors, details is False and `details["Tags"] = ...` raises TypeError, aborting the whole account batch. Same AC#4 crash-on-False class; fold into the OperationResult migration (check organizations_adapter.get_account_details(id).is_success before building the Tags dict).

4. CONFIRMED, cross-referenced on TASK-25.2.4.2 - spending.py:79-88 calls Cost Explorer get_cost_and_usage in a single call per month with no NextPageToken handling. get_cost_and_usage has no boto3 paginator (manual token loop required, confirmed via AWS/boto3 docs), so a response with more than one page silently drops results. The Cost Explorer adapter built in .4.2 needs a manual NextPageToken loop; when migrating spending.py onto it in .4.4, verify the adapter already loops and that spending.py doesn't need its own workaround.

Cross-reference from TASK-25.2.4.2 planning (2026-09-14): the Cost Explorer adapter (packages/aws_platform/adapters/cost_explorer.py, build_cost_explorer_adapter) follows NextPageToken internally and returns OperationResult[list[dict]] holding the concatenated ResultsByTime entries, not the raw response. Replace response.get('ResultsByTime', []) at spending.py:88 with result.data. With GroupBy, one TimePeriod can repeat across pages carrying different Groups, so iterate every entry's Groups; don't assume one entry per month. The filter argument is named filter_expression. No pagination workaround is needed in spending.py (resolves candidate bug #4).

Planning 2026-09-15 (human decisions):
- Error policy: abort the whole run (no sheet write) on a non-success from list_organization_accounts, get_account_details or get_cost_and_usage, because Sheet1 is fully replaced on each write. get_account_tags failure degrades the account to Unknown/Unknown instead.
- Fix the nightly scheduler job in this task: it passed logger= to the no-arg generate_spending_data (TypeError every night, swallowed by safe_run) and never wrote the sheet. It now runs execute_spending_data_update_job under the same lease key.
- Fix /aws spending ignoring update_spending_data's result in this task.
- Scope therefore grows from spending.py alone to spending.py + aws.py + scheduled_tasks.py (about 60 prod LOC). ACs were rewritten: 4 call sites confirmed crash-on-False; tags-degradation, end-date/empty-merge, scheduler and Slack-reply ACs added; per-call-site notes kept as the last AC.
- Candidate bug #4 (pagination) is resolved by the .4.2 adapter. Bug #1 (exclusive End) is AC#4. Bugs #2/#3 are AC#2.

Planning follow-up 2026-09-15:
- Production log from 2026-09-14T00:00:00Z confirms bug (c): safe_run_error "generate_spending_data() got an unexpected keyword argument 'logger'" from the _tier2 wrapper. AC#5 covers it. The scheduler test now calls the registered job with .do()'s real args/kwargs, so it reproduces this failure.
- Exchange rates: researched and split out to TASK-93 (Invoicing API ListInvoiceSummaries CurrencyExchangeDetails.Rate; payer invoiced in CAD). Human decision: not part of this migration; spending may be rearchitected when it moves to packages/aws_platform.

Failing tests authored 2026-09-15 (no production code changed):
- tests/unit/modules/aws/test_spending_handler.py: the happy path now stubs build_organizations_adapter / build_cost_explorer_adapter. The 4 pinned crash tests are replaced by: account-list failure, account-details failure, Cost Explorer failure (helper stops after the failing month; generation returns None), tags failure degrading to Unknown, and execute job logging a failed run on None. New boundary tests: exclusive End (year rollover, leap February), several result entries per month, and empty accounts/spending giving an empty DataFrame (parametrized). Log assertions match events by name on the patched module logger (aws_accounts_list_failed, aws_account_details_failed, aws_account_tags_failed, aws_cost_and_usage_failed, each with status/error_code/error), whether logged on the logger or a bound child.
- tests/unit/jobs/test_scheduled_tasks.py: test_init_daily_spending_job_runs_update_job_without_arguments runs each daily .do() registration with its recorded args/kwargs through the real _tier2 and an in-memory lease store, with spending functions autospecced from the real signatures. It reproduces the production "unexpected keyword argument 'logger'" failure.
- tests/unit/modules/aws/test_aws_command_handler.py: added sheet-write-failure and empty-DataFrame reply tests. Minimal edit to the existing success test: it now uses a real non-empty DataFrame and update returns True, because a MagicMock's .empty is truthy.
- Helper signatures the tests expect: get_accounts_details(organizations_adapter, ids) and get_accounts_spending(cost_explorer_adapter, year, month, span=12); get_cost_and_usage is called with time_period as a keyword.

Red-state evidence (from app/):
- uv run pytest tests/unit/modules/aws/test_spending_handler.py tests/unit/jobs/test_scheduled_tasks.py tests/unit/modules/aws/test_aws_command_handler.py -> 15 failed, 41 passed. Every failure is the intended one: missing adapter factories, old helper signatures, None.empty AttributeError, the update job not called, the "updated" reply on a failed write, and update called on an empty DataFrame.
- uv run ruff check / ruff format --check on the 3 files -> All checks passed, 3 files already formatted.
- uv run mypy on the 3 files -> 4 errors in test_spending_handler.py (lines 449, 481, 540, 561: the new helper signatures, which clear on implementation). The remaining errors are existing ones in modules/ followed through imports.
<!-- SECTION:NOTES:END -->
