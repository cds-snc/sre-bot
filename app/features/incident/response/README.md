# incident.response

The responders' subdomain while an incident is open (decisions/incident-management.md). It
rebuilds the legacy `modules/incident` surfaces one cutover at a time (TASK-145.7, 145.8).

## Commands

| Command | Does | Code |
| --- | --- | --- |
| `/sre incident status update <status>` | Changes the status of the channel's incident: the record, then the report's status line, the incident list's status cell and a notice in the incident channel. One private reply names the outcome and any write that was skipped or failed. | `entrypoints/slack.py`, `service/status.py` |
| `/sre incident roles manage` | Opens the roles modal (callback `incident.response.roles`): five user pickers, the incident commander and operations lead required, the communications lead, policy lead and postmortem owner optional, preselected from the record. The submission writes the five roles to the record, announces each role whose holder changed and rewrites the channel purpose's `IC: ... / OL: ...` line. | `entrypoints/slack_roles.py`, `service/roles.py` |
| `/sre incident roles`, `roles show` | The command's generated help (the `roles show` stub is retired). | `entrypoints/slack_roles.py` |
| `/sre incident close` and the stale notice's archive button | Closes the channel's incident and archives its channel: joins the channel, sets the status to Closed (the record, the report line, the list and a notice), posts the archived notice, archives the channel and sends one `incident_channel_archived` event. The button is the legacy attachment `archive_channel`, registered as `incident.response.archive` with the alias scoped to its `archive` value; its texts are in the instance languages and order, since a button press names no locale (decisions/languages.md). | `entrypoints/slack_archive.py`, `service/archive.py`, `adapters/sentinel.py` |
| `/sre incident show` and its update modal | Opens the information modal on the channel's incident (callback `incident.response.show`): the report and Meet links, the five roles, severity, status, security flag and times, each changeable field with an Update button (`incident.response.update_field.open`). The button pushes a field modal (callback `incident.response.update_field`): a select, or one date-and-time picker for a time. The submission writes the record, posts a notice in the instance languages to the incident channel and refreshes the information modal; the status field goes through `change_status`. | `entrypoints/slack_show.py`, `entrypoints/slack_show_views.py`, `service/fields.py` |
| `/sre incident status`, `status show` | The command's help. A bare valid status (`status Closed`, retired after 2025-11-01) answers a pointer to `status update` and changes nothing; TASK-145.13 deletes the pointer. | `entrypoints/slack.py` |

## Status changes

`service/status.py` holds `change_status`, the one status engine. The slash command and
the archive and the update modal's status field call it.

- The record write is the commit point: a refused command check or a failed record write
  stops and nothing else is written.
- The report line, the list and the channel follow in that order. Each failure is logged
  (`incident_status_stage_failed`) and reported, never rolls the record back, and the next ones
  still run. Running the same status again repairs them.
- The notice goes to the record's conversation, only when the bot can write to it.

## Roles

`service/roles.py` holds `assign_roles`, the one roles engine; the modal's submission calls it.

- The record write (`IncidentStore.set_roles`, all five roles in one guarded write) is the
  commit point: a refused command check or a failed record write stops and nothing is posted.
- Then, only when the incident's conversation is writable, one announcement per role whose
  holder differs from what the modal showed, in role order, and the purpose's `IC: ... / OL: ...`
  line (`purpose_with_roles`: appended after a space and a newline, or replaced in place, cut to
  250 characters, as the legacy command wrote it). Failures are logged and told to the
  submitter privately, never roll the record back.
- What the modal shows is `read_incident_roles` (`core/api.py`): the record's roles, or for an
  incident with no role on the record the report's Drive properties `ic_id` and `ol_id` through
  the legacy-only `LegacyRolesReader`. Nothing writes those properties. The legacy upgrade job's
  roles step (TASK-145.7.12) backfills them into the record on the same condition, through the
  same reader, and TASK-145.13 deletes the reader and the read (`providers.legacy_roles_reader`).

## Show and update

`entrypoints/slack_show.py` registers `show`, the Update buttons and the field modal's
submission; `entrypoints/slack_show_views.py` builds the views; `service/fields.py` holds
`update_fields`.

- `show` answers in the invoker's language (matched by the language policy); the modal carries that locale in its private
  metadata (with the channel, never the incident, which each press and submission read
  fresh), and the private lines of the flow use it.
- A field change writes the record first: the status through `change_status`, the severity,
  the three times and the security flag through `IncidentStore.update_fields` (a severity
  change appends its `severity_changed` timeline entry). Then the notice, in the instance languages and order
  since the channel is shared (decisions/languages.md), only when the channel is writable. A refused
  or failed record write, a lost guard and a skipped or failed follower are told to the
  submitter privately; nothing retries.
- A time is picked with one `datetimepicker`, which returns the instant itself, so no user
  time zone is looked up; the notice names it with a Slack date token.
- The information modal is refreshed from the incident as written. A refresh after the user
  closed it fails with `not_found`, an expected outcome logged at info.
- The security flag is a yes/no field anyone who passes the command check may change; a flip
  triggers nothing beyond the record and the notice (decisions/incident-management.md).
- Severity options are `none`, then `sev-0` to `sev-4`, one list (`SEVERITY_OPTIONS`) shared
  with the declare form.

## Archive

`service/archive.py` holds `archive_incident`; `/sre incident close` and the archive button call it.

- Find the conversation's incident (a refusal writes nothing and sends no event), join the
  channel (`IncidentConversation.join`: no call when the bot is a member), then `change_status`
  to Closed: the record write is the commit point.
- A failed join never stops the record: the incident is closed, the archived notice and the
  archive are skipped as `not_joined` and the reply says so.
- Then the archived notice and the archive; `incident_channel_archived` is sent once, only after a
  successful archive, through `adapters/sentinel.py` (`{event, message}` with the incident,
  conversation, user and time only; TODO(TASK-122): the audit capability's sink).

## Declare

`service/declare.py` holds `declare`; `entrypoints/slack_declare.py` serves it on Slack. It names
no platform: the caller passes a `DeclareRequest`, the ports (`DeclarePorts`, built by
`providers.declare_ports`; `chat` is `None` without a chat platform), the `DeclarePolicy` from
`[incident_response]` and the texts (`DeclareTexts`; `entrypoints/slack_declare_texts.py` on Slack).

- The record first, under `incident_id_for(idempotency_key)`, with the declarer as incident
  commander: the commit point, never rolled back.
- Then the conversation (`service/conversation.py`, `ensure_conversation`: the five
  one-conversation rules) and its primary binding, who is on call for the placement's schedule
  (`PlacementScheduleLookup`, then the on-call capability), the report filed in the placement with
  its placeholders, the video call, the conversation's set-up, links and messages, the invites,
  and last the list row, written whatever failed before it.
- A failed step leaves its reference empty and is reported in `Declared`; the declare continues.
- Running it again with the same key is the retry: a step whose reference is set is skipped and
  each one-time message is posted once (a claim per message through `Claims`). One run per
  incident at a time: a second is refused with `DECLARE_IN_PROGRESS`.
- Invites, each account once: the declarer, the on-call people (by account, or by email through
  `IncidentConversation.account_ids_for`), the security group for a security incident, the policy
  group when policy help is asked and the Notify management group for the Notify placement, each
  group only when its id is configured. A missing schedule or a failing source invites nobody on
  call and posts `on_call_unavailable`.
- The first status is `[incident_response] initial_status` (Open or In Progress, default Open).
- Each post to a conversation is rendered in that conversation's languages
  (`ChatSurface.languages`, the instance language policy); the announcement channel has its own.

Slack (`entrypoints/slack_declare.py`, views in `slack_declare_views.py`):

- `/incident <name>` (a host root command) opens a loading view on the trigger, then the form
  (callback `incident.response.declare`): name, product (the report placements), severity with
  SEV0, security and policy-help questions, the handbook link. Its locale button
  (`incident.response.locale`, legacy alias `incident_change_locale`) re-renders it in the other
  language, keeping the name.
- The submission is validated before its single ack (the name's field error in the instance
  languages), then declared with the view id as idempotency key. The success view opens on the
  submission's trigger; a refused record or a missing channel is told to the declarer in a direct
  message; a failed later step posts a warning in the incident channel.
- The alert buttons (`incident.response.alert_buttons`, legacy alias
  `handle_incident_action_buttons`, which the webhook producer posts): `call-incident` opens the
  form named after the alert with its channel and message, which become the source alert;
  `ignore-incident` claims the message (`incident:alert_ignore:<channel>:<ts>`), counts one
  acknowledgement on the first press (`AlertAcknowledgements`, `adapters/alert_acknowledgements.py`
  over the webhooks table; approximate, decisions/webhooks.md section 8; TODO(TASK-37.6.2)), and
  replaces the buttons with who ignored it.
- Each handler sends its Sentinel event (`incident_called`, `call_incident_button_pressed`,
  `ignore_incident_button_pressed`) with ids only, through `DeclareEventSink`.

## Layout

- `plugin.py`: the entry point `incident.response` (requirements, the new-incident policy
  check, the status, roles, close and show commands, the archive button, the update modal, the
  `incident_response` catalogue,
  the legacy upgrade job).
- `entrypoints/slack.py`: the status commands and the registration; `entrypoints/slack_roles.py`:
  the roles command and modal; `entrypoints/slack_archive.py`: close and the archive button;
  `entrypoints/slack_show.py` and `slack_show_views.py`: show and the update modal;
  `entrypoints/scope.py`: the service scope they open and the language policy. Every post to
  the incident channel (status, field and archived notices, role announcements) is in the
  channel's shared languages, in order; replies and modals come from `locales/` in the invoker's
  language, or the instance languages when the payload names none (decisions/languages.md).
- `service/status.py`: `change_status`; `service/fields.py`: `update_fields`; `service/roles.py`:
  `assign_roles`; `service/archive.py`: `archive_incident`; `service/declare.py`: `declare`;
  `service/conversation.py`: `ensure_conversation`.
- `interfaces.py`: `ArchiveEventSink` and `ArchivedEvent`, and `DeclareEventSink`,
  `adapters/sentinel.py` implements both; `AlertAcknowledgements`,
  `adapters/alert_acknowledgements.py` implements it;
  `Claims` (async claims), `adapters/claims.py` implements it over the `IdempotencyStore`;
  `DeclareTexts`, the declare's words, which the cutover's entry points render.
- `providers.py`: the core report, list projection, conversation, video call, placement schedule
  lookup and legacy roles reader, the on-call lookup, claims over the scope's conditional-write
  store, the declare policy and ports, the alert acknowledgements, and the archive and declare
  event sinks, the services use; tests substitute them here.
- `settings.py`, `legacy_upgrade_job.py`: see the umbrella README.
