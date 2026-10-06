# Legacy surface inventory

This inventory is the external compatibility contract of the legacy bot: every
user-facing surface of `app/modules/`, plus the Slack commands registered on
the Slack provider, by `register_slack_commands` hookimpls under `app/packages/`
and by the hand-written `_register_legacy_slack_commands` step in
`server/lifespan.py` for `modules/sre` and `modules/dev`.
It is step 1 (Inventory) of the per-surface recipe in `decisions/migration.md`,
and it is recorded before any module is rebuilt. Other teams depend on these
command names, interaction ids and URLs. Every rebuild must keep them working.

Each surface is assigned to a target by what it does, not by the module that
holds it today. `modules/sre` and `modules/aws` are grab-bags, so their
surfaces go to different targets. Incident surfaces go to `app/features/incident/`
through TASK-38. TASK-38 is gated on the TASK-97 decision, and the TASK-97
packet sets the subdomain split (TASK-38 lists the candidates).

Conventions:

- Paths are relative to `app/`.
- Slash commands register as `/{COMMAND_PREFIX}<name>`. `COMMAND_PREFIX` comes
  from the Slack transport settings and is empty in production.
- "Pinned by" names the test that pins the surface through its transport
  boundary. "not yet" names the follow-up task that adds the pin.

## Hard-coded slash commands

Each of these is registered by a module's `register(bot)`. `server/lifespan.py`
calls every such function from `_register_legacy_handlers()`.

| Surface | Defined at | Registration | Target | Rebuild ticket | Pinned by |
| --- | --- | --- | --- | --- | --- |
| `/aws` (subcommands `health`, `users`, `groups`, `lambdas`, `help`) | `modules/aws/aws.py:55` | hard-coded `register(bot)` | `app/features/`: one feature per business concern (account health, Identity Center users/groups, Lambda inventory); TASK-88 sets the boundaries | TASK-88 | not yet — TASK-36.1 |
| `/talent-role` | `modules/role/role.py:37` | hard-coded `register(bot)` | `app/features/talent/` | TASK-39 | not yet — TASK-36.1 |
| `/secret` | `modules/secret/secret.py:24` | hard-coded `register(bot)` | `app/features/secret/` | TASK-39 | not yet — TASK-36.1 |
| `/atip` | `modules/atip/atip.py:39` | hard-coded `register(bot)` | `app/features/atip/` | TASK-39 | not yet — TASK-36.1 |
| `/aiprp` (French alias of `/atip`, same handler) | `modules/atip/atip.py:40` | hard-coded `register(bot)` | `app/features/atip/` | TASK-39 | not yet — TASK-36.1 |
| `/incident` | `modules/incident/incident.py:38` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |

## Interactions (actions, views, events)

All of these are registered inside a module's `register(bot)`, which
`_register_legacy_handlers()` calls.

| Surface | Defined at | Registration | Target | Rebuild ticket | Pinned by |
| --- | --- | --- | --- | --- | --- |
| view `incident_view` | `modules/incident/incident.py:39` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `incident_change_locale` | `modules/incident/incident.py:40` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `handle_incident_action_buttons` | `modules/incident/incident_helper.py:150` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `add_folder_metadata` | `modules/incident/incident_helper.py:151` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `view_folder_metadata` | `modules/incident/incident_helper.py:152` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| view `view_folder_metadata_modal` | `modules/incident/incident_helper.py:153` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| view `add_metadata_view` | `modules/incident/incident_helper.py:154` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `delete_folder_metadata` | `modules/incident/incident_helper.py:155` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| view `view_save_incident_roles` | `modules/incident/incident_helper.py:156` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| view `view_save_event` | `modules/incident/incident_helper.py:157` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `confirm_click` | `modules/incident/incident_helper.py:158` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `user_select_action` | `modules/incident/incident_helper.py:159` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `archive_channel` | `modules/incident/incident_helper.py:160` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| event `reaction_added` (floppy-disk matcher) | `modules/incident/incident_helper.py:161` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| event `reaction_removed` (floppy-disk matcher) | `modules/incident/incident_helper.py:162` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| event `reaction_added` (ack-only fallback) | `modules/incident/incident_helper.py:163` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| event `reaction_removed` (ack-only fallback) | `modules/incident/incident_helper.py:164` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| view `incident_updates_view` | `modules/incident/incident_helper.py:165` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| action `update_incident_field` | `modules/incident/incident_helper.py:166` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| view `update_field_modal` | `modules/incident/incident_helper.py:167` | hard-coded `register(bot)` | `app/features/incident/` | TASK-38 (after TASK-97) | not yet — TASK-36.1 |
| view `create_webhooks_view` | `modules/sre/webhook_helper.py:26` | hard-coded `register(bot)` | `app/capabilities/webhooks/` (admin surface) | TASK-37 (cutover TASK-37.4) | not yet — TASK-36.1 |
| action `toggle_webhook` | `modules/sre/webhook_helper.py:27` | hard-coded `register(bot)` | `app/capabilities/webhooks/` (admin surface) | TASK-37 (cutover TASK-37.4) | not yet — TASK-36.1 |
| action `reveal_webhook` | `modules/sre/webhook_helper.py:28` | hard-coded `register(bot)` | `app/capabilities/webhooks/` (admin surface) | TASK-37 (cutover TASK-37.4) | not yet — TASK-36.1 |
| action `next_page` | `modules/sre/webhook_helper.py:29` | hard-coded `register(bot)` | `app/capabilities/webhooks/` (admin surface) | TASK-37 (cutover TASK-37.4) | not yet — TASK-36.1 |
| action `channel` (ack only) | `modules/sre/webhook_helper.py:30` | hard-coded `register(bot)` | `app/capabilities/webhooks/` (admin surface) | TASK-37 (cutover TASK-37.4) | not yet — TASK-36.1 |
| action `hook_type` (ack only) | `modules/sre/webhook_helper.py:31` | hard-coded `register(bot)` | `app/capabilities/webhooks/` (admin surface) | TASK-37 (cutover TASK-37.4) | not yet — TASK-36.1 |
| view `aws_health_view` | `modules/aws/aws.py:56` | hard-coded `register(bot)` | `app/features/` account-health feature (boundary set by TASK-88) | TASK-88 | not yet — TASK-36.1 |
| view `role_view` | `modules/role/role.py:38` | hard-coded `register(bot)` | `app/features/talent/` | TASK-39 | not yet — TASK-36.1 |
| action `role_change_locale` | `modules/role/role.py:39` | hard-coded `register(bot)` | `app/features/talent/` | TASK-39 | not yet — TASK-36.1 |
| action `secret_change_locale` | `modules/secret/secret.py:25` | hard-coded `register(bot)` | `app/features/secret/` | TASK-39 | not yet — TASK-36.1 |
| view `secret_view` | `modules/secret/secret.py:26` | hard-coded `register(bot)` | `app/features/secret/` | TASK-39 | not yet — TASK-36.1 |
| action `ati_search_width` | `modules/atip/atip.py:41` | hard-coded `register(bot)` | `app/features/atip/` | TASK-39 | not yet — TASK-36.1 |
| view `atip_view` | `modules/atip/atip.py:42` | hard-coded `register(bot)` | `app/features/atip/` | TASK-39 | not yet — TASK-36.1 |
| action `atip_change_locale` | `modules/atip/atip.py:43` | hard-coded `register(bot)` | `app/features/atip/` | TASK-39 | not yet — TASK-36.1 |

Totals: 18 actions, 12 views and 4 events, 34 interactions in all.

## Webhook route

| Surface | Defined at | Registration | Target | Rebuild ticket | Pinned by |
| --- | --- | --- | --- | --- | --- |
| `POST /hook/{webhook_id}`, served at both `/hook/...` and `/api/v1/hook/...` | `api/v1/routes/webhooks.py:41` (mounted in `api/v1/router.py`) | FastAPI route | `app/capabilities/webhooks/` | TASK-37 (cutover TASK-37.4); app/api/ removal TASK-53 | not yet — TASK-36.2 (partial: `tests/api/v1/test_webhooks.py`) |

## Scheduled job entry points

| Surface | Defined at | Registration | Target | Rebuild ticket | Pinned by |
| --- | --- | --- | --- | --- | --- |
| `provision_aws_identity_center` (every 2h, Tier-2 lease; calls `modules.aws.identity_center.synchronize`) | `jobs/scheduled_tasks.py:101` (body `:157`) | scheduler | `app/features/` Identity Center provisioning feature (boundary set by TASK-88) | TASK-88; job strangle TASK-65; runtime TASK-52 | not yet — TASK-36.3 |
| `notify_stale_incident_channels` (daily 16:00, Tier-2 lease; `modules.incident`) | `jobs/scheduled_tasks.py:104` | scheduler | `app/features/incident/` | TASK-38 (after TASK-97); job strangle TASK-65; runtime TASK-52 | not yet — TASK-36.3 |
| `spending.execute_spending_data_update_job` (daily 00:00, Tier-2 lease; `modules.aws.spending`) | `jobs/scheduled_tasks.py:109` | scheduler | `app/features/` spending-report feature (boundary set by TASK-88) | TASK-88; job strangle TASK-65; runtime TASK-52 | not yet — TASK-36.3 |
| `access_sync_reconciliation` (daily, settings-driven) | `packages/access/sync/__init__.py:94` | plugin job (`register_background_jobs` hookimpl) | `app/features/access/` (sync) | TASK-124.1; runtime TASK-52 | not yet — TASK-36.3 |
| `oncall_sync` (interval) | `packages/oncall_sync/__init__.py:34` | plugin job (`register_background_jobs` hookimpl) | `app/features/oncall_sync/` | TASK-124.2 (rotations dependency TASK-123); runtime TASK-52 | not yet — TASK-36.3 |

The runtime in `jobs/scheduled_tasks.py` also schedules the host-owned Tier-1
jobs `scheduler_heartbeat` and `integration_healthchecks`. Neither is a module
surface, and TASK-52 moves both to `app/server/scheduler/`.

## Provider-registered Slack commands

Each `register_slack_commands` hookimpl, and each module that
`_register_legacy_slack_commands` calls, delegates to a package-local
`register_commands(provider)`. When
the `/sre` root is called with no subcommand, or with `help`, the provider
generates the help text.

| Surface | Defined at | Registration | Target | Rebuild ticket | Pinned by |
| --- | --- | --- | --- | --- | --- |
| `/sre` root; `/sre version`, `/sre incident` (legacy mode), `/sre webhooks` (legacy mode) | `modules/sre/__init__.py:7` → `modules/sre/platforms/slack.py:183` | hard-coded `_register_legacy_slack_commands` | split: `version` → `app/server/` (system info, like `GET /version`); `incident` → `app/features/incident/`; `webhooks` → `app/capabilities/webhooks/` (admin surface) | `version` TASK-40; `incident` TASK-38; `webhooks` TASK-37.4 | `test_slack_command_registration_surface.py` `-k "sre_ or registered_once or prefix or tree"` |
| `/sre dev` with `google`, `slack`, `stale`, `incident`, `load-incidents`, `add-incident` (dev environment only) | `modules/dev/__init__.py:11` → `modules/dev/platforms/slack.py:291` | hard-coded `_register_legacy_slack_commands` | delete: dev-environment test commands with no production users (TASK-40 records the drop) | TASK-40 | `test_slack_command_registration_surface.py` `-k dev_` |
| `/rant` (root command, no parent) | `packages/rant/__init__.py:9` → `packages/rant/platforms/slack.py:19` | hookimpl | `app/features/rant/` | TASK-124.3 | `test_slack_command_registration_surface.py` `-k rant` |
| `/sre rotations`; `/sre rotations view <usergroup_handle>` | `packages/user_rotations/__init__.py:7` → `packages/user_rotations/platforms/slack.py:18` | hookimpl | `app/capabilities/rotations/` | TASK-123 | `test_slack_command_registration_surface.py` `-k rotations` |
| `/sre access` (parent, shared by the access subpackages); `/sre access sync`; `sync user <user_email> <platform> [--dry-run]`; `sync platform <platform> [--dry-run]`; `sync status <job_id>` | `packages/access/sync/__init__.py:26` → `packages/access/sync/interactions/slack.py:38` | hookimpl | `app/features/access/` (sync) | TASK-124.1 | `test_slack_command_registration_surface.py` `-k access_sync` |
| `/sre incident draft [--limit]` | `packages/incident/scribe/__init__.py:17` → `packages/incident/scribe/platforms/slack.py:85` | hookimpl | `app/features/incident/` (scribe) | TASK-124.5 | `test_slack_command_registration_surface.py` `-k incident_draft` |
| `/sre incident summarize [--since] [--limit]` | `packages/incident/scribe/__init__.py:17` → `packages/incident/scribe/platforms/slack.py:104` | hookimpl | `app/features/incident/` (scribe) | TASK-124.5 | `test_slack_command_registration_surface.py` `-k incident_summarize` |
| `/sre geolocate <ip_address>` | `packages/geolocate/__init__.py:14` → `packages/geolocate/platforms/slack.py:20` | hookimpl | `app/features/geolocate/` | TASK-124.6 | `test_slack_command_registration_surface.py` `-k geolocate` |

## Other `app/api/` routes

These routes are not owned by a module. They are listed because TASK-53
expects this inventory to cover every route under `app/api/`.

| Surface | Defined at | Registration | Target | Rebuild ticket | Pinned by |
| --- | --- | --- | --- | --- | --- |
| `GET /geolocate/{ip}` (legacy router, no prefix) | `api/v1/routes/geolocate.py:13` | FastAPI route | `app/features/geolocate/` | TASK-53 (feature move TASK-124.6) | existing route tests: `tests/api/v1/test_geolocate.py`, `tests/integration/api/v1/test_geolocate_routes.py` |
| `GET /version` | `api/routes/system.py:12` | FastAPI route | `app/server/` | TASK-53 | existing route test: `tests/api/routes/test_system.py` |
| `GET /health` | `api/routes/system.py:20` | FastAPI route | `app/server/` | TASK-53 | existing route test: `tests/api/routes/test_system.py` |
| `GET /` (landing page) | `api/routes/landing.py:441` | FastAPI route | `app/server/` | TASK-53 | existing route test: `tests/api/routes/test_landing.py` |

## Running this suite

Run the full suite:

```bash
cd app && uv run pytest tests/integration/legacy_surface -v
```

To check one surface before or after its cutover, select its tests with the
`-k` keyword from its "Pinned by" column:

```bash
cd app && uv run pytest tests/integration/legacy_surface -v -k <keyword>
```

For a surface's cutover PR, run the full suite immediately before the PR and
again immediately after it. This is the "smoke tests stay green" check in step
4 (Cut over) of the per-surface recipe in `decisions/migration.md`. If the
suite fails after the cutover, the surface's external behaviour has changed.
