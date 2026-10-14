---
id: TASK-27.3
title: >-
  Records slice 3: the CI fake-coverage check over hosting contracts and
  capability api.py Protocols
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-16 13:58'
updated_date: '2026-10-14 14:41'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies:
  - TASK-27.1
  - TASK-106
references:
  - decisions/cloud-portability.md
  - decisions/dependency-injection.md
  - app/bin/check_vendor_package_contract.py
  - app/infrastructure/idempotency/factory.py
  - decisions/plugin-architecture.md
parent_task_id: TASK-27
priority: medium
ordinal: 221000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-27, rescoped 2026-09-24 to decisions/plugin-architecture.md and cloud-portability.md (contract 4). The fake contract covers two kinds of Protocol:
- hosting contracts: Protocols in app/contracts/ implemented in app/infrastructure/ (records, coordination, queue, secrets);
- capability api.py Protocols that face an external system (directory, drive, spreadsheets, audit, people, approvals).
It does not cover feature Path B adapters or in-process mechanisms (logging, the plugin manager).

What moved out of this slice:
- The shared in-memory DirectoryProvider is built by TASK-119 when directory moves to app/capabilities/directory/, and the audit fake by TASK-122 when audit moves to app/capabilities/audit/. Building them in app/infrastructure/ first would move them twice.
- The former AC to give infrastructure/records/ a cached factory.py provider is dropped. decisions/dependency-injection.md replaces cached provider functions with the service registry (TASK-109), so that shape would be built and then deleted.

Remaining scope:
- wire the CI fake-coverage check. It fails the build when a Protocol in app/contracts/ that has an app/infrastructure/ implementation, or an externally facing capability api.py Protocol, has no in-memory fake exercised by tests. It reads the package tree, not app/tests/, and names its excluded in-process mechanisms explicitly.
- Follow the app/bin guardrail shape: a script, a make target, a listed exclusion set.

Reference shape from TASK-27.1: the records fake is app/infrastructure/records/in_memory.py (InMemoryRecordStore, alongside infrastructure/idempotency/in_memory.py), and tests/integration/infrastructure/records/test_records_store_query_conformance.py runs one set of cases parametrized over the fake and the moto-backed DynamoDB store. The check should recognise an in_memory.py module in the implementation package plus a conformance suite parametrized over fake and real implementations as satisfying the contract.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A CI check (app/bin/check_fake_coverage.py, make check-fake-coverage, a ci_code.yml step) fails the build when a covered Protocol has no fake: a class in an in_memory.py module under app/infrastructure/ or app/capabilities/ that explicitly subclasses it; it reads the package tree, not app/tests/
- [x] #2 Coverage is decided by structural rule, not an exclusion list: an app/contracts/ Protocol when an app/infrastructure/ class explicitly subclasses it (uncovered registrars and extension points are printed), a capability api.py Protocol when its adapters/ explicitly subclass it, any Protocol still defined in app/infrastructure/ until it moves; features/, packages/ and capability adapters/ are never scanned, so feature Path B adapters are out by rule
- [x] #3 Known gaps sit in a ratchet-down baseline, each entry naming the task that retires it (audit TASK-122, directory TASK-119, drive TASK-120, spreadsheets TASK-121, RetryStore and RetryProcessor TASK-59)
- [x] #4 Conformance suites pass against fake and real implementations for RecordStore and IdempotencyStore, and an enrollment test fails when a concrete production subclass is missing from the suite's fixture; DynamoDBRecordStore explicitly subclasses RecordStore
- [x] #5 decisions/cloud-portability.md Checks names the check, the structural rule and the explicit-subclass requirement
- [x] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass, with the commands and their output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decisions (agreed in session 2026-10-14)
- Scope: end-state locations plus Protocols still defined in app/infrastructure/ (hosting contracts not yet moved). That part empties itself as TASK-108/119/120/121/122 move them out.
- Coverage rule (structural, Backstage/Go CDK/Dapr driven-port line; no exclusion list): a Protocol needs a fake when a driven adapter explicitly subclasses it:
  - app/contracts/** Protocol: covered when an app/infrastructure/ class explicitly subclasses it. Registrars and extension points (plugins, i18n, scheduler, Slack) are implemented by the host and fall out by rule; the check prints them as "not covered: no infrastructure implementation".
  - app/capabilities/<c>/api.py Protocol: covered when a class under app/capabilities/<c>/adapters/ explicitly subclasses it.
  - Protocol defined anywhere under app/infrastructure/: covered by location (transitional).
  - features/, packages/, integrations/ and capability adapters/ are never scanned, so feature Path B adapters are out by rule.
- Evidence of a fake: a class in an in_memory.py module under app/infrastructure/ or app/capabilities/ that explicitly subclasses the Protocol (typing spec / mypy idiom; mypy proves conformance). Evidence it is exercised: each conformance fixture gets an Ibis-style enrollment test asserting its params cover every concrete production subclass of the Protocol.
- Known gaps go in a freeze baseline (ratchets down), each line commented with the task that retires it: AuditTrailService TASK-122, DirectoryProvider TASK-119, DriveProvider TASK-120, SpreadsheetProvider TASK-121, RetryStore and RetryProcessor TASK-59.

Steps (TDD)
1. Failing tests first:
   - app/tests/unit/bin/test_bin_fake_coverage_check.py, tmp_path trees + monkeypatched roots, mirroring test_bin_vendor_package_contract_check.py: contracts Protocol subclassed in infrastructure with/without in_memory.py fake; fake outside in_memory.py or structural-only fails; contracts Protocol with no infrastructure subclass is not covered and is printed; capability api.py Protocol subclassed in adapters/ with/without fake; infrastructure-defined Protocol covered by location; features/, packages/ and adapters/ Protocols ignored; `typing.Protocol` attribute form and PEP 695 `class X[T](Protocol)` detected; baselined gap passes, stale entry is INFO only; committed baseline entries each carry an owning task and the real tree passes.
   - Enrollment tests: tests/integration/infrastructure/records/test_records_store_conformance_enrollment.py and tests/integration/infrastructure/idempotency/test_idempotency_store_conformance_enrollment.py, using a small helper tests/fixtures/conformance.py (concrete subclasses of a Protocol whose module is under infrastructure./capabilities.). The records one fails until DynamoDBRecordStore subclasses RecordStore.
   - Verify assumptions in the first run: RecordStore and IdempotencyStore pass the rule as they are; the only infrastructure gaps are the six above; no contracts Protocol is subclassed in infrastructure today.
2. app/bin/check_fake_coverage.py: AST only, freeze_guard helpers (iter_python_files, load_baseline, report), entries "<app-relative module>:<Protocol>", main() -> int. Baseline app/bin/baselines/fake_coverage.txt.
3. infrastructure/records/service.py: class DynamoDBRecordStore(RecordStore). Records and idempotency conftests: fixture params come from one id -> class mapping exposed as a fixture the enrollment test reads (no conftest import).
4. Wiring: Makefile .PHONY + check-fake-coverage target; .github/workflows/ci_code.yml step after the import-contract check; freeze_guard.py consumers line.
5. decisions/cloud-portability.md Checks: name `make check-fake-coverage`, the structural rule and the explicit-subclass requirement for driven adapters and fakes; the gaps line points at the baseline.
6. Gates: ruff, mypy (touched files), pytest tests --ignore=tests/smoke, make check-fake-coverage.

Size: ~180 production LOC (script, baseline, wiring, one-line subclass), ~12 small files, one subsystem (CI guardrails + their conformance suites); no behavior change in app code.
Downstream: TASK-108 must keep InMemoryRecordStore/DynamoDBRecordStore subclassing contracts RecordStore; TASK-119/120/121/122/138/25.10/146.1 adapters subclass their api.py Protocol and ship in_memory.py; TASK-34 queue the same.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed
- app/bin/check_fake_coverage.py (new): AST-only freeze-baseline guard on bin/freeze_guard.py. Reads contracts/, capabilities/*/api.py (+ adapters/) and infrastructure/, never app/tests/. Coverage follows the driven-port rule agreed in planning: a contracts Protocol when an infrastructure class explicitly subclasses it; a capability api.py Protocol when its own adapters/ subclass it; any Protocol still defined in infrastructure/ by location. A fake is a class in an in_memory.py under infrastructure/ or capabilities/ that explicitly subclasses the Protocol. Uncovered contracts Protocols (the 5 registrars/extension points/reply sender) are printed as INFO.
- app/bin/baselines/fake_coverage.txt (new): 6 gaps, each with its retiring task: AuditTrailService TASK-122, DirectoryProvider TASK-119, DriveProvider TASK-120, SpreadsheetProvider TASK-121, RetryStore and RetryProcessor TASK-59.
- Wiring: app/Makefile check-fake-coverage target + .PHONY; .github/workflows/ci_code.yml step after the import-contract check; bin/freeze_guard.py consumers line (also adds the previously missing check_aws_platform_seam.py).
- Enrollment (Ibis style): tests/fixtures/conformance.py concrete_production_subclasses(); records and idempotency conftests now build their parametrized fixtures from one implementation -> fixture mapping exposed as record_store_implementations / idempotency_store_implementations; new test_records_store_conformance_enrollment.py and test_idempotency_store_conformance_enrollment.py.
- infrastructure/records/service.py: DynamoDBRecordStore explicitly subclasses RecordStore (mypy-verified conformance; the records enrollment test failed before this).
- decisions/cloud-portability.md Checks: names the check, the structural rule, the explicit-subclass requirement and the baseline; Changes entry 2026-10-14.

Assumptions verified in the first failing run: RecordStore and IdempotencyStore satisfy the rule unchanged; the real-tree gaps are exactly the six baselined; no contracts Protocol is subclassed in infrastructure today; 107 existing records/idempotency conformance cases stayed green after the fixture refactor.

Evidence
- cd app && uv run ruff check . -> All checks passed!; uv run ruff format --check . -> 902 files already formatted
- cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 48 errors in 19 files (checked 398 source files); 0 in touched files (pre-existing, outside scope)
- cd app && uv run pytest tests --ignore=tests/smoke -> 4779 passed, 2627 warnings in 118.08s
- cd app && make check-fake-coverage -> OK: every covered Protocol has an in-memory fake (6 baselined gap(s) remain).

For the human
- Confirm the new CI step runs green on the PR.
- Downstream: TASK-108 must keep InMemoryRecordStore and DynamoDBRecordStore subclassing contracts RecordStore (the check then covers it by the contracts rule); TASK-119/120/121/122/138/25.10/146.1 adapters must explicitly subclass their api.py Protocol and ship in_memory.py; each closing task removes its baseline line.
<!-- SECTION:NOTES:END -->
