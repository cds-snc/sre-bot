---
id: TASK-25.1.6.3
title: >-
  Make DirectoryProvider list-all generic and unbounded, and close the mapping
  gaps blocking the legacy consumers
status: To Do
assignee: []
created_date: '2026-09-02 15:00'
updated_date: '2026-09-03 17:58'
labels:
  - clients
  - phase-3
  - architecture
milestone: m-3
dependencies:
  - TASK-25.1.6.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/layers.md
  - app/infrastructure/directory/provider.py
  - app/infrastructure/directory/google.py
  - app/integrations/google_workspace/google_directory.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 134000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DECISION RECORDED (2026-09-02, human-directed): infrastructure/directory/{provider,google,factory}.py::DirectoryProvider / GoogleDirectoryProvider IS THE WAY FORWARD. It survives; app/integrations/google_workspace/google_directory.py is deleted; the four legacy app/modules/* consumers move onto the DirectoryProvider Protocol. This settles TASK-25.1.6's AC#5 for the Directory surface - no further 'which side wins' analysis is needed, only migration.

SLICE A of two (split 2026-09-03, human-approved; see comment #1). Capability parity ONLY - no consumer moves here. It exists because a straight repoint would silently change behaviour: the Protocol as written today cannot express what two of the four legacy call sites need. SLICE B is TASK-25.1.6.3.1 (batch rearchitecture + groups-with-members composition).

GUIDING PRINCIPLE FOR THIS SLICE (human, 2026-09-03): an infrastructure service method must be GENERIC. Early bespoke conveniences on this Protocol were naive attempts to improve developer experience and introduced antipatterns. Where feature-specific behaviour is required, the feature owns it. Each task moves us closer to decisions/outbound-clients.md and decisions/sdk-typing.md; interim shims are acceptable only to keep production working, never as a destination.

GAPS THIS SLICE CLOSES (verified 2026-09-03 against the code and the installed googleapiclient-stubs).

1. list_users cannot express 'the whole domain', and its limit does not do what it claims. Legacy google_directory.list_users() paginates to exhaustion and returns every user, which is what modules/provisioning/users.py relies on for a full-directory sync. DirectoryProvider.list_users(query='', limit=100) defaults to 100 - but the truncation is worse than the task originally described: google.py:402 _paginate walks EVERY page to exhaustion and only then applies result.data[:limit] (google.py:418). So today limit is a post-hoc slice, not an API-layer bound: modules/dev/google.py:82's list_users(limit=3) pulls the entire directory and discards all but three. Both halves are fixed here.

2. list_groups requires a query and rewrites bare strings. Legacy google_directory.list_groups() takes NO argument and lists every group. DirectoryProvider.list_groups(query: str) is required-argument, translates a bare string into email:{query}* and, when _managed_group_query_prefix matches, switches to an unfiltered list plus a client-side managed-prefix filter. modules/reports/google_groups.py:69 calls list_groups() with no arguments and expects all groups. Note the empty string is NOT usable as-is today: '' has no ':' or '=', so it becomes the query email:*.

3. Managed-group policy is feature logic sitting in an infrastructure service. _extract_managed_group_email prefers sg-prefixed aliases, _managed_group_query_prefix switches strategy, and _build_directory_group returns DIRECTORY_GROUP_DOMAIN_MISMATCH for any group outside DIRECTORY_MANAGED_GROUP_DOMAIN. That is packages/access policy. A 'list every group in the domain' capability routed through it is a latent hard failure: DIRECTORY_MANAGED_GROUP_DOMAIN and DIRECTORY_MANAGED_GROUP_PREFIX are unset everywhere today (grep-confirmed: no terraform, pyproject or Makefile entry), so there is no live impact - but the day that setting is populated, the reports consumer breaks. This slice splits the mapper in two and confines the managed policy to the paths that actually want it. FULL relocation of that policy into packages/access is deliberately NOT here - it touches packages/access and settings, mixing subsystems - and is tracked by its own follow-up task.

4. Silent group dropping. _build_directory_group can return success(None) - when the group has no resolvable email AND DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL is false - and list_groups then omits that group with no error. Impact, since the human asked for it concretely: packages/access/catalog silently omits an entitlement group (indistinguishable from 'not configured'), and modules/reports/google_groups.py silently ships an incomplete report. Under the generic mapper the only unmappable group is one missing email or provider id, i.e. a genuine provider data defect. Decision: skip it, log at warning with the provider group id, and count the drops on the completion log line. Never silent, and no feature policy added to infrastructure.

5. DirectoryUser cannot carry the names the migration needs. Legacy list_groups_with_members merged whole user records into member dicts via get_members_details, which is how modules/aws/identity_center.py:145-149 and :316-321 obtain name.givenName / name.familyName to create AWS users. DirectoryUser has only display_name. The stubs confirm the source shape exists and is typed (googleapiclient-stubs UserName TypedDict: givenName, familyName, fullName, displayName), so given_name and family_name are added here as capability parity. The member-to-user JOIN stays with the consumer - it is business logic and does not belong in the provider.

EXPLICITLY OUT OF SCOPE, each owned elsewhere: the groups-with-members composition, the batch pagination defect and the execute_batch_request rearchitecture (TASK-25.1.6.3.1); repointing any consumer (TASK-25.1.6.4 and .5); relocating managed-group policy into packages/access (its own follow-up task); modifying integrations/google_workspace/** or packages/access/**.

NOTE ON DATA SHAPE: the legacy functions return raw list[dict]; the provider returns DirectoryUser/DirectoryGroup/DirectoryMember frozen dataclasses. That translation is the point (decisions/sdk-typing.md item 3), not an obstacle - but the consuming slices need field-by-field mapping, so AC#7 requires the field inventory be recorded here rather than discovered mid-migration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 DirectoryProvider can express 'every user in the domain' without a caller-supplied magic limit, GoogleDirectoryProvider implements it by paginating to exhaustion, and a test proves a multi-page result set is returned in full
- [ ] #2 list_users stops paginating once an explicit limit is satisfied instead of walking every page and slicing the result, proven by a test asserting the number of pages fetched
- [ ] #3 DirectoryProvider can express 'every group in the domain' without a query and without routing through the managed-group-prefix path; a test proves it against a multi-page groups payload
- [ ] #4 Group mapping is split into a generic mapper (email + provider id only) used by the unfiltered list paths and a managed mapper (alias preference plus domain enforcement) used by get_group, get_user_groups and the query path; existing packages/access behaviour is unchanged and its tests pass untouched
- [ ] #5 A group entry that cannot be mapped is never silently dropped: it is logged at warning with its provider group id and counted on the completion log line, with a test covering an unmappable entry
- [ ] #6 DirectoryUser carries given_name and family_name, populated from the Google name.givenName / name.familyName payload, so TASK-25.1.6.5 can perform the member-to-user join that legacy get_members_details did
- [ ] #7 Every legacy google_directory.py response field the canonical dataclasses cannot carry is enumerated in the task notes, so TASK-25.1.6.4/.5 do not discover it mid-migration
- [ ] #8 No consumer is repointed in this task, integrations/google_workspace/** is not modified, and git diff touches app/infrastructure/directory/** and its tests only
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-03 17:58
---
RE-SCOPED AND RETITLED 2026-09-03 (task-planner, human-approved during planning). Split under the implementation-planning size gate: the original scope mixed a mechanical mapping/pagination change (reviewed for completeness) with a behavioural rearchitecture of the Google batch surface (reviewed for correctness) - gate trigger #3. Estimated combined diff was ~295 production LOC across 3 files, under the 400 LOC threshold, so the split is a deliberate reviewability choice rather than a hard-gate requirement.

THIS TASK IS NOW SLICE A: list-all semantics, the generic/managed group-mapping split, observable drops, the DirectoryUser name fields, and the field inventory. It unblocks TASK-25.1.6.4 on its own.

SLICE B IS THE NEW TASK-25.1.6.3.1: batch orchestration moved out of integrations/google_workspace/client.py::execute_batch_request into GoogleDirectoryProvider, batch pagination, and the groups-with-members composition. Only TASK-25.1.6.5 needs it, and TASK-25.1.6.5's dependency has been repointed accordingly.

AC REPLACEMENT RECORDED EXPLICITLY (per the backlog-task-workflow rule against silently reshaping ACs). The previous six criteria were REPLACED with eight. Mapping: old #1 (unbounded users) survives as new #1 and gains new #2; old #2 (unbounded groups) survives as new #3; old #3 (silent drop) survives as new #5 and gains new #4, which is the mechanism the human asked for after reviewing the drop-impact analysis; old #4 (groups-with-members composition) MOVED WHOLESALE to TASK-25.1.6.3.1 AC#4-#7 and is no longer this task's responsibility; old #5 (field inventory) survives as new #7; old #6 (no consumer repointed) survives as new #8. New #6 (DirectoryUser given_name/family_name) is added scope, human-approved, because without it TASK-25.1.6.5 cannot map identity_center's name.givenName / name.familyName AWS user-creation preformatting.
---
<!-- COMMENTS:END -->
