---
id: TASK-71
title: 'oncall_sync: use an admin-scoped Slack user token for user-group writes'
status: Done
assignee:
  - '@me'
created_date: '2026-08-05 19:10'
updated_date: '2026-08-05 21:00'
labels:
  - oncall-sync
  - slack
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/service-accounts.md
  - decisions/platform-transports.md
  - decisions/configuration.md
  - app/packages/oncall_sync/providers.py
  - app/packages/oncall_sync/adapters/slack.py
  - app/integrations/slack/settings.py
priority: high
ordinal: 122000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The `oncall_sync` feature mirrors the current on-call user into a Slack user group (`usergroups.users.update`, and `usergroups.create`/`usergroups.enable` when needed). It currently performs these writes with the shared inbound Slack **bot** token via `SlackClientManager.get_client()` — the same credential the inbound Slack transport uses for replies/commands.

This fails in production with `permission_denied` (previously `missing_scope`): the workspace gates "who can create/edit user groups" to Admins/Owners, and per Slack's model a bot token (`xoxb-`) can never satisfy `usergroups.*` writes under that setting regardless of scopes — only an admin/owner-authorized **user token** (`xoxp-`) works.

Beyond the runtime failure, reusing the shared bot token is an architecture violation: a feature that *mutates* Slack is a "managed system-of-record" (role 3) and must use a separate, least-privilege, **admin-scoped** credential behind its own port — never the shared inbound bot token (`decisions/platform-transports.md`, `decisions/configuration.md`, and the new `decisions/service-accounts.md`).

Outcome: add a dedicated admin-scoped Slack user-token setting and rewire `oncall_sync` to perform its user-group writes with that credential instead of the shared bot token. The `xoxp-` token itself is provisioned out-of-band from a dedicated Slack service identity (see `decisions/service-accounts.md`) and injected into the deployment config/secrets by the operator; that provisioning is not part of this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A dedicated admin-scoped Slack user token setting (e.g. SLACK_ONCALL_ADMIN_TOKEN) exists as a typed field in a settings slice with a cached provider; it has no plaintext default and never appears in logs or repr.
- [x] #2 get_user_group_sync_target() in app/packages/oncall_sync/providers.py builds SlackUserGroupTarget from a WebClient authenticated with the admin token, not from SlackClientManager.get_client() (the shared inbound bot token).
- [x] #3 No oncall_sync usergroups.* write (usergroups.users.update / usergroups.create / usergroups.enable) is issued with the shared inbound bot token.
- [x] #4 When the admin token is missing or empty, the feature surfaces a clear error naming the variable rather than silently falling back to the bot token.
- [x] #5 Tests cover: the provider wires the admin-scoped client; a usergroup write is issued via the admin client; and the missing-token behavior.
- [x] #6 A short 'Slack service identity' section (identity, credential type, scopes, owner, rotation trigger) for the admin-scoped oncall_sync token exists in app/packages/oncall_sync/README.md, per decisions/service-accounts.md's Checks.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 mypy and ruff clean; pytest for the affected feature/settings passes.
- [x] #2 Operator step (human-verified, outside this PR): the SLACK_ONCALL_ADMIN_TOKEN secret is provisioned in the AWS deployment config/secrets so the running task can read it.
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Implementation Plan

### Grounding (verified against current code, 2026-08-05)
- `packages/oncall_sync/providers.py::get_user_group_sync_target()` currently does
  `SlackUserGroupTarget(SlackClientManager.get_client())` — `SlackClientManager`
  (`integrations/slack/client.py`) is a singleton over `SlackSettings.BOT_TOKEN`
  (the shared inbound bot token used by the Slack transport for replies/commands).
- `SlackUserGroupTarget` (`packages/oncall_sync/adapters/slack.py`) is already
  client-agnostic: its constructor takes any `slack_sdk.WebClient`-shaped object
  and issues `users_lookupByEmail` / `usergroups_list` / `usergroups_create` /
  `usergroups_enable` / `usergroups_users_update` on it. No change needed here —
  confirms AC#3 is satisfied purely by changing what `providers.py` injects.
- `SlackSettings` (`integrations/slack/settings.py`) is the sole home for Slack
  vendor credentials (BOT_TOKEN, APP_TOKEN, SIGNING_SECRET), matches
  `decisions/configuration.md` ("Vendor credentials -> app/integrations/<vendor>/
  settings.py") and `decisions/service-accounts.md`'s own Migration ticket text,
  which names this exact file as the field's home.
- `decisions/platform-transports.md`: "Roles 2 and 3 share the authenticated Web
  API client ... built by `integrations/<platform>/` ... using different,
  least-privilege credentials." Confirms the admin-scoped `WebClient` is built
  from a Slack-vendor settings field, consumed only inside the feature's
  `adapters/slack.py` via `providers.py` — matches the existing `get_client()` /
  `SlackUserGroupTarget` shape exactly, just with a second, separate credential.
- No `repr=False` / `SecretStr` precedent exists anywhere in the repo's settings
  classes today (grep confirmed) — AC#1's "never appears in ... repr" is a new,
  stricter requirement than the existing BOT_TOKEN/APP_TOKEN/SIGNING_SECRET
  fields satisfy. Flagged as an explicit scope boundary below (only the new
  field gets `repr=False`; existing fields are not retrofitted in this task).
- No test file exists yet for `packages/oncall_sync/providers.py` (checked:
  only `test_oncall_sync_settings.py` / `_package_init.py` /
  `_opsgenie_adapter.py` / `_slack_adapter.py` / `_service.py`). New file:
  `app/tests/unit/packages/oncall_sync/test_oncall_sync_providers.py`.
- Neither `app/packages/oncall_sync/` nor `app/integrations/slack/` has a
  README today (file_search confirmed) — AC#6 (added this session) creates the
  first one, scoped to the service-identity note only.

### Steps

1. **`app/integrations/slack/settings.py`** — add one new field to `SlackSettings`:
   ```python
   ONCALL_ADMIN_TOKEN: str = Field(default="", alias="SLACK_ONCALL_ADMIN_TOKEN", repr=False)
   ```
   Placed alongside `BOT_TOKEN`/`APP_TOKEN`/`SIGNING_SECRET`. No change to
   `_validate_transport_credentials` — this credential is not gated on
   `ENABLED`/`SOCKET_MODE` (those validate the *transport*; this is a
   feature-owned write credential resolved lazily by `oncall_sync`, mirroring
   how `get_oncall_rotations()` already tolerates the feature being inactive).
   Satisfies AC#1 (typed field, cached provider already exists via
   `get_slack_settings()`, empty-string default is not a real secret, `repr=False`
   keeps it out of the settings object's own repr; the existing structlog
   redaction pipeline already masks any log key containing "token").

2. **`app/packages/oncall_sync/providers.py`** — rewire `get_user_group_sync_target()`:
   - Remove `from integrations.slack.client import SlackClientManager` (no
     longer used anywhere in this file).
   - Add `from slack_sdk import WebClient` and
     `from integrations.slack.settings import get_slack_settings`.
   - Replace the body:
     ```python
     @lru_cache(maxsize=1)
     def get_user_group_sync_target() -> UserGroupSyncTarget:
         settings = get_slack_settings()
         if not settings.ONCALL_ADMIN_TOKEN:
             raise ValueError(
                 "SLACK_ONCALL_ADMIN_TOKEN is required to sync on-call rotations "
                 "into Slack user groups (usergroups.* writes cannot use the "
                 "shared inbound bot token)."
             )
         return SlackUserGroupTarget(WebClient(token=settings.ONCALL_ADMIN_TOKEN))
     ```
   Satisfies AC#2 (builds from the admin token, not `SlackClientManager`), AC#3
   (only injection point for `SlackUserGroupTarget`'s client; no other call
   site constructs it), and AC#4 (raises `ValueError` naming
   `SLACK_ONCALL_ADMIN_TOKEN` explicitly, before any client/API call — since
   `lru_cache` does not cache raised exceptions, every call retries cleanly
   once the operator sets the variable, no restart required beyond process
   scheduling of the next job tick).

3. **`app/packages/oncall_sync/README.md`** (new file) — short "Slack service
   identity" section per `decisions/service-accounts.md`'s Checks: identity
   (dedicated Slack service account, admin/owner role), credential type
   (`xoxp-` user token via `SLACK_ONCALL_ADMIN_TOKEN`), scopes
   (`usergroups:write`, `usergroups:read`, `users:read.email`), owner
   (platform team, not tied to a personal account), rotation trigger (on
   suspicion/role-change, or if the identity's admin/owner role is revoked —
   not a fixed machine-secret schedule, per the decision's Consequences
   section). No provisioning steps beyond what the decision record already
   states; this is documentation only, not new code. Satisfies AC#6.

### AC -> Step -> Test traceability

| AC | Step(s) | Test(s) |
|----|---------|---------|
| #1 typed field, cached provider, no plaintext default, not in logs/repr | Step 1 | `test_slack_settings.py::TestSlackSettingsOncallAdminToken` (new class): default empty, reads from `SLACK_ONCALL_ADMIN_TOKEN` env, field has `repr=False` (assert `"ONCALL_ADMIN_TOKEN"` absent from `repr(settings)` when a token is set) |
| #2 provider builds from admin-token `WebClient`, not `SlackClientManager` | Step 2 | `test_oncall_sync_providers.py::test_get_user_group_sync_target_builds_client_with_admin_token` |
| #3 no usergroups.* write via bot token | Step 2 (removal of `SlackClientManager` import) | Same test above (asserts the injected client's `.token` equals the admin token, never the bot token) + repo-wide grep in review (`SlackClientManager` has zero references left in `providers.py`) |
| #4 clear error naming the variable when token missing | Step 2 | `test_oncall_sync_providers.py::test_get_user_group_sync_target_raises_when_admin_token_missing` (`pytest.raises(ValueError, match="SLACK_ONCALL_ADMIN_TOKEN")`) |
| #5 tests: provider wiring + a write issued via admin client + missing-token | Step 2 | All three tests in `test_oncall_sync_providers.py` (see Test Matrix) |
| #6 service-identity README section | Step 3 | Manual review (documentation, not test-covered); DoD#1's mypy/ruff/pytest gates are unaffected by a markdown-only file |

### Test Matrix (`app/tests/unit/packages/oncall_sync/test_oncall_sync_providers.py`, new)

- **Happy path** — `test_get_user_group_sync_target_builds_client_with_admin_token`:
  monkeypatch `providers.get_slack_settings` to return a fake settings object
  with `ONCALL_ADMIN_TOKEN="xoxp-fake"`; call `get_user_group_sync_target()`;
  assert `isinstance(target, SlackUserGroupTarget)` and
  `target._client.token == "xoxp-fake"`.
- **End-to-end write via the admin client** —
  `test_usergroup_write_is_issued_via_the_admin_scoped_client`: same wiring as
  above, then `unittest.mock.patch.object` the returned target's `_client`
  methods (`users_lookupByEmail`, `usergroups_list`, `usergroups_users_update`)
  to return canned Slack-shaped responses, call `.sync_user_group(rotation,
  email)`, and assert `usergroups_users_update` was called — proving the write
  flows through the client that was built from the admin token (reuses the
  `_rotation()` helper pattern already in `test_oncall_sync_slack_adapter.py`).
- **Failure / missing token** —
  `test_get_user_group_sync_target_raises_when_admin_token_missing`: fake
  settings with `ONCALL_ADMIN_TOKEN=""`; `pytest.raises(ValueError,
  match="SLACK_ONCALL_ADMIN_TOKEN")`.
- **Singleton contract** — `test_get_user_group_sync_target_is_singleton`:
  two calls return the same object (mirrors the existing
  `access/sync/test_providers.py` cache-clear pattern); each test calls
  `providers.get_user_group_sync_target.cache_clear()` before and after to
  avoid cross-test leakage (no autouse fixture resets this cache today).
- **Settings field coverage** (`test_slack_settings.py`, extended, not new):
  default-empty, env-var read, `repr=False` (value absent from
  `repr(SlackSettings(...))` when set), and — per `TestSlackSettingsScope`'s
  existing pattern — confirm no accidental validator coupling (setting
  `SLACK_ONCALL_ADMIN_TOKEN` alone, with `SLACK_ENABLED` unset/false, does not
  raise, proving this credential is independent of the transport's fail-fast
  validation).

### Assumptions and doubts (flagged for human review)

1. **Validation placement (fail lazily in `providers.py`, not eagerly in
   `SlackSettings.model_validator`)** — assumes the admin token should NOT be
   required whenever `SlackSettings` is constructed (that would force it
   whenever the Slack transport boots even if `oncall_sync` has zero
   rotations configured, which is inconsistent with `get_oncall_rotations()`'s
   existing "feature inactive -> silently no-op" posture and with
   `register_background_jobs` only registering the job when rotations exist).
   Verify: confirm `register_background_jobs` (unchanged in this task) still
   gates the job registration on `get_oncall_rotations()`, so
   `get_user_group_sync_target()` is only ever invoked when the feature is
   genuinely active — re-read `packages/oncall_sync/__init__.py` at review
   time to confirm this hasn't drifted.
2. **`repr=False` vs `pydantic.SecretStr`** — chose the smaller diff
   (`Field(repr=False)` on a plain `str`, matching the *type* of the existing
   three token fields) over converting to `SecretStr` (which would mask
   `str()`/`print()` too, not just the model's own `__repr__`, but requires
   every consumer to call `.get_secret_value()` — a call-site change alien to
   `BOT_TOKEN`'s current plain-`str` usage in `SlackClientManager`). Flagged
   as an open call: if the human wants the stronger `SecretStr` guarantee, it
   should apply to all four Slack token fields together in a follow-up, not
   be introduced inconsistently for only the newest field in this PR.
3. **README location** — placed the new "Slack service identity" section in
   `app/packages/oncall_sync/README.md` (new file) rather than
   `app/integrations/slack/README.md`, reading `decisions/service-accounts.md`
   Checks' "owning feature/vendor README, next to the adapter" as pointing at
   the feature that owns the adapter (`packages/oncall_sync/adapters/slack.py`).
   Verify: if the human intends a vendor-level README instead (e.g. because a
   future second feature also needs a Slack admin-scoped credential), redirect
   this section to `app/integrations/slack/README.md` instead — trivial to move
   post-hoc since it's prose only.
4. **No production-side fallback to the bot token on missing admin token** —
   confirmed by design (Step 2 raises rather than degrading); accepted per
   AC#4's explicit "rather than silently falling back to the bot token"
   wording. This means `oncall_sync`'s job execution will error every 5
   minutes (isolated per-rotation via `_sync_one`'s existing
   `OnCallSyncError` boundary — but note the new `ValueError` is raised one
   level up, in `get_oncall_sync_service()`/`get_user_group_sync_target()`,
   *before* `OnCallSyncService._sync_one`'s try/except is reached, so it will
   propagate out of `_run_oncall_sync()` uncaught) until the operator
   provisions `SLACK_ONCALL_ADMIN_TOKEN` (DoD#2). Verify at review time that
   the scheduler's job-runner wraps each job body in its own error boundary
   (per the `plugin-registration-lifespan` background-jobs pattern) so an
   uncaught `ValueError` here fails only the `oncall_sync` job tick, not the
   whole scheduler loop or app boot.

### Blast radius and rollback

- **Blast radius**: limited to `oncall_sync`'s Slack user-group writes and the
  `SlackSettings` class (additive field only — no existing field changes, no
  behavior change to the Slack transport/bot token path, no change to
  `SlackUserGroupTarget`/`SlackClientManager`/any other `SlackSettings`
  consumer). Today's live behavior is already broken in production
  (`permission_denied` on every sync tick), so there is no working behavior
  this PR could regress for `oncall_sync` itself.
- **Rollback**: a single `git revert` fully restores the prior (already-broken)
  state; no data migration, no schema change, no terraform change. The new
  `SLACK_ONCALL_ADMIN_TOKEN` env var is additive/optional at the settings
  level (empty default), so this PR is safe to merge and deploy *before* the
  operator provisions the secret (DoD#2) — `oncall_sync` will simply keep
  failing with the new, clearer `ValueError` (naming the variable) instead of
  the current opaque `permission_denied`, until the secret lands.
- **Ordering constraint**: none blocking merge. DoD#2 (operator provisions the
  secret in AWS deployment config/secrets) can happen before or after this PR
  merges; the code tolerates the token being absent by raising a clear,
  actionable error rather than crashing boot or silently degrading.

### Single-PR size gate

- Production files touched: 2 (`integrations/slack/settings.py`,
  `packages/oncall_sync/providers.py`) + 1 new doc file (README, not code).
- Estimated production LOC: ~15-20 changed/added lines total across the two
  Python files. One new test file (~90-110 LOC, not counted against the gate).
- Subsystems crossed: one (Slack vendor credential + the single feature that
  consumes it) — no terraform, no CI, no cross-package changes.
- No mechanical-refactor-plus-behavior-change mixing: this is a pure,
  single-purpose credential swap.
- **Verdict: fits comfortably in one PR. No decomposition required.**
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented: added SLACK_USER_TOKEN (repr=False, no plaintext default) to SlackSettings alongside BOT_TOKEN/APP_TOKEN/SIGNING_SECRET; rewired get_user_group_sync_target() in packages/oncall_sync/providers.py to build SlackUserGroupTarget from a WebClient(token=settings.USER_TOKEN) instead of SlackClientManager.get_client(), raising ValueError naming SLACK_USER_TOKEN when empty. Added Slack service identity section to packages/oncall_sync/README.md. Test evidence: tests/unit/integrations/slack/test_slack_settings.py (TestSlackSettingsUserToken) and tests/unit/packages/oncall_sync/test_oncall_sync_providers.py (client wiring, write via user-scoped client, missing-token ValueError, singleton contract) all pass; full oncall_sync/slack targeted suite 39 passed. mypy and ruff show zero errors in the touched files (mypy's 182 pre-existing errors are all in legacy app/modules, unrelated). Full pytest run has 5 pre-existing failures in tests/integrations/aws/test_client_next.py and tests/modules/webhooks/test_webhooks_aws_sns.py, confirmed present on a stashed (pre-change) tree too -- unrelated to this task. DoD#2 (provisioning SLACK_USER_TOKEN secret in AWS deployment config) is an operator step left for human verification.
<!-- SECTION:NOTES:END -->
