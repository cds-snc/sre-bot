---
id: TASK-76.4
title: Strip managed-group policy and settings out of infrastructure directory
status: To Do
assignee: []
created_date: '2026-09-04 14:19'
updated_date: '2026-09-04 14:25'
labels:
  - layering
milestone: m-3
dependencies:
  - TASK-76.3
parent_task_id: TASK-76
priority: medium
ordinal: 151000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-76, the subtractive cleanup that satisfies parent AC#1 and AC#2 (see the coordinator plan, decisions D2, D3). Infrastructure-only; safe because TASK-76.3 already moved every access consumer off this behaviour.

DELETE from app/infrastructure/directory/google.py:
- _extract_managed_group_email (269-285), _managed_group_query_prefix (286-305), _matches_managed_group_prefix (306-313), _build_managed_group (453-493).
- The _managed_group_domain and _managed_group_prefix instance attributes (constructor, 67-68).
- The strategy switch in list_groups (885-948): the method passes the caller's query straight through to the vendor and always maps with _build_group. The client-side post-filter block disappears with it.
- get_group (697-738), get_user_groups (1050-1129) and get_group_members switch to _build_group. Their docstrings must stop referring to managed groups and to DIRECTORY_MANAGED_GROUP_DOMAIN.
- The domain-completion half of _normalize_email (211-220) per D2: it strips and lowercases only, and callers pass fully-qualified keys. Check all eleven call sites (523, 614, 686, 708, 751-752, 803-804, 834-835, 1064).
- The DIRECTORY_GROUP_DOMAIN_MISMATCH error code, if nothing else emits it.

DELETE from app/infrastructure/configuration/infrastructure/directory.py: managed_group_domain, managed_group_prefix and enforce_managed_group_email, plus their docstring lines (21-22, 59-73). Update tests/unit/infrastructure/configuration/test_directory_settings.py, which asserts on all three (lines 27-28 and the defaults test).

RELOCATE the residual DirectorySettings (provider, require_startup_warmup, startup_preload_groups, cache_ttl_seconds, startup_warmup_timeout_seconds) plus get_directory_settings from app/infrastructure/configuration/infrastructure/directory.py to app/infrastructure/directory/settings.py, deleting the old home and updating importers including app/infrastructure/directory/factory.py and the settings test. decisions/configuration.md requires this migration to ride with work that already touches the domain rather than waiting for TASK-24, and forbids adding the slice to the legacy Settings aggregator. Verify before editing whether the aggregator file still exists and whether it references DirectorySettings. If this relocation turns out to pull in more importers than expected and pushes the PR past the size gate, split it into TASK-76.5 rather than shipping an oversized diff.

PROTOCOL DOCS. app/infrastructure/directory/provider.py's get_group docstring promises a canonical MANAGED group and accepts a managed-group slug. Reword to the generic contract: a fully-qualified group key. The method SET is unchanged, per the parent task's boundary.

VERIFY BEFORE MERGE. Re-run the plan's fact F2 grep (DIRECTORY_MANAGED, DIRECTORY_ENFORCE, MANAGED_GROUP across terraform/, Makefile, app/Makefile, app/pyproject.toml). If any environment has since set one of these, stop and re-assess.

TESTING. Provider unit tests asserting the generic contract: list_groups passes the query through and never full-lists as a side effect of the query shape; a group outside any particular domain maps successfully and unchanged (parent AC#5's provider half); a group with no email is a hard error with no silent success-None path; _normalize_email leaves a bare value bare. Existing access suites from TASK-76.3 must stay green untouched - that is the proof the seam moved rather than the behaviour.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 grep for _managed_group_prefix, _managed_group_domain, _managed_group_query_prefix, _matches_managed_group_prefix, _extract_managed_group_email and _build_managed_group returns zero hits under app/infrastructure/ (parent AC#1)
- [ ] #2 _normalize_email no longer completes a bare value with any domain, and every internal call site is confirmed to receive fully-qualified keys
- [ ] #3 list_groups applies no query-shape strategy switch and no client-side filtering; get_group, get_group_members and get_user_groups all map through the generic builder
- [ ] #4 DIRECTORY_MANAGED_GROUP_DOMAIN, DIRECTORY_MANAGED_GROUP_PREFIX and DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL are deleted from DirectorySettings and from its tests, with no replacement setting created in infrastructure (parent AC#2)
- [ ] #5 The residual DirectorySettings lives at app/infrastructure/directory/settings.py, the infrastructure/configuration/infrastructure/directory.py home is deleted, importers are updated, and no slice is added to the legacy Settings aggregator
- [ ] #6 The DirectoryProvider Protocol docstrings describe a generic, vendor-neutral contract with no managed-group language, and its method set is unchanged
- [ ] #7 The fact F2 grep across terraform, Makefile and app config is re-run at merge time and still returns zero hits
- [ ] #8 Provider unit tests cover query pass-through, successful mapping of an out-of-domain group, a missing-email group as a hard error with no silent drop, and bare-value pass-through in email normalization
- [ ] #9 The access suites from TASK-76.3 pass unmodified, and mypy, ruff and the full non-smoke pytest run are green
- [ ] #10 The four live app/modules/ DirectoryProvider consumers enumerated in the parent plan's fact F7 (permissions/handler.py:40, reports/google_groups.py:100, dev/google.py:170-171, provisioning/users.py) are re-verified at merge time to pass fully-qualified keys, so removing the email-completion branch is a no-op for them; the verification is recorded in the task notes
<!-- AC:END -->
