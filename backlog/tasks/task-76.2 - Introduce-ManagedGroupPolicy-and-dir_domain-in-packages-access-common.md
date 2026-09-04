---
id: TASK-76.2
title: Introduce ManagedGroupPolicy and dir_domain in packages/access/common
status: To Do
assignee: []
created_date: '2026-09-04 14:17'
labels:
  - layering
milestone: m-3
dependencies:
  - TASK-76.1
parent_task_id: TASK-76
priority: medium
ordinal: 149000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-76 (see the coordinator plan, decisions D1, D3, D5). Feature-only, additive; the new policy is not yet wired into the services - TASK-76.3 does that.

WHY. Per D1 the DirectoryProvider becomes unconditionally generic and packages/access owns the managed-group policy. This slice builds that owner and its configuration so the cutover slice is a pure call-site change.

SCOPE.

1. New app/packages/access/common/group_policy.py holding a frozen dataclass ManagedGroupPolicy - a pure value object, no I/O, no infrastructure imports beyond the DirectoryGroup model. It belongs in common/ because catalog, sync and request all consume it (decisions/feature-packages.md: common/ admits types with two or more subdomain consumers and no I/O). Responsibilities, each replacing one piece of provider logic:
   - canonical_email(group) - alias preference, replacing _extract_managed_group_email (google.py:269-285). Prefers an alias whose local part starts with the managed prefix AND whose domain is the managed domain; falls back to the group's primary email.
   - canonical_slug(group) - the local part of the canonical email, replacing the slug derivation currently baked into the mappers.
   - is_managed(group) - domain enforcement, replacing the DIRECTORY_GROUP_DOMAIN_MISMATCH branch in _build_managed_group (google.py:466-471). Returns a boolean; the feature decides whether a non-match is an error or an omission (see AC below).
   - matches_prefix(group, prefix) - alias-aware prefix matching, replacing _matches_managed_group_prefix (google.py:306-313).
   - group_key(slug) - slug-to-email composition, replacing the group half of _normalize_email (google.py:211-220) per D2.
   Construct it from AccessRuntimeConfig so the prefix comes from the existing AccessGroupNaming path (dir_prefix + dir_separator) and is NOT duplicated as its own setting (D3).

2. AccessRuntimeConfig (app/packages/access/common/config/settings.py) gains dir_domain alongside dir_prefix and dir_separator, plus whatever loader/bundle schema and fixtures carry the document. Per D5 it is REQUIRED and validated non-empty at load: an empty domain is what makes group_key produce an unusable bare slug today, and access is unreleased (plan fact F6) so there is no compatibility burden in tightening this. Failing loudly at config load beats failing opaquely at the IDP call.

3. Do NOT add an AccessSettings env var for the domain, and do NOT re-home managed_group_prefix or enforce_managed_group_email - D3 deletes both. Nothing in this slice may create a second home for a value that already exists (decisions/configuration.md).

NOT IN SCOPE. Wiring the policy into catalog/sync/request (TASK-76.3). Any change under app/infrastructure/ (TASK-76.4).

TESTING (decisions/testing.md). Pure unit tests, no doubles needed for a value object. Cover: alias preference wins over primary email; alias with the right prefix but wrong domain is not preferred; no matching alias falls back to primary; is_managed rejects an out-of-domain group (this is the AC#5 feature-boundary test the parent task requires); matches_prefix hits on an alias as well as on the primary email; group_key composes slug plus domain; AccessRuntimeConfig with a missing or blank dir_domain fails validation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ManagedGroupPolicy exists in app/packages/access/common as a frozen dataclass with no I/O and no imports from app/integrations, exposing canonical email, canonical slug, managed-domain check, alias-aware prefix match and slug-to-key composition
- [ ] #2 The managed prefix is derived from the existing AccessRuntimeConfig naming (dir_prefix plus dir_separator) and is not introduced as a new setting anywhere
- [ ] #3 AccessRuntimeConfig carries dir_domain, validated as required and non-empty, with loader/bundle/fixture plumbing updated; no ACCESS_ env var and no infrastructure setting is added for it
- [ ] #4 A DirectoryGroup whose email is outside the managed domain is rejected by ManagedGroupPolicy, proven by a unit test at the feature boundary (parent AC#5)
- [ ] #5 Unit tests cover alias preference including the wrong-domain-alias case, primary-email fallback, alias-based prefix matching, key composition, and blank dir_domain failing validation
- [ ] #6 No file under app/infrastructure/ is modified by this slice
- [ ] #7 mypy, ruff and the full non-smoke pytest run are green
<!-- AC:END -->
