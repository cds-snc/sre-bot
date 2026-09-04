---
id: TASK-76.5
title: Remove organization-specific defaults from access settings
status: To Do
assignee: []
created_date: '2026-09-04 15:46'
labels:
  - layering
  - configuration
milestone: m-3
dependencies:
  - TASK-76.2
references:
  - decisions/configuration.md
  - decisions/feature-packages.md
  - app/packages/access/common/settings.py
  - app/packages/access/request/service.py
parent_task_id: TASK-76
priority: medium
ordinal: 153000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Raised 2026-09-04 while planning TASK-76.2, from human direction: the app was originally built with hardcoded values and defaults matching one organization's domain, roles and group names, and is being made agnostic of the organization running it. TASK-76.2 establishes the rule for one value (dir_domain: no default anywhere, absent means a named startup error). This task applies the same rule to the organization-specific defaults it left behind in packages/access.

THE PROBLEM. Two access settings ship an organization's own group names as code defaults:
- AccessRequestsSettings.manager_group_slug = 'sg-managers' (app/packages/access/common/settings.py:83)
- AccessRequestsSettings.fallback_approver_slug = 'sg-org-admins' (app/packages/access/common/settings.py:84)

Both are wrong twice over. First, they are organization-specific values presented as universal defaults - an operator who never sets them silently gets another organization's group names, and the request feature then resolves approvers against groups that do not exist in their directory. Second, both literals re-encode the 'sg-' group prefix that AccessRuntimeConfig.dir_prefix + dir_separator already own, which is exactly the second-home duplication decisions/configuration.md forbids and which TASK-76 decision D3 removed for the managed-group prefix.

The fallback slug is additionally duplicated as a constructor default at app/packages/access/request/service.py:131 (fallback_approver_slug: str = 'sg-org-admins'), so the same organization-specific literal has two homes inside one feature. Live wiring passes the setting through at packages/access/request/__init__.py:55-56 and providers.py:47, so the constructor default is only reachable by direct construction and tests - it is dead weight that keeps the literal alive.

Consumers to keep working: resolve_approver_candidates (request/policies.py:72,103) receives fallback_slug and passes it straight to get_group_members as a group key, and request/service.py:303,310 supply it. Note the interaction with TASK-76.2 decision D2: after TASK-76.3 no access call site may pass a bare slug to DirectoryProvider, so whatever shape this value takes must still compose into a group key through ManagedGroupPolicy.group_key.

SCOPE.
1. Remove both organization-specific defaults so an unset value is a named configuration error rather than a silent wrong-organization lookup, consistent with the contract TASK-76.2 records as H5/H6.
2. DECIDE AND RECORD the owning home rather than moving the literals: these are org group-naming facts of the same class as dir_prefix/dir_separator/dir_domain, which TASK-76 decision D3 puts on the AccessRuntimeConfig runtime document - versus keeping them as ACCESS_REQUESTS_* env settings. Pick one, state the rationale, do not split one convention across both mechanisms.
3. DECIDE AND RECORD whether the slugs stay whole configured values or are composed from the existing naming (AccessGroupNaming). If composed, they must go through AccessGroupNaming rather than a fresh 'sg-' string literal; if whole, say why explicitly so the duplication is a deliberate choice rather than an oversight.
4. Delete the duplicated constructor default at request/service.py:131 so the value has exactly one home.
5. Update tests and fixtures to supply explicit values; no test may depend on an implicit organization default.

NOT IN SCOPE, and why.
- AWS_ADMIN_GROUPS = ['sre-ifs@cds-snc.ca'] (app/infrastructure/configuration/features/aws_ops.py:28). Same class of problem, different risk: unlike access, this default is LIVE. TASK-76's plan fact F7 grep-verified there is no terraform or Makefile override anywhere, so that default is what every environment actually uses today at modules/permissions/handler.py:40. Removing it without first provisioning the value through SSM/terraform breaks a running feature, and its consumer sits in app/modules/, frozen under decisions/migration.md rule 1. It needs its own task with a deployment step, not this one.
- infrastructure/configuration/features/groups.py::GROUP_DOMAIN (legacy, TASK-76 decision D4 names it) and TASK-74/75's approved-participant-domain (an allow-list policy, not an identity fact).
- Any change to ManagedGroupPolicy, the DirectoryProvider, or anything under app/infrastructure/.

PRECONDITION: TASK-76.2 must land first - it establishes the no-default rule, the AccessRuntimeConfig invariant pattern and the AccessGroupNaming derivation this task follows.

WHY THIS IS SAFE NOW: packages/access is not enabled in any environment (TASK-76 plan fact F6) and no ACCESS_ env var is set in terraform or either Makefile (verified 2026-09-04), so removing these defaults costs no rollout. RE-VERIFY BOTH BEFORE MERGE.

TESTING (decisions/testing.md). Unit tests at the settings/config boundary proving a missing value fails with a named error rather than falling back; request-service and approver-resolution tests updated to supply explicit values through their existing fixtures. Feature-boundary assertions, not settings-internals assertions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No organization-specific group name remains as a default anywhere under app/packages: grep for 'sg-managers' and 'sg-org-admins' returns zero hits outside test fixtures and documentation examples
- [ ] #2 The duplicated fallback_approver_slug default at app/packages/access/request/service.py:131 is removed so the value has exactly one owning home per decisions/configuration.md
- [ ] #3 The owning home is decided and recorded with rationale - AccessRuntimeConfig runtime document versus ACCESS_REQUESTS_ env settings - rather than the literals simply moving; one convention is not split across both mechanisms
- [ ] #4 The decision on whether the slugs are whole configured values or composed through AccessGroupNaming is recorded, and no new 'sg-' string literal is introduced either way
- [ ] #5 A missing value produces a named configuration error consistent with the TASK-76.2 contract: enabling access requires its settings to be present, disabling it leaves the rest of the app unaffected, proven by a test
- [ ] #6 Whatever shape the fallback slug takes still composes into a directory group key through ManagedGroupPolicy.group_key, so no bare slug reaches DirectoryProvider (TASK-76.2 decision D2)
- [ ] #7 The existing access request suites pass with fixtures supplying explicit values, and no test depends on an implicit organization default
- [ ] #8 No file under app/infrastructure/ or app/modules/ is modified, and AWS_ADMIN_GROUPS is left untouched
- [ ] #9 mypy, ruff and the full non-smoke pytest run are green
<!-- AC:END -->
