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

4. **Write the timeline back into the real report.** The only write into the
   live incident document — see [Writes to the real incident report](#writes-to-the-real-incident-report).

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

### One generation per section

A drafted section should hold the template's structure plus exactly one
generation, so anything else already sitting there is swept before writing.
This matters because a copy inherits whatever the *report* carries. Four things
are spared: **guidance** (italic or grey — the five-whys guidance itself ends in
a question mark, so matching on that alone would delete it), **`Label:` lines**,
**sub-labels**, and content inside a named range the run already replaces.

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

## Writes to the real incident report

The timeline section is the only part of the incident report this package
writes to. The whole section is replaced — the ⚠️ banner, the paragraph
explaining the 💾 reaction mechanism, and any existing entries — leaving:

```
Detailed Timeline
  • 14:02 Ada: PagerDuty alert on checkout 500s
  • 14:09 Bob: rolled back deploy 41c9
  • 14:20 Ada: error rate back to baseline

Trigger                                                             ← untouched
```

- The section's end is the next heading *or* a paragraph reading `Trigger`,
  mirroring how `modules/incident` finds the same boundary — so it works even
  where `Trigger` is not styled as a real heading.
- If that boundary cannot be found, **nothing is written**. Guessing the end
  would delete every remaining section of the report.
- Every other section of the report is untouched.
- A report with no timeline heading, or an empty AI timeline, is not written to
  at all — the command still produces the draft document and says so.

The timeline is deliberately **selective**, not a transcript log: the prompt
asks for detection, impact confirmation, key findings, decisions, mitigation,
recovery and resolution, explicitly excluding greetings, acknowledgements,
dead-end speculation and status pings, and merging related messages into a
single entry (roughly 5–12 for a typical incident).

Note that this **replaces** the reaction-curated timeline entries. Responders
can re-pin messages afterwards; pinning keeps working because the sentinel is
preserved.

## Formatting applied when filling a section

The copied template supplies the layout; these rules shape the content written
into each answered section.

**List sections** — any heading containing *lessons learned*, *retrospective*,
*action item*, *follow-up*, *next step*, *to-do* or *timeline* — always render
as real Google Docs bullets, one per line, even when the model returns them
unmarked. The prompt additionally asks for action items phrased as concrete
tasks naming an owner where the transcript identifies one. Unanswered list
sections keep their template guidance as plain prose, so instructions are
never dressed up as completed items.

**Retrospective sub-headings.** A lessons-learned section is organised under
*What went wrong*, *What went well* and *Where we got lucky*. The template
already prints those labels, so each group's points are filed **under the
template's own label** and the generated label is dropped — emitting our own
would print each heading twice:

```
Lessons Learned                          ← HEADING_2 (template)
What went well                           ← template's label
  • Rollback took under two minutes      ← written here
What went wrong                          ← template's label
  • The canary step was skipped
Where we got lucky                       ← template's label
  • This was not indicated in the report ← placeholder when unsupported
```

A group with no matching template label keeps its own heading (as `HEADING_3`)
and goes at the end of the section.

A sub-heading is any line matching one of those labels, or any short
unbulleted line ending in a colon (≤ 6 words, so an ordinary sentence
containing a colon is not mistaken for one). Sub-headings win over forced
bullets. A grouping the transcript cannot support gets the single bulleted
point *"This was not indicated in the report"* — a bare label reads as an
oversight, whereas the placeholder shows the question was asked.

**Question-and-answer sections.** Any unbulleted line ending in `?` renders as
a bold question, and the line directly beneath it as its indented answer — the
shape five-whys and root-cause sections want:

```
Five whys and Root Cause(s)                        ← HEADING_2
1. Why did checkout return 500s?                   ← numbered, bold
    Because the deploy introduced a null deref.    ← indented answer
2. Why did the deploy introduce it?
    Because the canary step was skipped.
```

Questions are numbered in the five-whys section only; answers are not, and
questions elsewhere are left unnumbered.

The prompt asks five-whys chains to start from the user-visible failure and let
each question ask why the previous answer happened, producing **exactly five**
pairs. Where the transcript runs out first, the model is told to say so in that
answer rather than invent a cause.

The five-question limit is also enforced in code (`_cap_questions`): surplus
pairs are dropped before anything is written, since a prompt is a request and
not a guarantee. Only the extra pairs go — a trailing root-cause statement is
not part of the chain and survives — and a capped run logs
`incident_draft_whys_capped` with how many the model returned.

Sections the transcript can't support are left untouched, so they keep the
template's original guidance and a human still sees what that section needs.

## Template scaffolding

The copy keeps the template's structure, with four exceptions applied only to
sections that were actually drafted — an undrafted section keeps everything, so
the scaffolding is still there for a human to fill in.

| Removed | Why |
| --- | --- |
| Empty bullets under Trigger, Detection, Resolution/Recovery and the retrospective groupings | Once a section has content, an empty bullet reads as an item nobody filled in. |
| The `DO NOT REMOVE…` sentinel | It exists so `modules/incident` can find the timeline in the **report**; a draft is a copy nothing appends to. The report's own copy is untouched. |
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

- **The timeline is not written** on a truncated run. It is the only thing
  written into the *real* report, where it replaces curated entries — a chain
  that may itself have been cut short must not overwrite them
  (`incident_draft_timeline_skipped_after_truncation`).
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
