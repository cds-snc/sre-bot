# incident_draft

Adds `/sre incident draft`: from inside an incident channel, reads the
incident Google Doc created at channel creation, treats the guidance written
under each heading as that section's drafting instructions, answers each one
from the incident channel's messages, and writes the filled-in result into a
**new** document. The original report is read, not rewritten.

## Usage

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

## Sections left for humans

**Five whys / root causes** and **Lessons Learned** (*What went well*, *What
went wrong*, *Where we got lucky*) are never drafted. They are judgement calls
the team makes together in the retro, not conclusions to be inferred from a
transcript, so those sections are filtered out before the request is built —
the model never sees them, and nothing is written into them. Their template
guidance is left exactly as it is, ready for a human.

## How it works

1. **Locate and read the channel.** The incident document is found via the
   channel's "Incident report" bookmark. The transcript is fetched from channel
   creation, display names resolved, timestamps attached, and noise removed:

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

### A fresh copy every run

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

### Editing the copy safely

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

### Pull-request links

The model writes "PR 1898" in prose, having summarised away the link somebody
posted. Those references are hyperlinked back to the real URL: PR links are
harvested from the raw channel messages into a `number -> url` map, and every
`PR 1898` / `PR #1898` reference written into the document — including in the
report's timeline — is linked over exactly that text.

A number nobody posted a link for is left as plain text. A bare PR number does
not identify a repository, so the alternative would be guessing one, and a link
to the wrong repository is worse than no link at all.

### Pre-filled metadata is never overwritten

A label that already carries a value is left alone: `Name`, `Team`, `Date`,
`Slack channel` and `Status` are filled by `modules/incident` when the incident
is created, and those values are authoritative. Writing beside them is what
produced `Status: In Progress In Progress`. Only labels the template left blank
are filled — or ones this package wrote itself on an earlier run, which are
replaced through their named range rather than appended to.

### Empty Impact labels

`End-users`, `CDS Staff`, `Other government department(s)` and `Other` are
dropped when nothing fills them, rather than left as bare stubs. Two guards
keep that from removing anything useful: a label carrying a value — written on
this run or left by an earlier one — is kept, and a section the transcript
could not answer is left entirely alone, template structure included, so a
human can fill it in by hand.

## Metadata fields

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

Because the date matters for these fields, transcript timestamps carry the full
`YYYY-MM-DD HH:MM`, while timeline entries still render just the clock time.

These label lines are normalised to **ordinary body text** — the six fields
above plus the Impact section's `End-users`, `CDS Staff`,
`Other government department(s)` and `Other`. The template renders them as bold
headings, which makes them loom over the content beneath, so all three causes
are reset: the named style to `NORMAL_TEXT`, bold off, and the font to 11pt.
Matching is by label, so it works both in the preamble and inside a section.

The restyle leads the same `batchUpdate` as the content: it changes no text
lengths, so it is valid against the snapshot every other edit was computed
from.

## The incident report is never written to

Every section — the timeline included — is drafted into the **copy**. The
report created when the incident opened is only ever read.

This is deliberate: its `Detailed Timeline` is maintained by `modules/incident`,
which appends 💾-reacted messages beneath the `DO NOT REMOVE…` line. Writing an
AI timeline there replaced entries responders had curated by hand. The two
mechanisms now stay out of each other's way — 💾 owns the report's timeline,
this command owns the draft's.

The `DO NOT REMOVE…` line is stripped from the **copy**, where nothing appends
to it and it is only noise. The report's own copy is untouched.

## Formatting applied when filling a section

The copied template supplies the layout; these rules shape the content written
into each answered section.

**List sections** — any heading containing *action item*, *follow-up*,
*next step*, *to-do* or *timeline* — always render
as real Google Docs bullets, one per line, even when the model returns them
unmarked. The prompt additionally asks for action items phrased as concrete
tasks naming an owner where the transcript identifies one. Unanswered list
sections keep their template guidance as plain prose, so instructions are
never dressed up as completed items.

## Template scaffolding

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

## Action items table

Action items are written into the **Action Item** column of the template's
table, leaving Type, Owner, Issue #, Priority and Done for whoever triages the
retro. The header row and any row somebody has already filled are skipped, so a
re-run adds rather than overwrites. Items beyond the available empty rows stay
as bullets above the table — filling only what fits would silently drop the
rest.

## Settings (all optional)

| Env var | Default | Meaning |
| --- | --- | --- |
| `INCIDENT_DRAFT__DEFAULT_HISTORY_LIMIT` | 500 | Messages fetched when `--limit` is absent |
| `INCIDENT_DRAFT__MAX_HISTORY_LIMIT` | 1000 | Hard cap on `--limit` |
| `INCIDENT_DRAFT__DEFAULT_SINCE_HOURS` | 24 | Fallback window when the channel creation time can't be read |
| `INCIDENT_DRAFT__MAX_OUTPUT_TOKENS` | 8000 | Completion budget for the draft. One response covers every section, so it needs far more than the vendor default, which truncates the JSON mid-object. |

Vendor settings live in `integrations.openai`. Two matter here:
`OPENAI_MAX_OUTPUT_TOKENS` (the fallback budget, overridden per call by the
row above) and `OPENAI_TEMPERATURE`, which is **omitted by default** — the
gateway's current model rejects the parameter with a 400. Set `0.0` to opt in
where the model supports it, for more reproducible drafts.

## Truncated responses

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

## Credentials

`OPENAI_API_KEY` (`integrations.openai`, which also supplies the model and
timeout) and the Google Workspace service account, with the `documents` and
`drive` scopes.

## Required Slack scopes

`bookmarks:read`, `channels:history`/`groups:history`, `channels:read`/`groups:read`, `users:read`.

## Architecture

Per `decisions/feature-packages.md` and `decisions/transport-slack.md`:

- `domain.py` — frozen values: `TranscriptMessage`, `DocumentSection`
  (heading + instructions), `SectionDraft`, `DocumentField`,
  `DraftWriteResult`, `DraftedDocument`.
- `service.py` — platform-agnostic orchestrator; depends on the
  `IncidentDocumentPort` Protocol and the `Summarizer` port; no Slack, HTTP,
  or Google SDK imports.
- `adapters/google_docs.py` — the only file touching **Google**
  (Docs read + Drive copy + Docs populate). `service.py` imports the
  `Summarizer` port and `platforms/slack.py` the transport models, both by
  design.
- `providers.py` — feature-local DI wiring for the document port.
- `platforms/slack.py` — five-step handler; ephemeral responses; EN/FR
  locales in `locales/`.
