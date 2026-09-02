---
id: TASK-74
title: 'oncall_sync: validate participant email domains before Slack lookup'
status: To Do
assignee: []
created_date: '2026-09-02 20:17'
updated_date: '2026-09-02 20:27'
labels:
  - oncall-sync
  - slack
  - configuration
  - observability
dependencies: []
references:
  - decisions/configuration.md
  - decisions/observability.md
  - decisions/layers.md
  - app/packages/oncall_sync/settings.py
  - app/packages/oncall_sync/providers.py
  - app/packages/oncall_sync/adapters/slack.py
  - app/packages/oncall_sync/service.py
ordinal: 143000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
OpsGenie may return an on-call participant email that cannot belong to a Slack workspace user, such as a personal or otherwise non-organizational address. The current Slack adapter calls users_lookupByEmail on every sync tick and logs users_not_found at error level with the raw email, repeating indefinitely when the source profile cannot be corrected.

Add feature-owned configuration for approved participant email domains and use it before Slack lookup. An address outside the configured domains is a source-data mismatch: it must be excluded from the synced user group without calling Slack, and it must remain observable via a single privacy-safe informational log line per sync attempt (never the raw email address). Do not reuse directory or legacy group-domain settings.

Kept intentionally simple: this task does not add durable cross-tick alert suppression or a configurable suppression interval -- the informational (non-paging) log level is enough to stop the original recurring-ERROR problem. Durable suppression with a configurable interval is deferred to TASK-75.

This work is independent of TASK-25.1.* Google Workspace client migrations and follows completed TASK-71, which only established the admin-scoped Slack credential.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A feature-owned OnCallSyncSettings slice and cached provider (get_oncall_sync_settings) define approved participant email domains; no directory or legacy group-domain setting is reused.
- [ ] #2 The Slack user-group adapter skips users_lookupByEmail for an on-call email outside the approved domains and leaves the user group membership limited to resolvable, approved participants; when no approved domains are configured, behavior is unchanged (no filtering, current pass-through behavior preserved).
- [ ] #3 An unapproved email domain logs one informational structured event per sync attempt containing the Slack handle and a privacy-safe SHA-256 email fingerprint, never the raw email address.
- [ ] #4 Slack users_lookupByEmail failures for approved domains retain their existing error handling and are not classified as an unapproved-domain mismatch.
- [ ] #5 Focused tests cover settings parsing/normalization, approved-domain lookup, unapproved-domain lookup avoidance, membership behavior, and privacy-safe logging fields.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Mypy and ruff are clean for changed files, and focused oncall_sync tests pass.
- [ ] #2 A human verifies the approved-domain deployment values before enabling the behavior in production.
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Ground truth (verified against current code, 2026-09-02)

- app/packages/oncall_sync/settings.py currently has NO pydantic BaseSettings class (only BaseModel schedule-config types + load_schedules()/get_oncall_schedules()). A new OnCallSyncSettings slice is genuinely new, not a rename.
- app/packages/oncall_sync/adapters/slack.py::SlackUserGroupTarget._resolve_user_id (lines ~55-68) is the sole call site of users_lookupByEmail; it already has a try/except SlackApiError -> log.error("oncall_sync_user_lookup_failed", email=email, error=...) return None. That existing raw-email ERROR log for genuine approved-domain lookup failures is explicitly OUT of scope (AC#4) -- preserved as-is.
- providers.py::get_user_group_sync_target() is the only construction site of SlackUserGroupTarget (one lru_cache singleton).
- The "directory/legacy group-domain settings" AC#1 warns against reusing are confirmed to exist and are unrelated: infrastructure/configuration/features/groups.py::GROUP_DOMAIN and infrastructure/configuration/infrastructure/directory.py::DIRECTORY_MANAGED_GROUP_DOMAIN/DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL. New setting is package-local and separate from both.
- Precedent for a small package-owned BaseSettings slice with one list field + lru_cache provider: app/packages/incident_draft/settings.py::IncidentDraftSettings/get_incident_draft_settings (flat fields, per-field alias, no env_prefix/nested delimiter needed since this is a single-purpose slice, unlike AccessSettings's multi-sub-feature nesting).
- List-typed env vars in this repo use JSON-array string format (CORS_ALLOWED_ORIGINS precedent, terraform/ecs.tf:22 jsonencode(...)) -- pydantic-settings parses this natively for a `list[str]` field, no custom parser needed.
- HUMAN DECISION (2026-09-02): scope simplified from the original draft -- no durable/DynamoDB suppression store, no configurable suppression interval, no per-tick dedup in this task. A single INFO-level (non-paging) structured log line per sync attempt is sufficient to eliminate the original recurring-ERROR problem, because INFO isn't alert-worthy noise the way the current ERROR-level `users_not_found` is. Durable suppression + interval is TASK-75 (created this session, dep TASK-74).
- HUMAN DECISION: when APPROVED_EMAIL_DOMAINS is left unconfigured (empty list, the safe default), the adapter must treat the feature as OFF -- i.e. no domain filtering, current pass-through behavior unchanged -- rather than deny-all. This avoids a deploy-time regression where shipping this change without setting the env var would silently exclude every on-call participant from every synced Slack group.

## Steps

1. `app/packages/oncall_sync/settings.py` -- add, after the existing flat-rotation section:
   - `OnCallSyncSettings(BaseSettings)`: `APPROVED_EMAIL_DOMAINS: list[str] = Field(default_factory=list, alias="ONCALL_SYNC_APPROVED_EMAIL_DOMAINS")`, `model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")` (mirrors IncidentDraftSettings exactly).
   - `@field_validator("APPROVED_EMAIL_DOMAINS", mode="after")` normalizing each entry via `.strip().lower()` and dropping empties, so adapter-side comparison never needs to re-normalize.
   - `@lru_cache(maxsize=1) def get_oncall_sync_settings() -> OnCallSyncSettings: return OnCallSyncSettings()`.
   - New imports needed: `Field` (already imported), add `field_validator` from pydantic, add `BaseSettings, SettingsConfigDict` from pydantic_settings, add `lru_cache` (already imported for get_oncall_schedules).

2. `app/packages/oncall_sync/adapters/slack.py`:
   - `SlackUserGroupTarget.__init__(self, client: WebClient, *, approved_domains: frozenset[str] = frozenset()) -> None` -- keyword-only, default empty preserves every existing call site (`SlackUserGroupTarget(client)`) and existing test at zero-diff.
   - New module-level helper: `def _fingerprint_email(email: str) -> str: return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()` (new `import hashlib`).
   - New private method `_is_approved_domain(self, email: str) -> bool`: `domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""`; `return domain in self._approved_domains`.
   - In `_resolve_user_id`, before the existing `try: resp = self._client.users_lookupByEmail(...)`, add:
     ```python
     if self._approved_domains and not self._is_approved_domain(email):
         log.info("oncall_sync_participant_email_domain_mismatch", email_fingerprint=_fingerprint_email(email))
         return None
     ```
     `log` is already the bound logger from `sync_user_group`'s `logger.bind(slack_handle=handle)`, so `slack_handle` is already attached to the event without extra plumbing -- satisfies AC#3's "containing the Slack handle" with zero new parameter threading.
   - Zero change to `sync_user_group`'s existing try/except/OnCallSyncError wrapping, `_find_or_create_usergroup`, `_lookup_usergroup` -- unapproved emails just don't produce a `user_id`, so they fall out of the existing `user_ids` list comprehension exactly the same way an unresolvable email does today.

3. `app/packages/oncall_sync/providers.py`:
   - Import `get_oncall_sync_settings` from `packages.oncall_sync.settings` (alongside the existing `get_oncall_schedules` import).
   - In `get_user_group_sync_target()`, after the existing `USER_TOKEN` guard, read `oncall_settings = get_oncall_sync_settings()` and pass `approved_domains=frozenset(oncall_settings.APPROVED_EMAIL_DOMAINS)` into `SlackUserGroupTarget(...)`.

4. `app/packages/oncall_sync/README.md` (optional, small): add one line under "How it works" noting `ONCALL_SYNC_APPROVED_EMAIL_DOMAINS` gates which participant emails are looked up in Slack -- mirrors the existing "Slack Service Identity" section's role of documenting feature-owned config in the package README. Not load-bearing; skip if reviewer prefers no doc churn.

## AC traceability

- AC#1 (settings slice + provider) -> Step 1 -> `test_oncall_sync_settings.py` (new tests: default empty list, JSON-array env parsing, lowercase/strip normalization, `get_oncall_sync_settings` singleton identity).
- AC#2 (skip lookup for unapproved domain; unchanged when unconfigured) -> Step 2 -> `test_oncall_sync_slack_adapter.py` (new tests: unapproved-domain email never calls `users_lookupByEmail` and is excluded from final membership; approved-domain email still resolves normally; empty `approved_domains` default preserves every existing test in this file unmodified).
- AC#3 (one INFO event, handle + fingerprint, no raw email) -> Step 2 -> new test asserting, via `structlog.testing.capture_logs()`, the emitted event's kwargs contain `email_fingerprint` (a 64-char hex string, not equal to the raw email) and `slack_handle`, and that no key/value in the captured event equals or contains the raw email string.
- AC#4 (approved-domain lookup failures unchanged) -> no code change (already correct) -> existing test `test_skips_when_email_does_not_resolve_to_user` stays green unmodified; add one explicit regression test asserting the existing `_slack_error("users_not_found")` path still logs `oncall_sync_user_lookup_failed` (not the new mismatch event) when the domain is approved.
- AC#5 (focused tests) -> Steps 1-2 plus `test_oncall_sync_providers.py` updates (below).

## Test matrix

- Settings (`test_oncall_sync_settings.py`, new test class/functions):
  - default `APPROVED_EMAIL_DOMAINS == []` with no env var set.
  - `ONCALL_SYNC_APPROVED_EMAIL_DOMAINS='["Example.COM", " other.org "]'` parses and normalizes to `["example.com", "other.org"]`.
  - `get_oncall_sync_settings()` returns the same cached instance on repeated calls (mirrors existing `get_oncall_schedules` singleton test pattern if one exists, else a fresh `is` identity check).
- Adapter (`test_oncall_sync_slack_adapter.py`, new tests alongside the existing 9):
  - approved-domain email (domain in `approved_domains`) still calls `users_lookupByEmail` and resolves normally.
  - unapproved-domain email: `users_lookupByEmail` is `assert_not_called()`; final `usergroups_users_update` (or "no resolvable users" skip) excludes it, same shape as `test_skips_when_email_does_not_resolve_to_user`.
  - unapproved-domain email with no `@` character: treated as unapproved (empty domain never matches), does not raise.
  - `approved_domains=frozenset()` (default): behavior identical to before this change (existing 9 tests need zero modification -- this IS the regression check for the "unchanged when unconfigured" half of AC#2).
  - INFO log assertion for the unapproved-domain path (email_fingerprint present + correct SHA-256 hex value, `email` key absent, raw email substring absent from all logged values, `slack_handle` present).
  - approved-domain `SlackApiError("users_not_found")` still logs `oncall_sync_user_lookup_failed` (existing event name), not the new mismatch event -- explicit AC#4 regression guard.
- Providers (`test_oncall_sync_providers.py`, mechanical update to all 4 existing tests):
  - add `monkeypatch.setattr(providers, "get_oncall_sync_settings", lambda: SimpleNamespace(APPROVED_EMAIL_DOMAINS=[]))` (or a small local fixture) to each existing test so they stay isolated from real env/pydantic-settings construction, mirroring how `get_slack_settings` is already monkeypatched there.
  - one new test asserting `approved_domains=frozenset({"example.com"})` is passed through into the constructed `SlackUserGroupTarget` when `get_oncall_sync_settings()` returns that value.

## Assumptions and doubts (flagged for human review, not silently resolved)

1. **Double log line per tick for the same participant.** `OnCallSyncService._sync_rotation` and `_sync_schedule` each call `sync_user_group` independently (rotation-level group, then schedule-aggregate group) for the same on-call email, with two different `slack_handle`s. An unapproved-domain email therefore produces two separate INFO log lines per tick (one per handle), not one. This is a direct, unavoidable consequence of the existing service-layer structure and is INFO-level (non-paging), so it was judged acceptable rather than restructuring `service.py` to dedupe across both calls -- flagged here in case the human wants it unified later (would be additional scope, likely folded into TASK-75's suppression-key design instead, since that task already keys per (slack_handle, fingerprint) pair and would just also suppress the second same-tick emission for free once implemented).
2. **`hashlib.sha256` for the fingerprint** (not md5/sha1) -- satisfies the AC's literal "SHA-256" requirement and keeps ruff's `S324` (insecure hash) rule quiet, which flags md5/sha1 but not sha256.
3. **No validation on `APPROVED_EMAIL_DOMAINS` entries' shape** (e.g. rejecting a value containing "@" or whitespace mid-string beyond `.strip()`) -- kept minimal per the "keep it simple" direction; a malformed entry just never matches any real email domain, failing safe (over-exclusion, not under-exclusion).
4. **README update (Step 4) is optional** -- flagged as skippable if the reviewer prefers a smaller diff; not required by any AC.

## Blast radius and rollback

- Touches exactly one feature package (`app/packages/oncall_sync/`); no terraform, no CI, no shared infrastructure changes (no new DynamoDB table or StorageService usage in this reduced scope).
- Default behavior (empty `APPROVED_EMAIL_DOMAINS`) is provably identical to pre-change behavior: the adapter's new domain check is gated on `self._approved_domains` being truthy, so with no env var configured every existing code path and every existing test in `test_oncall_sync_slack_adapter.py` is unaffected.
- A single `git revert` fully restores prior behavior; no data migration, no persisted state introduced by this task (TASK-75 is the one that introduces persisted state).
- Rollout ordering: shipping this PR with `ONCALL_SYNC_APPROVED_EMAIL_DOMAINS` unset is safe (feature stays off, current behavior). Setting the env var to a real domain list is a separate, human-verified deploy step per DoD#2 -- do not set it in the same change unless the value has been confirmed against the real Slack workspace's approved org domain(s).

## Size gate

Production diff: ~50-70 LOC across 3 files (settings.py, adapters/slack.py, providers.py) + an optional ~2-line README addition. One subsystem (oncall_sync package only), no terraform/CI, no mechanical-refactor-plus-behavior mixing. Fits comfortably within a single reviewable PR -- no decomposition needed.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-02 20:26
---
Re-scoped 2026-09-02 (human request): dropped the durable alert-suppression record + configurable suppression interval from this task's scope to keep the change small; the informational (non-paging) log level alone is sufficient to stop the original recurring-ERROR noise. Durable suppression/interval work moved to TASK-75 (dep TASK-74).
---
<!-- COMMENTS:END -->
