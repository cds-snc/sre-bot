---
id: TASK-25.2.1
title: >-
  Add characterization tests for the AWS call sites lacking unit coverage before
  adapter work
status: Done
assignee:
  - '@me'
created_date: '2026-07-31 18:48'
updated_date: '2026-09-11 16:41'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
references:
  - app/integrations/aws/client.py
  - app/modules/aws
  - app/modules/provisioning
  - app/modules/slack/webhooks.py
  - app/modules/incident/db_operations.py
  - app/modules/incident/incident_folder.py
  - app/jobs/scheduled_tasks.py
  - app/jobs/revoke_aws_sso_access.py
parent_task_id: TASK-25.2
priority: high
ordinal: 118000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 0 of TASK-25.2 (tests-only gate, mirrors TASK-25.1.6.1). Before adapters replace the False-swallowing integrations/aws mirrors, lock the current observable behaviour of each legacy call site, including what the caller does when the integration returns False today, so the switch to OperationResult in later slices shows up as an explicit, reviewable diff rather than a silent behaviour change.

Known coverage state (2026-09-11, starting point only; the planner re-greps it): tests/unit/modules/aws/* cover aws_access_requests, aws_account_health, identity_center, lambdas, ops_group_assignment and spending handlers; tests/unit/jobs/test_revoke_aws_sso_access.py exists; tests/unit/modules/provisioning has test_provisioning_users.py only (groups is covered by the legacy tests/modules/provisioning suite); modules/slack/webhooks.py and modules/incident/{db_operations,incident_folder}.py are covered only by legacy tests/modules suites and the webhooks e2e; jobs/scheduled_tasks.py's identity_store.healthcheck path and modules/aws/aws.py's get_user_id / get_account_id_by_name path have no targeted test.

Production code is not modified. New tests go under app/tests/ per the testing-standards skill, named test_<domain>_<entity>_<action>.py, with docstrings describing observable behaviour and stub strategy only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every production call into integrations.aws.{identity_store,organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas,dynamodb} has at least one unit test asserting the caller's success path and its behaviour when the integration returns False; the verified call-site inventory is recorded in notes
- [x] #2 No production file is modified; ruff, mypy and pytest pass with output recorded
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-11, re-grepped against current code; task-description prose lists were a starting point only)

Re-grep commands run: `rg -n "integrations\.aws" app --glob '!tests/**' modules jobs packages` and per-file reads of every hit plus `integrations/aws/client.py`. Confirmed `handle_aws_api_errors` (client.py:137-186) catches BotoCoreError/ClientError/Exception, logs, and always returns `False` (line 184) -- never None, never raises. `packages/access/sync/adapters/aws_identity_center.py` already calls `get_aws_client`/`classify_aws_error` directly (not through the mirrors) and is explicitly out of scope per TASK-25.2's access-feature scope note. `modules/aws/aws_access_requests.py`'s DynamoDB helpers (`already_has_access`, `create_aws_access_request`, `expire_request`, `get_expired_requests`, `get_active_requests`) use a private raw-boto3 client (`_get_dynamodb_client()`), NOT `integrations.aws.dynamodb` -- out of scope for this AC (no False-swallow to characterize there).

CALL-SITE INVENTORY (file:line -> integration fn -> today's False-path behaviour -> existing coverage)

Cluster A: config/cost_explorer/guard_duty/security_hub/organizations (account health + spending)
1. modules/aws/aws_account_health.py:53 cost_explorer.get_cost_and_usage -> indexes response["ResultsByTime"] unguarded -> CRASHES (TypeError) on False. Success: covered (test_aws_account_health_handler.py::test_should_get_account_spend_with_data). False: NOT covered.
2. modules/aws/aws_account_health.py:66 config.describe_aggregate_compliance_by_config_rules -> `len(response)` -> CRASHES on False. Success: covered. False: NOT covered.
3. modules/aws/aws_account_health.py:70 guard_duty.list_detectors -> `detector_ids[0]` -> CRASHES on False. Success: covered. False: NOT covered.
4. modules/aws/aws_account_health.py:78 guard_duty.get_findings_statistics -> indexes response["FindingStatistics"] -> CRASHES on False. Success: covered. False: NOT covered.
5. modules/aws/aws_account_health.py:105 security_hub.get_findings -> `if response:` -- DEFENDED, False -> issues=0 (same branch as [] already tested). Success: covered. False: covered by branch-equivalence with the existing empty-list test; skip.
6. modules/aws/aws_account_health.py:211 organizations.list_organization_accounts (request_health_modal) -> dict/list comprehension over accounts -> CRASHES on False. Success: covered (test_should_request_health_modal). False: NOT covered.
7. modules/aws/spending.py:40 organizations.list_organization_accounts (generate_spending_data) -> list comprehension -> CRASHES on False. Only exercised with organizations fully mocked to a success list; False NOT covered.
8. modules/aws/spending.py:61 organizations.get_account_details (get_accounts_details) -> `details["Tags"] = ...` -> CRASHES on False (item assignment on bool). NOT covered at all (existing spending tests mock get_accounts_details itself away).
9. modules/aws/spending.py:62 organizations.get_account_tags (get_accounts_details) -> assignment succeeds, but format_account_details' `for tag in account["Tags"]` CRASHES when Tags=False. NOT covered.
10. modules/aws/spending.py:79 cost_explorer.get_cost_and_usage (get_accounts_spending) -> `response.get(...)` -> CRASHES (AttributeError) on False. NOT covered.
11. modules/aws/ops_group_assignment.py:20 identity_store.get_group_id -> `if not aws_ops_group_id:` -- DEFENDED and False path already covered (test_should_return_failed_when_group_not_found).
12. modules/aws/ops_group_assignment.py:29 organizations.list_organization_accounts -> list comprehension over it -> CRASHES on False. NOT covered.
13. modules/aws/ops_group_assignment.py:30 sso_admin.list_account_assignments_for_principal -> set comprehension -> CRASHES on False. NOT covered.
14. modules/aws/ops_group_assignment.py:66 sso_admin.create_account_assignment -> `if success:` -- DEFENDED and covered (test_should_return_failed_when_assignment_fails).
15. modules/aws/lambdas.py:48/68 aws_lambdas.list_functions/list_layers -> `if response:` -- DEFENDED; existing tests use `[]`, which takes the identical branch as False. Skip (branch-equivalent, already characterized).

Cluster B: identity_store consumers (provisioning, identity_center, aws.py, aws_access_requests, revoke job)
16. modules/provisioning/users.py:58 identity_store.list_users (get_users_from_integration, "aws_identity_center" case) -> `log.info(..., users_count=len(users))` -> CRASHES on False (len(False) is TypeError; len([]) is NOT the same -- this is NOT branch-equivalent, unlike the `if x:` cases above). Existing test (test_provisioning_users.py:105-107) only uses a real list. NOT covered.
17. modules/provisioning/groups.py:142 identity_store.list_groups_with_memberships (get_groups_from_integration, "aws_identity_center" case) -> falls through to log_groups' `len(groups)` -> CRASHES on False. Existing tests (test_provisioning_groups.py:334-422) only use real lists. NOT covered.
18. modules/aws/identity_center.py:70,79 identity_store.list_users (synchronize) -> `len(target_users)` and passed to sync_users/sync_groups -> CRASHES on False. Existing tests (test_identity_center_handler.py) set `list_users.return_value = []`, not False -- same non-equivalence as #16. NOT covered.
19. modules/aws/aws.py:157-158 organizations.get_account_id_by_name / identity_store.get_user_id (request_aws_account_access) -> no guard at all, both flow unconditionally into `aws_access_requests.create_aws_access_request(...)`. ZERO test coverage exists for this function (confirmed: `rg request_aws_account_access` finds only its own definition). NOTE (found while grounding, NOT fixed here per the tests-only AC#2): the call passes args positionally as (account_id, account_name, user_id, user_email, start_date, end_date, access_type, rationale) but `create_aws_access_request`'s signature is (account_id, account_name, user_id, email, access_type, rationale, start_date_time=None, end_date_time=None) -- positions 5-8 are shifted, so `access_type` receives a datetime and `start_date_time` receives the access_type string. This function is also unreferenced anywhere in production (dead code; matches the "(currently disabled)" note in aws.py's own help text), so the test isolates identity_store/organizations usage by mocking `create_aws_access_request` itself and pins TODAY's (buggy) positional call shape rather than exercising the real DynamoDB write.
20. modules/aws/aws_access_requests.py:194 (access_view_handler) identity_store.get_user_id -> checked via `if aws_user_id is None:` -- but the integration returns `False` on error, never `None`, so this branch is DEAD CODE today: a get_user_id failure falls through into `already_has_access(...)` and then into `create_aws_access_request(...) and sso_admin.create_account_assignment(aws_user_id, ...)` with `aws_user_id=False`. ZERO coverage of access_view_handler exists (only that aws.py delegates to request_access_modal, in test_aws_command_handler.py). NOT covered.
21. modules/aws/aws_access_requests.py:241 (request_access_modal) organizations.list_organization_accounts -> dict comprehension over accounts -> CRASHES on False. NOT covered.
22. jobs/revoke_aws_sso_access.py:30 identity_store.get_user_id -> no guard, `False` flows unconditionally into `sso_admin.delete_account_assignment(False, account_id, access_type)`. Existing test `test_revoke_access_handles_identity_store_error` uses `side_effect = RuntimeError(...)`, which can never happen in production (the decorator swallows to False, never raises) -- it characterizes an impossible scenario, not today's real contract. NOT covered for the real False-return behaviour.
23. jobs/scheduled_tasks.py:128 identity_store.healthcheck -- SURPRISE: already adequately covered. `identity_store.healthcheck()` itself is fully tested for both its healthy and unhealthy (list_users returns [], same falsy branch as False) paths in tests/integrations/aws/test_identity_store.py::test_healtcheck_is_healthy/is_unhealthy. The generic per-key failure branch in `integration_healthchecks()` is already exercised with other integration keys failing (test_healthcheck_partial_failures, opsgenie/incident_drive=False) -- the loop is integration-name-agnostic, so adding an "aws key specifically fails" case would exercise no new code path. The parent task's "known coverage state" note about this call site is stale. No new test planned for #23; noted here as the required per-call-site disposition record.

Cluster C: dynamodb consumers (slack webhooks, incident db_operations, incident_folder)
24. modules/slack/webhooks.py:26 dynamodb.put_item (create_webhook) -> indexes response["ResponseMetadata"] unguarded -> CRASHES on False. Existing tests only use dict responses with good/bad HTTPStatusCode (test_create_webhook, test_create_webhook_with_type, test_create_webhook_return_none uses status 401, still a dict). NOT covered for the real False contract.
25. modules/slack/webhooks.py:48 dynamodb.delete_item (delete_webhook) -> pure pass-through, returns response unchanged. Only success-dict tested. False pass-through NOT covered.
26. modules/slack/webhooks.py:53 dynamodb.get_item (get_webhook) -> `if response:` -- DEFENDED; existing "no_result" test uses `{}`, same falsy branch as False. Skip (branch-equivalent).
27. modules/slack/webhooks.py:62 dynamodb.scan (lookup_webhooks) -> pure pass-through. Only success-list tested. NOT covered.
28. modules/slack/webhooks.py:70/80 dynamodb.update_item (increment_acknowledged_count/increment_invocation_count) -> pure pass-through. Only success-dict tested. NOT covered.
29. modules/slack/webhooks.py:90 dynamodb.scan (list_all_webhooks) -> pure pass-through. Only success-list tested. NOT covered.
30. modules/slack/webhooks.py:95 dynamodb.update_item (revoke_webhook) -> pure pass-through. Only success-dict tested. NOT covered.
31. modules/slack/webhooks.py:106 dynamodb.get_item (is_active) -- DEFENDED and ALREADY fully covered (True/False-active/not-found, 3 tests). Skip.
32. modules/slack/webhooks.py:118 toggle_webhook calls get_webhook(id) inline: `not get_webhook(id)["active"]["BOOL"]` -> get_webhook returns None on any falsy/False response -> `None["active"]` CRASHES. Existing test only mocks get_webhook to a valid dict. NOT covered.
33. modules/incident/db_operations.py:40 dynamodb.put_item (create_incident) -> indexes response["ResponseMetadata"] unguarded -> CRASHES on False. Existing failure test uses a 400-status dict, not False. NOT covered for the real contract.
34. modules/incident/db_operations.py:67 dynamodb.scan (list_incidents) -> pure pass-through. Only list/[] tested. NOT covered for False.
35. modules/incident/db_operations.py:90 dynamodb.update_item (update_incident_field) -- DEFENDED (`if response:`); existing failure test uses `None`, same falsy branch as False. Skip (branch-equivalent).
36. modules/incident/db_operations.py:108 dynamodb.update_item (log_activity) -- DEFENDED (`if response:`), not directly tested standalone but reached via create_incident's success path only; add a direct False-path test since log_activity's own False branch (returns False, logs error) is unexercised.
37. modules/incident/db_operations.py:138 dynamodb.get_item (get_incident) -> pure pass-through. Only success dict tested. NOT covered for False.
38. modules/incident/db_operations.py:158 dynamodb.scan (lookup_incident, reached from get_incident_by_channel_id) -> pure pass-through AND `get_incident_by_channel_id`'s `len(incidents) > 0` CRASHES on False. Existing "no_results" test uses `[]` (works fine), not False (crashes) -- NOT branch-equivalent, real gap.
39. modules/incident/incident_folder.py:546 dynamodb.update_item (store_update) -> `response.get("ResponseMetadata", {})...` -> CRASHES (AttributeError) on False. Existing `test_store_update_failed` uses a 400-status dict, not False. NOT covered for the real contract.

NEW/EXTENDED TEST FILES AND CASES

A. app/tests/unit/modules/aws/test_aws_account_health_handler.py (EXTEND)
   - test_should_raise_when_cost_explorer_returns_false (get_account_spend, cost_explorer.get_cost_and_usage=False, pytest.raises(TypeError))
   - test_should_raise_when_config_summary_integration_returns_false (get_config_summary, config...=False, pytest.raises(TypeError))
   - test_should_raise_when_guardduty_list_detectors_returns_false (pytest.raises(TypeError))
   - test_should_raise_when_guardduty_findings_statistics_returns_false (pytest.raises(TypeError))
   - test_should_return_zero_securityhub_when_integration_returns_false (get_securityhub_summary, security_hub.get_findings=False -> issues == 0; documents the existing defended branch explicitly with False, not just [])
   - test_should_raise_when_request_health_modal_organizations_call_returns_false (pytest.raises(TypeError))

B. app/tests/unit/modules/aws/test_spending_handler.py (EXTEND)
   - test_should_raise_when_list_organization_accounts_returns_false (generate_spending_data, organizations.list_organization_accounts=False, pytest.raises(TypeError))
   - test_should_raise_when_get_account_details_returns_false (get_accounts_details, organizations.get_account_details=False, pytest.raises(TypeError))
   - test_should_raise_when_get_account_tags_returns_false (get_accounts_details, get_account_details succeeds + get_account_tags=False, pytest.raises(TypeError) -- crash happens in format_account_details, not get_accounts_details itself; assert the raise propagates through get_accounts_details)
   - test_should_raise_when_cost_and_usage_returns_false (get_accounts_spending, cost_explorer.get_cost_and_usage=False, pytest.raises(AttributeError))

C. app/tests/unit/modules/aws/test_ops_group_assignment_handler.py (EXTEND)
   - test_should_raise_when_list_organization_accounts_returns_false (pytest.raises(TypeError))
   - test_should_raise_when_list_account_assignments_returns_false (pytest.raises(TypeError))

D. app/tests/unit/modules/aws/test_aws_access_requests_handler.py (EXTEND -- new section for the handler-level functions this file does not yet touch)
   - class-level fixture patching modules.aws.aws_access_requests.identity_store/.organizations/.sso_admin/.dynamodb_client as needed
   - test_should_treat_integration_false_as_not_none_and_proceed (access_view_handler; identity_store.get_user_id=False; asserts the "not registered" branch is NOT taken -- i.e. the `is None` check is pinned-not-fixed dead code -- and that create_aws_access_request/sso_admin.create_account_assignment are still invoked with aws_user_id=False; comment marks this as a pinned defect, not endorsed, per the precedent's convention)
   - test_should_respond_not_registered_message_never_fires_on_integration_failure (companion assertion on the chat_postEphemeral message text actually sent)
   - test_should_raise_when_request_access_modal_organizations_call_returns_false (pytest.raises(TypeError))

E. app/tests/unit/modules/aws/test_aws_command_handler.py (EXTEND -- request_aws_account_access lives in modules.aws.aws, this file's subject module)
   - test_should_pass_through_account_id_and_user_id_on_success (request_aws_account_access; identity_store.get_user_id and organizations.get_account_id_by_name mocked to real values; create_aws_access_request mocked; asserts call_args pins today's argument order/positions -- comment notes the positional-shift defect found while grounding, pinned not fixed)
   - test_should_proceed_with_false_account_id_when_organizations_lookup_fails (organizations.get_account_id_by_name=False; asserts create_aws_access_request is still called, no guard)
   - test_should_proceed_with_false_user_id_when_identity_store_lookup_fails (identity_store.get_user_id=False; same shape)

F. app/tests/unit/modules/aws/test_identity_center_handler.py (EXTEND)
   - test_should_raise_when_list_users_returns_false_before_sync (synchronize; identity_store.list_users=False on the first call; pytest.raises(TypeError) from len(target_users))

G. app/tests/unit/modules/provisioning/test_provisioning_users.py (EXTEND)
   - test_should_raise_when_aws_identity_store_list_users_returns_false (get_users_from_integration("aws_identity_center"); identity_store.list_users=False via monkeypatch as the existing style; pytest.raises(TypeError))

H. app/tests/modules/provisioning/test_provisioning_groups.py (EXTEND -- legacy tree, still collected under testpaths=["tests"]; groups.py has no app/tests/unit counterpart today per the parent task's coverage note)
   - test_get_groups_from_integration_case_aws_raises_when_integration_returns_false (identity_store.list_groups_with_memberships=False; pytest.raises(TypeError) from log_groups' len(groups))

I. app/tests/modules/slack/test_slack_webhooks.py (EXTEND -- legacy tree, natural home matching existing per-function test style)
   - test_create_webhook_raises_when_integration_returns_false (put_item=False, pytest.raises(TypeError))
   - test_delete_webhook_returns_false_unchanged (delete_item=False, assert result is False -- pins the pass-through contract)
   - test_lookup_webhooks_returns_false_unchanged (scan=False)
   - test_increment_acknowledged_count_returns_false_unchanged (update_item=False)
   - test_increment_invocation_count_returns_false_unchanged (update_item=False)
   - test_list_all_webhooks_returns_false_unchanged (scan=False)
   - test_revoke_webhook_returns_false_unchanged (update_item=False)
   - test_toggle_webhook_raises_when_get_webhook_returns_none_due_to_integration_failure (get_item=False so get_webhook returns None; pytest.raises(TypeError) on the inline `get_webhook(id)["active"]`)

J. app/tests/modules/incident/test_db_operations.py (EXTEND)
   - test_create_incident_raises_when_put_item_returns_false (pytest.raises(TypeError), contrasted with the existing 400-status-dict test)
   - test_list_incidents_returns_false_unchanged (scan=False)
   - test_get_incident_returns_false_unchanged (get_item=False)
   - test_lookup_incident_returns_false_unchanged (scan=False)
   - test_get_incident_by_channel_id_raises_when_lookup_incident_returns_false (pytest.raises(TypeError) from len(False), contrasted with the existing empty-list "no_results" test which does NOT crash)
   - test_log_activity_returns_false_and_logs_error_when_integration_returns_false (direct call, not just via create_incident's success path)

K. app/tests/modules/incident/test_incident_folder.py (EXTEND)
   - test_store_update_raises_when_update_item_returns_false (pytest.raises(AttributeError), contrasted with the existing 400-status-dict test)

L. app/tests/unit/jobs/test_revoke_aws_sso_access.py (EXTEND)
   - test_revoke_access_proceeds_with_false_user_id_when_identity_store_lookup_fails (identity_store.get_user_id.return_value = False, NOT a raised exception; asserts sso_admin.delete_account_assignment is still called with user_id=False, no guard, and the loop continues to expire_request/chat_postEphemeral -- this replaces reliance on the existing RuntimeError side_effect test as evidence of "error handling," since that scenario cannot occur in production)

DISPOSITION RECORD FOR "ALREADY ADEQUATE" CALL SITES (for the notes, satisfies AC#1's "verified call-site inventory" without adding redundant tests)
- #5, #15, #23, #26, #31, #35: existing tests already exercise the identical branch False would take (an `if x:`/`if not x:` truthy check where the existing falsy fixture -- `[]`, `{}`, `None` -- and `False` are behaviourally indistinguishable). No new test added; recorded here as the verification evidence.
- #14, #11: DEFENDED and already directly tested with False.

STUB STRATEGY
- Mirror each subject module's existing house style exactly (all of these already use `unittest.mock.patch`/`monkeypatch` on the module-level integration import, e.g. `@patch("modules.aws.aws_account_health.cost_explorer")`, `monkeypatch.setattr(users.identity_store, "list_users", ...)`); no new mocking library, no pytest-mock, no Protocol fakes -- these are legacy app/modules/* callers of plain function modules with no Protocol, matching the precedent's ACCEPTED rationale for MagicMock module doubles (decisions/testing.md last-choice double, accepted 2026-09-02 for this exact situation and carried forward here since nothing has changed).
- Patch the integration functions exactly as imported by each caller (`from integrations.aws import X` -> patch `modules.<path>.X.<fn>`), never `integrations.aws.client.execute_aws_api_call` or `handle_aws_api_errors` directly -- that boundary is what the later adapter slices (25.2.3-25.2.5) replace, so tests must pin the CALLER's contract, not the decorator's internals (those already have their own coverage in tests/integrations/aws/test_legacy_aws_client.py and tests/unit/integrations/aws/test_aws_client.py).
- Every new "returns False" case sets the mock's return value to the literal `False` (never `None`, `{}`, or `[]`) to match `handle_aws_api_errors`' actual contract; every crash case uses `pytest.raises(<ExactExceptionType>)` around the call, not a bare try/except, so the exact exception type is part of the pinned contract for the later OperationResult diff to visibly change.
- No `botocore.stub.Stubber`, no `moto` here -- those are reserved for the adapter unit tests in 25.2.3-25.2.5 per TASK-25.2's TESTS section; this gate stays at the caller/integration-module-mock boundary consistent with all the tests it extends.

VERIFICATION COMMANDS (run from app/, evidence recorded in notes)
- cd app && uv run ruff check .
- cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
- cd app && uv run pytest tests --ignore=tests/smoke
- git diff --stat (confirm zero non-test files changed, satisfying AC#2)

AC TRACEABILITY
- AC#1 (every call site has success + False-path coverage, inventory recorded in notes): satisfied by the 39-row inventory above plus the 12 new/extended test files (A-L) covering every NOT-covered row, and the disposition record for every row skipped as already-adequate. The verified inventory itself is the AC#1 deliverable and will be carried into the notes verbatim at finalization.
- AC#2 (no production file modified; gates pass with output recorded): satisfied by running the three verification commands and recording `git diff --stat` showing only app/tests/** paths, at finalization time (this plan authorizes no production edits).

ASSUMPTIONS AND HOW TO VERIFY THEM
- Assumes `handle_aws_api_errors` is the ONLY error boundary in play for every listed call site (i.e., no caller wraps the integration call in its own try/except that would change the exception type pinned above) -- verified by reading each caller function in full during grounding; re-verify at implementation time by running each new test once against the CURRENT (unmodified) code and confirming it fails for the right reason before the fix, or passes as a pin if no code changes are made (this is a characterization task, so tests should pass unmodified against today's code -- a red test here means the inventory's behavioural claim was wrong and must be re-derived from the real stack trace, not adjusted to force a pass).
- Assumes `tests/modules/**` (the legacy tree) is collected by `pytest tests --ignore=tests/smoke` -- verified directly: app/pyproject.toml:95 sets `testpaths = ["tests"]` with no marker-based exclusion of `legacy`, so plain collection includes it.
- Assumes the aws.py:130 `request_aws_account_access` positional-argument mismatch and the aws_access_requests.py:194 `is None` vs `is False` dead-branch are real, not misreadings -- verified by direct signature-vs-call-site comparison during grounding (documented inline above); flagged as pinned-not-fixed per AC#2, candidates for a follow-up fix task the human may want to create before 25.2.4/25.2.5 touch these files (same pattern as TASK-25.1.6.1's A1-quoting finding).

BLAST RADIUS AND ROLLBACK
- Zero production code changes; a `git revert` of this PR is always safe and trivially restores nothing-changed. The only risk is a mis-pinned characterization test asserting behaviour that isn't actually today's behaviour -- mitigated by running the new tests against the unmodified checkout before merging (see assumptions above) and by every crash-path test using `pytest.raises(<exact type>)` rather than a loose assertion.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Files changed (all under app/tests/, zero production files modified):
- tests/unit/modules/aws/test_aws_account_health_handler.py (+6 tests; 19 total)
- tests/unit/modules/aws/test_spending_handler.py (+4 tests; 17 total)
- tests/unit/modules/aws/test_ops_group_assignment_handler.py (+2 tests; 11 total)
- tests/unit/modules/aws/test_aws_access_requests_handler.py (+4 tests; 16 total)
- tests/unit/modules/aws/test_aws_command_handler.py (+3 tests; 13 total)
- tests/unit/modules/aws/test_identity_center_handler.py (+1 test; 15 total)
- tests/unit/modules/provisioning/test_provisioning_users.py (+1 test; 8 total)
- tests/modules/provisioning/test_provisioning_groups.py (+1 test; 19 total, legacy tree)
- tests/modules/slack/test_slack_webhooks.py (+8 tests; 27 total, legacy tree)
- tests/modules/incident/test_db_operations.py (+6 tests; 21 total, legacy tree)
- tests/modules/incident/test_incident_folder.py (+1 test; 42 total, legacy tree)
- tests/unit/jobs/test_revoke_aws_sso_access.py (+1 test; 6 total)
Total: 38 new tests across 12 files.

Call-site disposition (plan's 39-row inventory, file:line -> fn):
- Added now (crash pinned with pytest.raises or defended-branch/pass-through pinned with literal False): rows 1,2,3,4,6,7,8,9,10,12,13,16,17,18,19,20,21,22,24,25,27,28,29,30,32,33,34,36,37,38,39 -- all covered by the new tests above exactly as planned.
- Branch-equivalent, no new test (existing falsy fixture takes the identical `if x:`/`if not x:` branch as False): rows 5,11,14,15,26,31,35 -- verified by re-reading each guard during implementation, matches the plan's disposition record.
- Already adequate, no new test: row 23 (jobs/scheduled_tasks.py identity_store.healthcheck) -- confirmed already exercised via test_identity_store.py and the integration-agnostic healthcheck loop, per the plan's grounding note.

Behavioural claims corrected: none. Every planned exception type (TypeError/AttributeError) and every planned pass-through/defended-branch assertion matched today's real behaviour on first run; no test needed re-deriving from an actual stack trace.

Verification commands and results (run from app/):
- `uv run ruff check .` -> All checks passed!
- `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` -> 88 pre-existing errors in 32 production files (none in app/tests/, none in files touched by this task -- e.g. modules/incident/core.py, modules/webhooks/aws_sns_notification.py, packages/incident/scheduling/adapters/google_calendar.py); unrelated to this tests-only change, not fixed per the stop-condition on pre-existing unrelated gate failures.
- `uv run pytest tests --ignore=tests/smoke` -> 3294 passed, 6 failed. The 6 failures are in tests/modules/webhooks/test_webhooks_aws_sns.py (3 tests) and tests/unit/infrastructure/directory/test_google.py (3 tests) -- files this task never touches. Each of the 6 passes in isolation and as a pair-run; they only fail as part of the full ordered suite, indicating pre-existing full-suite state leakage unrelated to this change. Not fixed, per the stop-condition on pre-existing unrelated failures.
- Each of the 12 extended files was also run standalone; all pass (counts listed above).

Remaining for human: PR review of the 12 extended test files; optional decision on whether to open a follow-up investigation task for the pre-existing full-suite-only failures in test_webhooks_aws_sns.py / test_google.py (unrelated to TASK-25.2.1's scope) and for the two dead-code/positional-argument defects documented inline in the plan (aws.py request_aws_account_access positional shift; aws_access_requests.py access_view_handler's `is None` vs `is False` dead branch).

INDEPENDENT VERIFICATION OF THE GATE CLAIMS (2026-09-11, main session, after the implementation agent's run):
- ruff: `uv run ruff check .` -> All checks passed.
- mypy: `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` -> 88 errors in 32 production files. mypy excludes tests/ by config (pyproject [tool.mypy] exclude = ["^tests/"]), so a tests-only change cannot add or remove any of them; CI runs mypy non-blocking (`make lint-ci` appends `|| true`). Pre-existing, unrelated, not fixed.
- pytest, combined invocation `uv run pytest tests --ignore=tests/smoke` -> 3294 passed, 6 failed (3 in tests/modules/webhooks/test_webhooks_aws_sns.py, 3 in tests/unit/infrastructure/directory/test_google.py).
  Proof the 6 are pre-existing and independent of this change:
  (a) same invocation with all 12 modified test files excluded via --ignore -> the same 6 fail, 3080 passed;
  (b) each of the 12 modified files run ahead of the two failing files -> all pass (117-153 passed per pair);
  (c) CI-shaped splits are green: `pytest tests/unit tests/integration` -> 2475 passed; `pytest tests/api tests/modules tests/integrations tests/utils tests/test_factory_validation.py` (the make test-legacy list) -> 825 passed.
  The failures are an order-dependent state leak that only surfaces when the unit and legacy trees run in one process; candidate for a separate bug task, out of this slice's scope.
- Hygiene: rg over the 12 files finds no task ids, sprint labels or plan-step references; pinned-defect comments describe the defect and its revisit trigger in words.
<!-- SECTION:NOTES:END -->
