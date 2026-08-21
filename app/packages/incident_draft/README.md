# incident_draft

Adds `/sre incident draft`: from inside an incident channel, reads the
incident Google Doc created at channel creation, treats the guidance written
under each heading as that section's drafting instructions, answers each one
from the incident channel's messages, and writes the filled-in result into a
**new** document. The original incident document is only ever read.

## Usage

```
/sre incident draft                # draft from the whole incident history
/sre incident draft --limit 200    # draft from at most 200 messages
```

History always starts at the channel's creation, so the draft covers the whole
incident; `--limit` caps how many messages are read (capped at
`MAX_HISTORY_LIMIT`).

## How it works

1. The Slack adapter finds the incident document via the channel's
   "Incident report" bookmark (set when the incident is created), and fetches
   the channel transcript with display names resolved, then filters out noise:

   - **This bot's own messages** (topic changes, hangout links, "an incident
     report has been created at…") — scaffolding, not incident facts. Matched
     on *any* of `user_id`, `bot_id`, or normalised display name from
     `auth_test`, because a message may carry only some of those.
   - **Slack system events** — `channel_topic`, `channel_join`, pins and
     similar, whoever triggered them.

   Other bots are kept on purpose: an alerting bot's message is often the
   first real timeline event. The prompt additionally forbids describing
   automated bot activity as team actions, and forbids creating action items
   for work a bot performed.
2. The Google adapter walks the document body: each `HEADING_*` paragraph is a
   section, and the text under it is that section's **instructions** (the
   template's guidance for what belongs there).
3. The service sends every heading with its instructions, plus the transcript,
   to the `Summarizer` port (`integrations.openai`) asking for a strict JSON
   mapping of heading → section content. The instructions say *what to write*;
   the transcript is the *only* source of facts.
4. The draft document — `"<incident doc title> - AI draft"` — is a **Drive
   copy of the incident report**, so it keeps the template's exact format:
   every heading, the metadata block, the blameless statement, the italic
   guidance under each heading, and the Action Items table.
5. Drafted content is **appended below each section's guidance**, at the end of
   that section. Nothing in the template is ever deleted — the guidance stays
   in the document, serving as both the model's instructions and the reader's.
   Where the template already prints sub-labels (`What went well`,
   `What went wrong`, `Where we got lucky`), each matching group is placed
   directly under **the template's own label** and the generated label is
   dropped — otherwise the heading appears twice. A group with no matching
   template label keeps its own heading and goes at the end of the section.
6. The report's **metadata block** (the `Label: value` lines above the first
   heading) is filled in the draft too — see below.

### Replacing a previous run

Generated content is wrapped in a Google Docs **named range** —
`incident_draft::<heading>` for a section, `incident_draft::<heading>::<label>`
for a group placed under a template sub-label. Named ranges are invisible, and Google keeps
their offsets in sync as the document changes, so a re-run can find exactly
what the last run wrote and replace just that — leaving every template heading
and every line of guidance untouched. Matching on the text itself would be
guesswork; this is a record.

Sections are written **bottom-up** so an edit higher in the document can never
invalidate indices already used below it. Metadata fields and the banner follow,
for the same reason.

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
| `Author(s)` | Derived directly from who spoke in the channel, in order of first appearance. No inference involved. |
| `On-call` | The person the transcript names as on call or paged. Blank unless stated — the first person to speak is not assumed to be on call. Note this is also filled from the on-call rotation at creation. |
| `Facilitators` | Anyone the transcript identifies as coordinating the incident or its review. Blank unless stated. |
| `Name`, `Team`, `Date`, `Slack channel`, `Status` | Already filled by `modules/incident` at creation; left alone. |

Because the date matters for these fields, transcript timestamps carry the full
`YYYY-MM-DD HH:MM`, while timeline entries still render just the clock time.

These label lines are normalised to **ordinary body text** — the six fields
above plus the Impact section's `End-users`, `CDS Staff`,
`Other government department(s)` and `Other`. The template renders them as bold
headings, which makes them loom over the content beneath, so all three causes
are reset: the named style to `NORMAL_TEXT`, bold off, and the font to 11pt.
Matching is by label, so it works both in the preamble and inside a section.

The restyle runs as a second `batchUpdate` against a freshly fetched document:
styling is index-based, and re-reading avoids reasoning about how the content
edits shifted everything. Being purely cosmetic, a failure there is logged and
swallowed rather than failing the draft.

## Writes to the real incident report

The timeline section is the only part of the incident report this package
writes to. The whole section is replaced — the ⚠️ banner, the paragraph
explaining the 💾 reaction mechanism, and any existing entries — leaving:

```
Detailed Timeline
DO NOT REMOVE this line as the SRE bot needs it as a placeholder.   ← muted italic
  • 14:02 Ada: PagerDuty alert on checkout 500s
  • 14:09 Bob: rolled back deploy 41c9
  • 14:20 Ada: error rate back to baseline

Trigger                                                             ← untouched
```

- The sentinel is deleted with the rest and **re-inserted verbatim**, styled
  muted italic since it is machinery rather than content. `modules/incident`
  locates the timeline by that exact line to append 💾-reacted messages;
  losing it would make every future reaction fail silently. A test asserts the
  re-inserted text matches that module's `START_HEADING` constant.
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

The draft copy is located by title within the incident's folder, and never by
the source document's id — so a lookup mishap cannot point the fill at the
report itself.

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
*What went wrong*, *What went well* and *Where we got lucky*, each rendered as
a `HEADING_3` with its points bulleted beneath:

```
Lessons Learned                          ← HEADING_2
What went wrong                          ← HEADING_3
  • The canary step was skipped
  • Alerting missed the 500 spike
What went well                           ← HEADING_3
  • Rollback took under two minutes
Where we got lucky                       ← HEADING_3
  • Traffic was low at the time
```

A sub-heading is any line matching one of those labels, or any short
unbulleted line ending in a colon (≤ 6 words, so an ordinary sentence
containing a colon is not mistaken for one). Sub-headings win over forced
bullets, and a grouping the transcript cannot support is omitted entirely
rather than left empty.

**Question-and-answer sections.** Any unbulleted line ending in `?` renders as
a bold question, and the line directly beneath it as its indented answer — the
shape five-whys and root-cause sections want:

```
Five Whys                                        ← HEADING_2
Why did checkout return 500s?                    ← bold
    Because the deploy introduced a null deref.  ← indented answer
Why did the deploy introduce it?
    Because the canary step was skipped.
```

The prompt asks five-whys chains to start from the user-visible failure and
let each question ask why the previous answer happened — stopping as soon as
the transcript stops supporting the next step, rather than inventing a deeper
cause to reach five.

Sections the transcript can't support keep the template's original
instructions in the draft, so a human still sees what that section needs, and
the ephemeral reply lists them explicitly.

## Settings (all optional)

| Env var | Default | Meaning |
| --- | --- | --- |
| `INCIDENT_DRAFT__DEFAULT_HISTORY_LIMIT` | 500 | Messages fetched when `--limit` is absent |
| `INCIDENT_DRAFT__MAX_HISTORY_LIMIT` | 1000 | Hard cap on `--limit` |
| `INCIDENT_DRAFT__DEFAULT_SINCE_HOURS` | 24 | Fallback window when the channel creation time can't be read |
| `INCIDENT_DRAFT__MAX_OUTPUT_TOKENS` | 8000 | Completion budget for the draft. Drafting emits JSON covering every section, so it needs far more than the vendor default of 800 (which truncates the JSON mid-object). Raise it for very long reports. |

## Truncated responses are discarded, never written

The draft document is rewritten in place on every run, so a degraded run could
otherwise replace good content with a fragment. If the model's JSON is cut off
mid-object, the run is **abandoned**: neither the draft document nor the
report's timeline is touched, and the invoker is told to retry. The sections
missing from a truncated response are an artefact of the cutoff, not the
model's judgement, so writing them as "unanswered" would silently delete work.

Vendor settings come from `integrations.openai` (`OPENAI_API_KEY`, model,
timeout) and the Google Workspace integration (service-account credentials
with `documents` and `drive` scopes).

## Required Slack scopes

`bookmarks:read`, `channels:history`/`groups:history`, `channels:read`/`groups:read`, `users:read`.

## Architecture

Per `decisions/feature-packages.md` and `decisions/transport-slack.md`:

- `domain.py` — frozen values: `TranscriptMessage`, `DocumentSection`
  (heading + instructions), `SectionDraft`, `DraftedDocument`.
- `service.py` — platform-agnostic orchestrator; depends on the
  `IncidentDocumentPort` Protocol and the `Summarizer` port; no Slack, HTTP,
  or Google SDK imports.
- `adapters/google_docs.py` — the only file importing `integrations`
  (Docs read + Drive create + Docs populate).
- `providers.py` — feature-local DI wiring for the document port.
- `platforms/slack.py` — five-step handler; ephemeral responses; EN/FR
  locales in `locales/`.
