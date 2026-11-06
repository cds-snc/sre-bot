# Incident comms

The comms subdomain of the incident umbrella
([`../README.md`](../README.md), `decisions/incident-management.md`, External
status updates): the public status updates of an incident. A responder writes
each update in a Slack modal; AI is an optional assist inside the form.

- `/sre incident status-update` opens the incident's status-updates modal:
  start, save, fill with AI, approve, copy and mark published.

Paths are relative to `app/features/incident/comms/` unless they start with
`core/` (`app/features/incident/core/`) or `tests/` (`app/tests/`).

## Architecture

Per `decisions/feature-packages.md`, `decisions/transport-slack.md` and
`decisions/incident-management.md`.

### Call path

```
Slack  /sre incident status-update, modal buttons, Approve submission
  │
  ▼
entrypoints/slack.py      parse payload → typed values → one service call → OperationResult → render (slack_views.py, i18n)
  │                         one service scope per call: RecordStore + ConfiguredSystems → IncidentStore, ConversationReference, StatusUpdateStore
  │
  ▼
service/ (draft, form, approval, publication, history)      platform-agnostic; no Slack or OpenAI imports
  │
  ├─► IncidentStore and StatusUpdateStore (passed in), IncidentTranscriptReader ── core/api.py
  ├─► TextGenerator ──────── providers.py ──► adapters/text_generation.py   (integrations.openai)
  └─► StatusPagePublisher ── providers.py ──► adapters/copy_ready.py         (domain.render_copy_ready)
```

### Files

- `__init__.py` — pluggy hookimpls only: `register_slack_commands` and
  `register_i18n_resources`. The plugin is loaded from the `incident.comms`
  entry point under `[project.entry-points.sre_bot]` in `app/pyproject.toml`
  (`decisions/plugins.md`); no import-time side effects.
- `entrypoints/slack.py` — the `status-update` command handler registered
  under `sre.incident`, and the status-updates modal's block-action and
  view-submission listeners, all by one `register`. Each handler acks, makes
  one service call and updates the modal; no `slack_sdk` import. A handler
  that resolves the channel's incident opens one service scope, builds the
  `IncidentStore` there with `build_incident_store` and the channel's
  `ConversationReference` under the configured Slack tenant, and passes both
  to the service. Without a configured Slack tenant `register` registers
  nothing and logs `incident_comms_registration_skipped` naming
  `[slack.tenant] team_id`.
- `entrypoints/slack_views.py` — the Block Kit view builders, payload parsers,
  action ids (`incident.comms.status_update.*`) and every translated string,
  reached through `core.api.translate` (no comms module imports
  `infrastructure.i18n`). No Slack SDK import.
- `service/` — the status-update use cases, one module per use case; nothing
  in it imports Slack or an integration, and only `core/api.py` from `core`:
  - `service/draft.py` — `start_status_update_draft` (the pending draft, or the
    latest approved update stored as the next draft for a responder to write),
    `save_status_update_draft` (the typed fields as the next draft) and
    `generate_status_update_draft` (Draft with AI: carries the typed fields
    forward when nothing is new, otherwise one model call fills them), each
    storing a `StatusUpdate` record. Only messages posted by people after the
    latest approved update's cutoff count as new; thread replies are not read.
  - `service/form.py` — the review form each form action shows, as a
    `StatusUpdateFormState`: `start_status_update_form`, `open_status_update_form`,
    `save_status_update_form` and `fill_status_update_form`. A save or fill that
    changes nothing keeps the stored draft overlaid with the typed values, with
    the code that explains it, so a surface handler makes one call and renders.
  - `service/approval.py` — reading a draft for review and approving it (stops
    at `APPROVED`, never publishes); `approve_and_publish` also renders the
    approved update as copy-ready EN/FR text in one call.
  - `service/publication.py` — reopening an approved update and `set_published`,
    the copy-ready text's toggle: one store transition between `APPROVED` and
    `PUBLISHED` (recording or clearing `published_at`/`published_by`), with the
    button carrying the target state. It records a person's confirmation that
    they posted the text; nothing is posted to the channel. `read_published` and
    `set_published_and_render` return the record with its copy-ready text in one call.
  - `service/history.py` — `get_status_update_overview`: the pending draft and
    the approved updates, newest first; it drafts nothing.
  - `service/prompt.py` — the status-update prompt and its strict answer
    parser, which rejects any partial or malformed answer.
- `domain.py` — frozen values: `StatusUpdateDraftOutcome` and its
  `StatusUpdateOutcomeKind`, `DraftedFields` (model output) and
  `StatusUpdateEdit` (a responder's submission, with `blank_fields`), kept
  apart on purpose, `NoNewInformationWording`, `CopyReadyText`,
  `StatusUpdateOverview`, `StatusUpdateFormState`, `PublishedRecord`; and the
  default comms profile: `ProfileLabels` and the pure rendering of a status
  update as public text (its sections and the next-update time in Eastern
  time, from labels the caller has already localized), with
  `render_copy_ready`, which every `StatusPagePublisher` renders through. The
  `StatusUpdate` record itself comes from `features/incident/core`.
- `interfaces.py` — the comms-owned interfaces: `TextGenerator` and
  `StatusPagePublisher`.
- `adapters/text_generation.py` — binds `TextGenerator` to the OpenAI
  `Summarizer`; the subdomain's only integration import.
- `adapters/copy_ready.py` — the `StatusPagePublisher` that renders copy-ready
  text for a person to paste; it calls no status page.
- `providers.py` — feature-local DI wiring for the text generator
  (`text_generation_available`) and the publisher.
- `settings.py` — `IncidentStatusUpdateSettings` and its cached getter.
- `locales/` — the EN/FR `incident_status_update` catalogue, loaded by one
  `register_i18n_resources` registration (resource domain `incident_comms`).

Tests live in `tests/unit/features/incident/comms/` and
`tests/integration/features/incident/comms/` (`test_incident_comms_*`).

## Naming note

The subdomain is `comms`, but names that shipped before the carve-out stay, so
nothing deployed has to change: the settings prefix `INCIDENT_STATUS_UPDATE__`
(environment variable names), the `incident_status_update` catalogue (the i18n
key prefix, `STATUS_UPDATE_DOMAIN`) and the stored `StatusUpdate` records. The
action and callback ids did change, from `incident.scribe.status_update.*` to
`incident.comms.status_update.*`: a modal left open across that deploy stops
responding and is reopened with the command.

## Reference

### `/sre incident status-update`

A responder writes the update; AI is an optional assist inside the form
(`decisions/incident-management.md`, External status updates; TASK-144).
Nothing is posted to the incident conversation.

Opens the incident's status-updates modal, private to the invoker. The handler
opens a loading view at once with the command's trigger id (it expires after
about three seconds), then `get_status_update_overview` in `service/history.py`
resolves the incident and reads its records. The view is updated to the
overview: the pending draft with its origin line, rendered in English then
French by the default comms profile (`domain.py`), or a localized
no-draft notice, then the approved updates; or to a localized error with a
Close button (outside an incident channel, ambiguous incident, store failure).
Opening never drafts. Strings live in
`locales/incident_status_update.{en-US,fr-FR}.yml`; `t()` is called only in
`entrypoints/slack_views.py`.

Overview: with no pending draft the only button is New update
(`incident.comms.status_update.new`); with one it is Review
(`incident.comms.status_update.review`), which opens the review form. There
is no Draft button on the overview.

Origin line: above a pending draft the modal says who made it, how and when
("Written by @user", "Drafted by AI", "Redrafted with instructions", "Carried
forward", with the creation time in Eastern time); a record written before
origins existed names only its author.

New update: `start_status_update_draft` makes no model call and reads no
security flag. It stores the latest approved update (blank at Investigating
for the first one) as the next draft with origin `HAND`, or returns the draft
another responder started meanwhile, and the modal switches to the review form.
A first update with no message from a person yet is refused with the
empty-history notice.

Draft with AI: the review form opens with an AI section only when text
generation is configured (`text_generation_available`): an optional
instructions input and a Draft with AI button
(`incident.comms.status_update.generate`). Without it the form has the stage,
the fields, Save draft and Approve only. `generate_status_update_draft` takes
the typed values as the base. With no new message from a person since the
latest approved update and no instructions, it carries the typed values
forward with the no-new-information wording and makes no model call;
otherwise it makes one model call over the conversation since that update,
with the instructions when given, keeps the stage floor and strict parsing,
and stores the result as the next draft. The modal shows a generating view
only while the model runs.

Security gate: before a model call, `generate_status_update_draft` reads the
flag with `IncidentStore.read_security_flag` and refuses a security incident,
or one whose flag cannot be read, with
`SECURITY_CONFIRMATION_REQUIRED` unless called with `security_confirmed=True`.
A legacy incident stored without the flag reads as not a security incident.
The form then comes back with a warning and a confirmation checkbox; pressing
Draft with AI with the box checked confirms. A hand-written or saved draft and
its approval need no confirmation. Any refusal or failure keeps the previous
draft and re-renders the typed values with a notice.

Save draft: the review form ends with a Save draft button
(`incident.comms.status_update.save`); Approve stays the only submit.
`save_status_update_draft` stores the typed stage and fields, blanks included,
as the next draft with origin `HAND`, and the form re-renders for the new
sequence with a "Draft saved." notice. A form opened on an older sequence shows
the conflict view; any other failure re-renders the typed values with a notice
and stores nothing. Only the modal is updated.
