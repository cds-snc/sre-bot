---
id: TASK-76.5
title: Remove organization-specific defaults from access settings
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-04 15:46'
updated_date: '2026-09-04 22:40'
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
- [x] #1 No organization-specific group name remains as a default anywhere under app/packages: grep for 'sg-managers' and 'sg-org-admins' returns zero hits outside test fixtures and documentation examples
- [x] #2 The duplicated fallback_approver_slug default at app/packages/access/request/service.py:131 is removed so the value has exactly one owning home per decisions/configuration.md
- [x] #3 The owning home is decided and recorded with rationale - AccessRuntimeConfig runtime document versus ACCESS_REQUESTS_ env settings - rather than the literals simply moving; one convention is not split across both mechanisms
- [x] #4 The decision on whether the slugs are whole configured values or composed through AccessGroupNaming is recorded, and no new 'sg-' string literal is introduced either way
- [x] #5 A missing value produces a named configuration error consistent with the TASK-76.2 contract: enabling access requires its settings to be present, disabling it leaves the rest of the app unaffected, proven by a test
- [x] #6 Whatever shape the fallback slug takes still composes into a directory group key through ManagedGroupPolicy.group_key, so no bare slug reaches DirectoryProvider (TASK-76.2 decision D2)
- [x] #7 The existing access request suites pass with fixtures supplying explicit values, and no test depends on an implicit organization default
- [x] #8 No file under app/infrastructure/ or app/modules/ is modified, and AWS_ADMIN_GROUPS is left untouched
- [x] #9 mypy, ruff and the full non-smoke pytest run are green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLANNED 2026-09-04. Dependency TASK-76.2 (and siblings 76.1/76.3/76.4) are all Done and merged, so this plan is grounded against the CURRENT shipped code, not the coordinator's pre-76.3 line numbers (which have drifted).

## Grounding facts verified 2026-09-04 (read directly, not inferred)

F1. manager_group_slug IS CONFIRMED DEAD CODE, not merely defaulted wrong. Repo-wide grep across app/ (excluding caches) finds exactly one production read: packages/access/request/__init__.py:55, inside `startup_warmup`'s structured log call (`logger.info("access_requests_settings_loaded", manager_group_slug=settings.manager_group_slug, ...)`). It is never passed into AccessRequestService, never read by service.py or policies.py. service.py's own Step-4 comment is explicit that delegated-actor authorization checks OWNER/MANAGER membership of the TARGET group, "not a member of a global manager group" — the setting's docstring claim ("IDP group whose members may submit delegated requests") describes behavior that was never wired.

F2. CRITICAL DESIGN CONSTRAINT — naively removing the pydantic default would break every environment's boot, not just misconfigured ones. AccessRequestsSettings is a plain BaseModel nested inside AccessSettings (a BaseSettings), constructed EAGERLY and UNCONDITIONALLY: request/__init__.py::startup_warmup calls `get_access_request_settings()` (which constructs the whole AccessSettings singleton) as its FIRST line, BEFORE checking `settings.enabled`. Per TASK-76 coordinator fact F6/TASK-76.2 fact F9, zero ACCESS_ env vars are set in any environment today. If fallback_approver_slug became a bare required field (no default at all), `AccessRequestsSettings()`/`AccessSettings()` would raise ValidationError on EVERY boot in EVERY environment, not just ones that enable access without configuring it — a universal regression, and a direct violation of the H5/AC#5 contract ("disabling access leaves the rest of the app unaffected"). This differs from AccessRuntimeConfig's dir_domain (TASK-76.2/D6): that dataclass's `__post_init__` is safe to always-raise-on-blank because it is only ever constructed lazily, behind each subfeature's own `if settings.enabled:` gate (`get_access_runtime_config()` is never called unconditionally). AccessRequestsSettings has no equivalent lazy gate — the settings object itself IS what callers read to find `enabled`.

F3. THE FIX PATTERN ALREADY EXISTS IN THIS REPO: `integrations/slack/settings.py::SlackSettings._validate_transport_credentials`, a `@model_validator(mode="after")` that short-circuits immediately when `not self.ENABLED`, and otherwise raises `ValueError` naming the missing env var. Same file's `BOT_TOKEN: str = Field(default="", alias=...)` is the precedent for using an empty string (not an organization-specific value) as the "unconfigured" sentinel default for a required-when-enabled string setting. This plan reproduces both: `fallback_approver_slug: str = ""` plus a mirroring model_validator gated on `self.enabled`.

F4. TASK-76.3 already composes the fallback slug through `ManagedGroupPolicy.group_key` (packages/access/request/policies.py:103-106, inside `resolve_approver_candidates`), so parent AC#6 is PRE-SATISFIED by prior work — this task only re-verifies it, it does not add that composition.

F5. Exhaustive current-state call-site list (grep-verified 2026-09-04, all under app/packages/access/ plus their READMEs and app/tests/unit — zero hits anywhere else in app/, zero in app/tests/integration):
  - common/settings.py:76 (docstring line for MANAGER_GROUP_SLUG), :77 (docstring line for FALLBACK_APPROVER_SLUG, keep/reword), :83 (`manager_group_slug: str = "sg-managers"`, delete), :84 (`fallback_approver_slug: str = "sg-org-admins"`, change to `""` + validator).
  - request/service.py:124 (docstring, reword to "required; no default"), :135 (`fallback_approver_slug: str = "sg-org-admins"` constructor default, remove default → required param), :143 (`self._fallback_approver_slug = fallback_approver_slug`, unchanged), :322/:330 (reads, unchanged).
  - request/__init__.py:55 (`manager_group_slug=settings.manager_group_slug,` log kwarg, delete); :56 (`fallback_approver_slug=...`, unchanged).
  - request/providers.py:50 (`fallback_approver_slug=settings.fallback_approver_slug`) — NO CHANGE, already passes the settings value through explicitly; this is exactly why AC#2 calls the constructor default "dead weight reachable only by direct construction and tests."
  - Three READMEs (packages/access/README.md:33-34, packages/access/common/README.md:36-37, packages/access/request/README.md:79-80): each has one MANAGER_GROUP_SLUG row (delete) and one FALLBACK_APPROVER_SLUG row (default column changes from `sg-org-admins` to `none (required if enabled)`, description keeps an illustrative example per parent AC#1's documentation-example carve-out).
  - Tests: app/tests/unit/packages/access/common/test_settings.py:49-50 (defaults assertions), :108-117 (env-var-override test); app/tests/unit/packages/access/request/test_access_request_package_init.py:48,87 (`_Settings`/fixture attrs); app/tests/unit/packages/access/request/test_service.py — `make_service` helper (already explicit, no change) and `make_policy_service` (~line 1044, currently omits `fallback_approver_slug` and relies on the constructor default being removed here — MUST be updated to pass it explicitly).
  - request/policies.py and test_policies.py: no change — `resolve_approver_candidates(fallback_slug, ...)` is already a plain required parameter, not settings-sourced; existing literal `"sg-org-admins"` test arguments are fixture inputs, not defaults, and AC#1 permits them.

## Human decisions (asked during planning, both confirmed 2026-09-04)

D1 — manager_group_slug is DELETED OUTRIGHT (field, env var, docstring lines, README rows, the __init__.py log kwarg, and the two test fixture attributes), not merely un-defaulted. Rationale: F1 proves it is genuinely orphaned; requiring an operator to configure a variable that does nothing would be a worse outcome than removing it, and removing it still satisfies AC#1's literal "no default remains" bar (there is no field left to default).

D2 — fallback_approver_slug stays a WHOLE configured value (operator supplies the complete slug, e.g. `sg-org-admins`), not composed from `AccessGroupNaming.managed_prefix` + a local part. Rationale: composing would assume every organization's fallback/org-admin approver group necessarily follows the same `sg-`-managed-group naming convention as regular synced entitlement groups, which is not established anywhere in the codebase and is a bigger, unrequested behavioral assumption than this task's scope warrants.

## My decisions (grounded in code/decisions, not asked — flagged for reviewer challenge)

D3 — OWNING HOME: fallback_approver_slug STAYS an `AccessRequestsSettings` env var (`ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG`), not moved to `AccessRuntimeConfig`. Rationale, by contrast with TASK-76.2's dir_domain precedent: dir_domain feeds `ManagedGroupPolicy`, consumed across THREE subdomains (catalog, sync, request) and is loaded once from the shared runtime-config document those subdomains all read. fallback_approver_slug is read by exactly ONE subdomain (`AccessRequestService`/`resolve_approver_candidates`, request-only) — promoting it into the cross-subdomain runtime document would violate the "narrowest settings slice" rule (decisions/configuration.md, feature-packages.md, settings-singleton skill) by coupling catalog/sync's config loading to a value they never use. Reviewer: override this if the intent was uniform homing with dir_domain regardless of consumer scope.

D4 — ENFORCEMENT MECHANISM: a `@model_validator(mode="after")` on `AccessRequestsSettings` — `if self.enabled and not self.fallback_approver_slug.strip(): raise ValueError(...)` — replaces the removed default, with the field itself defaulting to `""`. This is not optional polish; F2 shows an unconditional required field breaks boot everywhere. Modeled exactly on `SlackSettings._validate_transport_credentials` (short-circuit when disabled, raise naming the env var when enabled-but-unset) and `SlackSettings.BOT_TOKEN`'s empty-string sentinel. Satisfies AC#5's exact wording: enabling requires the value present (raises), disabling leaves the rest of the app unaffected (empty string is falsy-safe and never read for real work while disabled).

## Production changes

1. `packages/access/common/settings.py` — delete the `ACCESS_REQUESTS_MANAGER_GROUP_SLUG` docstring line and the `manager_group_slug` field; change `fallback_approver_slug: str = "sg-org-admins"` to `fallback_approver_slug: str = ""`; reword its docstring line to state it is required whenever `enabled=True`, with no organization-specific default; add `from pydantic import model_validator` (already imports `field_validator`, extend the import) and the new `_validate_fallback_approver_slug` method on `AccessRequestsSettings` per D4.
2. `packages/access/request/service.py` — remove the default from the `fallback_approver_slug` constructor parameter (becomes a required, no-default `str`, staying before the still-defaulted `min_approver_count`, which is valid parameter ordering); reword its Args docstring line to "required; no default — construction fails without it" (mirrors AccessRuntimeConfig's own required-field docstring convention from TASK-76.2).
3. `packages/access/request/__init__.py` — remove the `manager_group_slug=settings.manager_group_slug,` line from the `startup_warmup` structured log call.
4. `packages/access/README.md`, `packages/access/common/README.md`, `packages/access/request/README.md` — delete the MANAGER_GROUP_SLUG row from each settings table; change the FALLBACK_APPROVER_SLUG row's default column to `none (required if enabled)` in each, keeping the description column's illustrative example.

No file under `app/infrastructure/` or `app/modules/` is touched (AC#8); `AWS_ADMIN_GROUPS` is untouched; `request/providers.py` needs no change (F5).

## Test changes

- `app/tests/unit/packages/access/common/test_settings.py`:
  - `test_access_requests_settings_defaults`: remove the `manager_group_slug` assertion; change to construct `AccessRequestsSettings()` (disabled by default) and assert `fallback_approver_slug == ""` — proving the disabled-by-default construction still succeeds.
  - `test_access_settings_reads_requests_flat_env_vars`: remove the `ACCESS_REQUESTS_MANAGER_GROUP_SLUG` `monkeypatch.setenv` call and its assertion; keep the `FALLBACK_APPROVER_SLUG` env var and assertion unchanged.
  - NEW `test_access_requests_settings_requires_fallback_approver_slug_when_enabled`: `AccessRequestsSettings(enabled=True)` raises (`pytest.raises((ValueError, ValidationError))`) naming `ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG` in the message.
  - NEW `test_access_requests_settings_enabled_with_fallback_slug_constructs`: `AccessRequestsSettings(enabled=True, fallback_approver_slug="sg-org-admins")` constructs without error.
  - NEW `test_access_requests_settings_disabled_ignores_missing_fallback_slug`: `AccessRequestsSettings(enabled=False)` constructs fine with no fallback slug set (the disabling-is-unaffected half of AC#5).
- `app/tests/unit/packages/access/request/test_access_request_package_init.py`: remove the `manager_group_slug = "sg-managers"` line from both `_Settings` fixture classes (~lines 48 and 87); `fallback_approver_slug` stays as an explicit fixture value.
- `app/tests/unit/packages/access/request/test_service.py`: update `make_policy_service` (~line 1044) to pass `fallback_approver_slug="sg-org-admins"` explicitly to `AccessRequestService(...)`, since the constructor no longer supplies one. `make_service`'s own helper default is unchanged (already explicit at the real constructor call).
- No change needed to `test_policies.py` (F5) or any integration test (F5 — zero hits).

## AC traceability

AC#1 -> settings.py field deletion + README row deletions (Production 1,4) -> test_settings.py updated defaults test; grep re-run at merge.
AC#2 -> service.py constructor default removal (Production 2) -> test_service.py's `make_policy_service` update proves the constructor now requires the argument.
AC#3 -> D3 (recorded above, no code change — it is a decision, not a migration).
AC#4 -> D2 (recorded above) + settings.py using `""` not a new `sg-` literal -> grep re-run at merge confirms no new `sg-` literal.
AC#5 -> D4's model_validator (Production 1) -> the three NEW test_settings.py cases.
AC#6 -> F4 (already implemented by TASK-76.3; this task only re-verifies) -> existing `test_policies.py::resolve_approver_candidates` composed-fallback-slug case, re-run unmodified.
AC#7 -> all UPDATED test files -> full suite green.
AC#8 -> grep for any diff under app/infrastructure/ or app/modules/, and confirm aws_ops.py untouched, at merge (git status).
AC#9 -> mypy/ruff/pytest run at merge.

## Assumptions and how to verify them

A1. No environment has set any `ACCESS_REQUESTS_*` env var since TASK-76's coordinator last checked (F6/F9) — re-run that grep across terraform/, Makefile, app/Makefile before merge; if one now sets `ACCESS_REQUESTS_ENABLED=true` without `ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG`, this change would newly fail that environment's boot (the intended, named failure mode, but confirm it isn't a silent surprise for someone mid-rollout).
A2. `make_policy_service` in test_service.py is the only direct `AccessRequestService(...)` construction relying on the now-removed default — re-grep for `AccessRequestService(` before merge to confirm no other call site was missed.
A3. pydantic-settings' nested-model construction correctly triggers `AccessRequestsSettings`'s own `model_validator` when `AccessSettings()` builds the `requests` slice from partial env data — this is the same mechanism `SlackSettings` already relies on for its own `BaseSettings`-level validator, so treated as proven precedent rather than re-verified from scratch; confirm with the new test_settings.py cases at implementation time.

## Blast radius and rollback

Production: 4 files (settings.py, service.py, __init__.py, 3 READMEs), well under 50 changed production LOC, one subsystem (`packages/access`), no terraform/CI. Zero observable behavior change in any current environment: every environment has `ACCESS_REQUESTS_ENABLED` unset/false today (F6), so the new validator never fires, and `manager_group_slug` was already inert (F1). The only reachable behavior change is the new named boot failure for an operator who sets `ACCESS_REQUESTS_ENABLED=true` without also setting the fallback slug — a strictly better outcome than today's silent wrong-organization default. Single `git revert` restores everything; no data, no migration, no ordering constraint beyond TASK-76.2 (already merged).

## Size gate

Comfortably inside the single-PR gate: ~40-60 production LOC across 4 files (one of them 3 near-identical README edits), one subsystem, no infra/modules touch, no mixed refactor-and-behavior-across-subsystems. No decomposition needed.

## Alignment with the wider programme

- decisions/configuration.md: one owning class per value — fallback_approver_slug's only home is `AccessRequestsSettings` (D3); manager_group_slug gets no home at all (deleted, D1).
- decisions/feature-packages.md / settings-singleton skill: narrowest-slice settings ownership — this task keeps a request-only value out of the shared `AccessRuntimeConfig` that catalog/sync also read.
- decisions/layers.md / migration.md: no file under `app/infrastructure/` or `app/modules/` is touched; `AWS_ADMIN_GROUPS` (the one LIVE org-specific default, frozen-module consumer) is explicitly out of scope and untouched, per the task's own NOT-IN-SCOPE section.
- TASK-76 coordinator: this is the last open child (76.1-76.4 all Done); once this lands, parent AC#6 ("all five subtasks Done") can be verified.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTED 2026-09-04, plan followed as written with one addition found at test time.

PRODUCTION (6 files, ~25 changed LOC):
- packages/access/common/settings.py: deleted manager_group_slug field + its docstring line (D1); fallback_approver_slug default changed from 'sg-org-admins' to '' with a reworded docstring; added model_validator(mode='after') _validate_fallback_approver_slug raising ValueError naming ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG only when self.enabled (D4, mirroring SlackSettings._validate_transport_credentials).
- packages/access/request/service.py: fallback_approver_slug is now a required constructor parameter (no default); Args docstring reworded.
- packages/access/request/__init__.py: removed the manager_group_slug kwarg from the startup_warmup log call.
- packages/access/README.md, common/README.md, request/README.md: MANAGER_GROUP_SLUG rows deleted; FALLBACK_APPROVER_SLUG default column now 'none (required if enabled)'. request/README.md 'How it works' step 3 also reworded from 'falling back to sg-org-admins' to the configured env var name (it read as a hardcoded fact, not an example).
- providers.py unchanged as planned (F5).

TESTS:
- test_settings.py: defaults test asserts no manager_group_slug field and fallback == ''; flat-env-var test drops MANAGER_GROUP_SLUG; three new cases (enabled-without-slug raises naming the env var, enabled-with-slug constructs, disabled-without-slug constructs) plus a root AccessSettings boot-safety case.
- test_access_request_package_init.py: manager_group_slug removed from both _Settings fixtures.
- test_service.py: make_policy_service now passes fallback_approver_slug explicitly; new test_service_construction_should_require_explicit_fallback_approver_slug asserts TypeError without it.
- NOT IN PLAN, found at test time: test_access_settings_accepts_requests_json_blob set ACCESS_REQUESTS='{"enabled": true, ...}' with no fallback slug and was relying on the removed implicit default (exactly the AC#7 anti-pattern). Blob updated to include fallback_approver_slug. This incidentally proves A3 — the nested model_validator does fire through pydantic-settings JSON-blob construction.
- test_policies.py unchanged (F4/AC#6 pre-satisfied by TASK-76.3), re-run green.

VERIFICATION: A1 re-verified — grep for ACCESS_REQUESTS/ACCESS_SYNC/ACCESS_CATALOG/ACCESS_CONFIG across terraform/, Makefile, app/Makefile returns zero hits, so no environment boot changes. A2 re-verified — AccessRequestService( has exactly two call sites (providers.py, already explicit; test_service.py, now explicit). AC#1 grep: remaining sg-org-admins hits are three documentation examples (two README table description columns, one policies.py docstring 'e.g.') and test fixture arguments, all inside the AC's carve-out; zero sg-managers hits anywhere. AC#8: git diff --stat main -- app/infrastructure app/modules is empty; aws_ops.py untouched.

GATES: ruff clean; mypy shows zero errors in any touched file (the 94 repo-wide errors are the pre-existing baseline, all in app/modules and unrelated packages); full non-smoke suite green via make test (user-run).

LEFT FOR HUMAN DoD VERIFICATION: review of decision D3 (fallback_approver_slug stays an ACCESS_REQUESTS_ env var rather than moving to AccessRuntimeConfig — flagged in the plan for reviewer challenge) and D4's empty-string sentinel; task left In Progress.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-04 20:59
---
PLANNED 2026-09-04. Two human decisions taken via clarifying questions before writing the plan: (1) manager_group_slug is dead code (only ever logged, never consumed by any authorization logic) - deleted outright rather than merely un-defaulted; (2) fallback_approver_slug stays a whole configured value, not composed via AccessGroupNaming.managed_prefix. CRITICAL FINDING (F2 in plan): naively removing fallback_approver_slug's pydantic default would break boot in every environment (not just misconfigured ones), since AccessRequestsSettings is constructed eagerly/unconditionally before the enabled check runs - fixed with a model_validator gated on self.enabled, mirroring integrations/slack/settings.py::SlackSettings exactly (empty-string sentinel + raise-when-enabled-and-unset). Owning-home decision (D3, not asked - grounded in feature-packages.md/settings-singleton's narrowest-slice rule): fallback_approver_slug stays an AccessRequestsSettings env var rather than moving to AccessRuntimeConfig, since only the request subdomain consumes it (unlike dir_domain, shared via ManagedGroupPolicy across catalog/sync/request). Fits one PR comfortably (~40-60 prod LOC, 4 files, one subsystem). Ready for human plan review.
---
<!-- COMMENTS:END -->
