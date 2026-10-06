# Incident scribe

The scribe subdomain of the incident umbrella
([`../README.md`](../README.md), `decisions/incident-management.md`):
AI-assisted commands that work from an incident channel's transcript, read
through `packages/incident/core`.

- `/sre incident draft` writes a filled-in copy of the incident report.
- `/sre incident summarize` gives a responder joining the incident a catch-up
  summary.

## At a glance

Paths are relative to `app/packages/incident/scribe/` unless they start with
`core/` (`app/packages/incident/core/`) or `tests/` (`app/tests/`).

| | `/sre incident draft` | `/sre incident summarize` |
| --- | --- | --- |
| Slack handler | `handle_draft_command` in `platforms/slack.py` | `handle_summarize_command` in `platforms/slack.py` |
| Service function | `draft_incident_document_from_conversation` → `draft_incident_document` in `service.py` | `summarize_incident_conversation` → `summarize_transcript` in `service.py` |
| Interfaces | `IncidentReportLinkLookup`, `IncidentDocumentStore` (`service.py`); `IncidentTranscriptReader` (`core/api.py`); `Summarizer` (`integrations.openai`) | `IncidentTranscriptReader` (`core/api.py`); `Summarizer` (`integrations.openai`) |
| Adapters | `adapters/slack.py` (report link from bookmarks), `adapters/google_docs.py` (read report, copy, fill copy), `core/adapters/slack.py` (transcript), `app/integrations/openai/` | `core/adapters/slack.py` (transcript), `app/integrations/openai/` |
| Wiring | `providers.py`: `get_incident_report_link_lookup`, `get_incident_document_store`; `core/api.py`: `get_incident_transcript_reader` | `core/api.py`: `get_incident_transcript_reader` |
| Settings | `IncidentDraftSettings`, prefix `INCIDENT_DRAFT__` | `IncidentSummarySettings`, prefix `INCIDENT_SUMMARY__` |
| Locale files | `locales/incident_draft.en-US.yml`, `locales/incident_draft.fr-FR.yml` | `locales/incident_summary.en-US.yml`, `locales/incident_summary.fr-FR.yml` |
| Tests (`tests/unit/packages/incident/scribe/`) | `test_incident_scribe_draft_{service,adapter,slack,settings,locales}.py`, `test_incident_scribe_conversation_draft.py`, `test_incident_scribe_providers_document_store.py`, `test_incident_scribe_slack_adapter_lookup.py` | `test_incident_scribe_summary_{service,slack,settings,locales}.py`, `test_incident_scribe_conversation_summarize.py` |
| Details | [Reference: draft](#sre-incident-draft) | [Reference: summarize](#sre-incident-summarize) |

Both use cases share `test_incident_scribe_plugin_registration.py`.

## Architecture

Per `decisions/feature-packages.md`, `decisions/transport-slack.md` and
`decisions/incident-management.md`.

### Call path

```
Slack  /sre incident draft | summarize
  │
  ▼
platforms/slack.py        parse args → typed values → one service call → OperationResult → render (i18n)
  │
  ▼
service.py                platform-agnostic; no Slack, HTTP or Google SDK imports
  │
  ├─► IncidentTranscriptReader ── core/api.py ──► core/adapters/slack.py        (Slack history)
  ├─► Summarizer ─────────────── integrations.openai                            (text generation)
  │
  │   draft only:
  ├─► IncidentReportLinkLookup ── providers.py ──► adapters/slack.py            (bookmarks)
  └─► IncidentDocumentStore ───── providers.py ──► adapters/google_docs.py      (Docs read, Drive copy, Docs fill)
```

### Files

- `__init__.py` — pluggy hookimpls only: `register_slack_commands` and
  `register_i18n_resources`. The plugin is loaded from the `incident.scribe`
  entry point under `[project.entry-points.sre_bot]` in `app/pyproject.toml`
  (`decisions/plugins.md`); no import-time side effects.
- `platforms/slack.py` — both five-step handlers, registered under
  `sre.incident` by one `register_commands`; the draft handler posts the
  progress notice when the service signals the start; ephemeral responses; no
  `slack_sdk` import.
- `service.py` — both use cases and the two scribe-owned interfaces
  (`IncidentDocumentStore`, `IncidentReportLinkLookup`). The only module of the
  subdomain that imports `packages/incident/core`, through `core/api.py`.
  Empty history returns an `OperationResult` with `error_code="EMPTY_HISTORY"`.
- `domain.py` — frozen values of the drafting use case: `DocumentSection`
  (heading + instructions), `SectionDraft`, `DocumentField`,
  `DraftWriteResult`, `DraftedDocument`. `TranscriptMessage` comes from
  `packages/incident/core`.
- `adapters/slack.py` — the report-link lookup on Slack bookmarks; returns
  plain strings and no links on an API error.
- `adapters/google_docs.py` — the only file touching **Google**
  (Docs read + Drive copy + Docs populate). `service.py` imports the
  `Summarizer` interface and `platforms/slack.py` the transport models, both by
  design.
- `providers.py` — feature-local DI wiring for the document store and the
  report-link lookup.
- `settings.py` — partitioned feature settings, one class and one cached getter
  per use case.
- `locales/` — EN/FR message catalogues, one pair per use case. One
  `register_i18n_resources` registration (resource domain `incident_scribe`)
  loads every `<catalogue>.<locale>.yml` file in the directory.

## Adding a use case

1. **Service.** Add the use case's function to `service.py`, taking typed
   values and returning `OperationResult`. Declare any new interface as a
   `Protocol` beside it. Read the channel through `IncidentTranscriptReader`
   from `core/api.py` and generate text through `Summarizer`; import nothing
   else from `core`.
2. **Domain values.** Add frozen dataclasses to `domain.py` only if the use
   case needs its own values.
3. **Adapters.** A new external call goes in `adapters/<system>.py`, wired
   through a cached getter in `providers.py`. If a second incident subdomain
   will need the same interface, it belongs in `core/` instead (see
   [Where does new work go](../README.md#where-does-new-work-go)).
4. **Settings.** Add a `BaseSettings` class and an `lru_cache` getter to
   `settings.py`, with its own `INCIDENT_<USE_CASE>__` prefix. Do not reuse
   another use case's class.
5. **Slack.** Add the handler to `platforms/slack.py` and one
   `registrar.register_command(..., parent="sre.incident")` call inside
   `register_commands`. No new hookimpl is needed.
6. **Locales.** Add `locales/<catalogue>.en-US.yml` and
   `locales/<catalogue>.fr-FR.yml`. The existing `register_i18n_resources`
   picks them up.
7. **Tests.** Add `app/tests/unit/packages/incident/scribe/test_incident_scribe_<use_case>_<action>.py`
   for service, Slack handler (success and error mapping), settings and locales.
8. **This README.** Add a column to [At a glance](#at-a-glance) and a section
   under [Reference](#reference).

## Naming note

The subdomain is `scribe`, but the two original use cases kept the names they
shipped with, so nothing deployed has to change:

- Settings prefixes `INCIDENT_DRAFT__` and `INCIDENT_SUMMARY__` (and the
  classes `IncidentDraftSettings`, `IncidentSummarySettings`) are environment
  variable names already set in deployed configuration.
- The `incident_draft` and `incident_summary` catalogues are the i18n key
  prefixes the handlers look up (`_DRAFT_DOMAIN`, `_SUMMARY_DOMAIN` in
  `platforms/slack.py`).
- The `incident_draft::` named-range prefix (`adapters/google_docs.py`) is
  already written into existing draft documents.

Renaming any of them would be a migration, not a docs change. New use cases are
named after themselves, not after `scribe`.

## Reference

The behaviour detail for each use case.

### `/sre incident draft`

Adds `/sre incident draft`: from inside an incident channel, reads the
incident Google Doc created at channel creation, treats the guidance written
under each heading as that section's drafting instructions, answers each one
from the incident channel's messages, and writes the filled-in result into a
**new** document. The original report is read, not rewritten.

#### Usage

```
/sre incident draft                # draft from the whole incident history
/sre incident draft --limit 200    # draft from at most 200 messages
```

History starts at the channel's creation, so the draft covers the whole
incident; `--limit` caps how many messages are read (itself capped at
`MAX_HISTORY_LIMIT`).

The invoker gets an ephemeral notice while the work runs — the AI call alone
takes most of a minute — then a one-line confirmation linking the draft and
asking them to carry changes back into the original incident document.

#### Sections left for humans

**Five whys / root causes** and **Lessons Learned** (*What went well*, *What
went wrong*, *Where we got lucky*) are never drafted. They are judgement calls
the team makes together in the retro, not conclusions to be inferred from a
transcript, so those sections are filtered out before the request is built —
the model never sees them, and nothing is written into them. Their template
guidance is left exactly as it is, ready for a human.

#### How it works

1. **Locate and read the channel.** The handler makes one service call. The
   service finds the incident document via the channel's "Incident report"
   bookmark (the package's `IncidentReportLinkLookup` interface), then reads
   the transcript through the `IncidentTranscriptReader` interface of
   `packages/incident/core`: fetched from channel creation, display names
   resolved, each message carrying its time, and noise removed:

   - **This bot's own messages** — topic changes, hangout links, "an incident
     report has been created at…". Matched on *any* of `user_id`, `bot_id` or
     normalised display name, because a message may carry only some of those.
   - **Slack system events** — `channel_topic`, `channel_join`, pins.

   Other bots are kept deliberately: an alerting bot's message is often the
   first real timeline event.

2. **Draft every section in one AI call.** Each heading is sent with the
   template's guidance beneath it as that section's instructions; the
   transcript is the only permitted source of facts.

3. **Copy the report and fill the copy.** See below.

4. **Nothing is written to the report.** See
   [The incident report is never written to](#the-incident-report-is-never-written-to).

##### A fresh copy every run

Each invocation copies the report to its own document, named with the run time
(`<title> - AI draft 2026-08-26 09:12`). Nothing is reused.

Editing one long-lived draft in place was the source of a whole class of bugs:
every run inherited the previous run's output, could only identify it by
heuristics, and needed a separate sweep for each way that guess went wrong —
duplicated sections, stacked banners, doubled label values, orphaned
sub-headings. When two of those sweeps proposed overlapping deletions, the
second deleted against indices the first had already shifted, shredding
neighbouring text into fragments. A pristine document cannot accumulate any of
it, so the whole class disappears rather than being patched case by case.

The trade is that drafts accumulate in the Drive folder instead of inside one
document, and each run has its own URL. The sweeps described below still run,
because a copy inherits whatever damage the *report itself* carries.

##### Editing the copy safely

Every edit is computed against one snapshot of the document and applied in a
single `batchUpdate`, under three rules:

- **Bottom-up.** Edits are ordered by descending position, so an edit higher in
  the document can never invalidate an index already used below it.
- **Disjoint.** Deletions proposed by different sweeps are merged into a
  non-overlapping set first. Two overlapping deletions cannot both be honoured:
  the first shifts every index after it, so the second removes text it was
  never meant to.
- **Styling first.** Label restyling changes no text lengths, so it leads the
  batch — valid against the same snapshot, and one round trip cheaper than a
  second pass.

Generated content is wrapped in named ranges (`incident_draft::<heading>`,
`::<label>` for a group under a sub-label). With a fresh copy each run they are
not needed for replacement; they remain as an invisible record of what the
machine wrote.

##### Pull-request links

Every pull request the report names must be openable from the report. The model
writes "PR 1898" in prose, having summarised away the link somebody posted, so
the references are hyperlinked back to a real URL. PR links are harvested from
the raw channel messages into a `number -> url` map, and every form the model
writes is linked over exactly its own text — `PR 1898`, `PR #1898`, `PRs 1898`,
`pull request 1898`, a bare `#1898`, and a full URL copied through (which links
to itself), including inside the timeline.

A number nobody posted a link for is resolved against the repository the channel
was discussing: when every PR link in the transcript belongs to one repository,
`PR 2001` becomes that repository's `/pull/2001`. Two things deliberately stay
unlinked, because a wrong link is worse than none: any reference at all when the
channel spanned more than one repository, and a bare `#2001` nobody linked —
that may be an issue number, and `/pull/<issue>` is a dead link.

Each PR is named **once**. The model is asked for the short `PR 1898` form and
told not to paste the URL beside it, since the document links that text itself —
writing both produced `Opened PR 1898, https://…/pull/1898, to add error
handling`, the same reference printed twice. Whatever it writes anyway is
collapsed: a URL naming the PR beside it is dropped along with its separator,
and a URL standing alone becomes `PR <number>`. Collapsing runs *after* link
resolution, so a URL only the model supplied is harvested into the link map
before it is removed from the text.

##### Pre-filled metadata is never overwritten

A label that already carries a value is left alone: `Name`, `Team`, `Date`,
`Slack channel` and `Status` are filled by `modules/incident` when the incident
is created, and those values are authoritative. Writing beside them is what
produced `Status: In Progress In Progress`. Only labels the template left blank
are filled — or ones this package wrote itself on an earlier run, which are
replaced through their named range rather than appended to.

##### Empty Impact labels

`End-users`, `CDS Staff`, `Other government department(s)` and `Other` are
dropped when nothing fills them, rather than left as bare stubs. Two guards
keep that from removing anything useful: a label carrying a value — written on
this run or left by an earlier one — is kept, and a section the transcript
could not answer is left entirely alone, template structure included, so a
human can fill it in by hand.

#### Metadata fields

Every field is attempted, and any the transcript does not establish is left
blank rather than guessed — a blank line in a retro is expected, a wrong name
or time is not.

The `Label: value` block above the first heading is addressed by label rather
than by section (only the preamble is scanned, so a colon in ordinary prose
further down is never mistaken for a field).

| Field | Filled from |
| --- | --- |
| `Start-of-impact time`, `Detection time`, `End-of-impact time` | The `YYYY-MM-DD HH:MM` timestamp of the message evidencing impact starting, first detection, and impact ending. Omitted when no message evidences them — never estimated. |
| `On-call` | The person the transcript names as on call or paged. Blank unless stated — the first person to speak is not assumed to be on call. Note this is also filled from the on-call rotation at creation. |
| `Facilitators` | Anyone the transcript identifies as coordinating the incident or its review. Blank unless stated. |
| `Name`, `Team`, `Date`, `Slack channel`, `Status` | Already filled by `modules/incident` at creation; left alone. The template styles several of these as headings, so they are recognised as labelled values rather than draftable sections — otherwise each value was written in again beneath itself. |

`_DRAFT_INSTRUCTIONS` is organised into labelled blocks (`## SOURCES`,
`## OUTPUT`, `## WRITING`, `## TIMELINE`, …) rather than one run-on paragraph,
and each behaviour is governed by exactly one rule. It was previously a single
4.5k-character string in which selectivity ("be highly selective", "not a log",
"merge closely related messages") was asserted five ways while the entry count
was asserted once, and a global "1-4 sentences per section" quietly capped the
list sections; the model resolved the contradiction toward brevity and returned
one or two timeline entries. Keep new rules in the block they belong to, and
check a rule does not contradict one already stated elsewhere.

Transcript lines are stamped `YYYY-MM-DD HH:MM ZZZ` in the configured zone
(`INCIDENT_DRAFT__TIMEZONE`, default `America/Toronto`), and the prompt tells the
model to copy that stamp verbatim into each timeline entry. An incident can span
days or a daylight-saving boundary, so a bare clock time is ambiguous; the zone
abbreviation follows DST because the setting names a zone rather than an offset.

The timeline answer is normalised before it is written, because "one event per
line" is an instruction models reshape: a JSON array (or an array of
`{"time": …, "text": …}` objects) is joined back into lines, and a timeline run
together into one paragraph is re-split at each timestamp. Without this a
whole incident arrived as a single entry, or — for array answers — was dropped
by the string-only parse and left the section looking unanswered.

These label lines are normalised to **ordinary body text** — the six fields
above plus the Impact section's `End-users`, `CDS Staff`,
`Other government department(s)` and `Other`. The template renders them as bold
headings, which makes them loom over the content beneath, so all three causes
are reset: the named style to `NORMAL_TEXT`, bold off, and the font to 11pt.
Matching is by label, so it works both in the preamble and inside a section.

The restyle leads the same `batchUpdate` as the content: it changes no text
lengths, so it is valid against the snapshot every other edit was computed
from.

#### The incident report is never written to

Every section — the timeline included — is drafted into the **copy**. The
report created when the incident opened is only ever read.

This is deliberate: its `Detailed Timeline` is maintained by `modules/incident`,
which appends 💾-reacted messages beneath the `DO NOT REMOVE…` line. Writing an
AI timeline there replaced entries responders had curated by hand. The two
mechanisms now stay out of each other's way — 💾 owns the report's timeline,
this command owns the draft's.

The `DO NOT REMOVE…` line is stripped from the **copy**, where nothing appends
to it and it is only noise. The report's own copy is untouched.

#### Formatting applied when filling a section

The copied template supplies the layout; these rules shape the content written
into each answered section.

**List sections** — any heading containing *action item*, *follow-up*,
*next step*, *to-do* or *timeline* — always render
as real Google Docs bullets, one per line, even when the model returns them
unmarked. The prompt additionally asks for action items phrased as concrete
tasks naming an owner where the transcript identifies one. Unanswered list
sections keep their template guidance as plain prose, so instructions are
never dressed up as completed items.

#### Template scaffolding

The copy keeps the template's structure, with four exceptions applied only to
sections that were actually drafted — an undrafted section keeps everything, so
the scaffolding is still there for a human to fill in.

| Removed | Why |
| --- | --- |
| Empty bullets under Trigger, Detection, Resolution/Recovery and the retrospective groupings | Once a section has content, an empty bullet reads as an item nobody filled in. |
| The `DO NOT REMOVE…` line | It exists so `modules/incident` can find the timeline in the **report**; a draft is a copy nothing appends to. The report's own copy is untouched. |
| Impact labels nothing filled | See [Empty Impact labels](#empty-impact-labels). |
| The trailing blank paragraph before the next heading | Content lands directly under the guidance rather than below a gap. |

Guidance is **added** where the report lacks it: `Detailed Timeline` and
`Trigger` always carry their template text, inserted in the same muted italic
if missing. The timeline's was replaced by the bot's banner in the report long
ago, so a copy inherits a section with none — it has to be written in rather
than merely preserved.

#### Action items table

Action items are written into the **Action Item** column of the template's
table, leaving Type, Owner, Issue #, Priority and Done for whoever triages the
retro. The header row and any row somebody has already filled are skipped, so a
re-run adds rather than overwrites. Items beyond the available empty rows stay
as bullets above the table — filling only what fits would silently drop the
rest.

#### Settings (all optional)

| Env var | Default | Meaning |
| --- | --- | --- |
| `INCIDENT_DRAFT__DEFAULT_HISTORY_LIMIT` | 500 | Messages fetched when `--limit` is absent |
| `INCIDENT_DRAFT__MAX_HISTORY_LIMIT` | 1000 | Hard cap on `--limit` |
| `INCIDENT_DRAFT__DEFAULT_SINCE_HOURS` | 24 | Fallback window when the channel creation time can't be read |
| `INCIDENT_DRAFT__MAX_OUTPUT_TOKENS` | 4000 | Completion budget for the draft. One response covers every section, so it needs far more than the vendor default, which truncates the JSON mid-object. |

Vendor settings live in `integrations.openai`. Two matter here:
`OPENAI_MAX_OUTPUT_TOKENS` (the fallback budget, overridden per call by the
row above) and `OPENAI_TEMPERATURE`, which is **omitted by default** — the
gateway's current model rejects the parameter with a 400. Set `0.0` to opt in
where the model supports it, for more reproducible drafts.

#### Truncated responses

If the model's JSON is cut off mid-object, the sections that arrived are kept
and written; the invoker is told the draft is partial and can re-run. Since
every run writes a fresh document, a fragment replaces nothing, so a partial
draft beats no draft.

Two exceptions:

- **Nothing usable, nothing written.** When no key/value pair can be recovered
  at all, the run fails with `DRAFT_UNPARSEABLE` rather than producing an empty
  document. The failure logs the response length and a preview, because an
  empty completion, prose instead of JSON, and a cutoff otherwise look
  identical.

`openai_summarize_truncated` records the budget and how much came back — the
number to look at before raising `INCIDENT_DRAFT__MAX_OUTPUT_TOKENS`, since a
length well short of the budget means the model has its own ceiling and raising
ours will not help.

#### Credentials

`OPENAI_API_KEY` (`integrations.openai`, which also supplies the model and
timeout) and the Google Workspace service account, with the `documents` and
`drive` scopes.

#### Required Slack scopes

`bookmarks:read`, `channels:history`/`groups:history`, `channels:read`/`groups:read`, `users:read`.

### `/sre incident summarize`

An AI-generated catch-up summary of the current
channel, for someone jumping into an incident.

#### What it does

Reads the incident conversation's transcript (recent channel history with
author display names resolved), builds a plain transcript, and asks the
`Summarizer` interface (OpenAI, see
`app/integrations/openai/`) to produce a concise, factual summary: what is
happening, current status, actions taken, and next steps. The summary is
returned **ephemerally** — only the person who ran
the command sees it, so it never adds noise to the incident channel.

#### Usage

```
/sre incident summarize                      # since channel creation, up to 500 messages (defaults)
/sre incident summarize --since 30m           # last 30 minutes
/sre incident summarize --since 2h           # last 2 hours
/sre incident summarize --since 90m --limit 100
/sre incident summarize --since 1d --limit 300
```

- `--since` — how far back to summarize: `30m`, `2h`, `1d` (a bare number is
  treated as hours). Omitted → the incident channel's creation time (falling
  back to `INCIDENT_SUMMARY__DEFAULT_SINCE_HOURS`, 24h, if the channel start
  cannot be determined).
- `--limit` — maximum messages to include. Omitted/invalid → default (500);
  capped at `INCIDENT_SUMMARY__MAX_HISTORY_LIMIT` (1000).

#### Settings

Feature-domain settings live in `settings.py` (`IncidentSummarySettings`); all
have safe defaults:

| Env var | Default | Meaning |
| --- | --- | --- |
| `INCIDENT_SUMMARY__DEFAULT_HISTORY_LIMIT` | `500` | Messages fetched when `--limit` is omitted |
| `INCIDENT_SUMMARY__MAX_HISTORY_LIMIT` | `1000` | Hard cap on `--limit` |
| `INCIDENT_SUMMARY__DEFAULT_SINCE_HOURS` | `24` | Fallback look-back window when `--since` is omitted and the channel start cannot be determined |

OpenAI credentials/model are **not** configured here — they belong to the
vendor client (`OPENAI_API_KEY`, `OPENAI_MODEL`, …) in
`app/integrations/openai/settings.py`.

#### Required Slack scopes

The bot must be able to read channel history and look up users:

- `channels:history` (public channels) / `groups:history` (private channels)
- `users:read`

The bot must be a member of the channel (or have `channels:history` via an
appropriate install). After changing scopes, reinstall the app and restart the
bot so the Web API client picks up the new token.
