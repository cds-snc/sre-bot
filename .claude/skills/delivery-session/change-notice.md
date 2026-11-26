# Change notice for developers

A PR that changes something a developer can see or must act on gets a change notice. The team shares it with the dev teams when the PR ships. It covers people outside the bot's users: teams that call the bot (webhook senders, API callers, workflows), teams that operate something it talks to, and contributors to this repository.

Changes that count:
- a URL, request or response shape, status code or header
- authentication or signing
- a rate limit
- a payload field accepted, ignored or rejected
- a new or removed endpoint
- a deprecation, a sunset date or a brownout
- a contributor-facing workflow, such as a new content root, a schema check or a generator

Changes that don't count: dark layers with no consumer, internal refactors, and logging that nobody outside reads.

A change that end users also see in Slack gets the user announcement too ([user-announcement.md](user-announcement.md)). The two are written separately, because their readers differ.

## When it goes out

- **No action needed:** with the PR, on the day it ships.
- **Action needed:** a first notice **before the merge**, with the date and at least two weeks' lead time unless the human sets another. Then a second notice when the change takes effect. Name the callers already known to be affected (from logs or fingerprints), so their owners can be told directly.
- **A deprecation series** (announcement, reminders, brownouts, enforcement): one notice per step, each repeating the dates.

## Notice

Write for a developer on another team who has never read this repository.

Prose rules:
- Plain words and full sentences.
- Exact header names, status codes, field names and commands in backticks.
- No task ids, PR numbers, package names, slice names or internal terms (record, adapter, cutover, lane).
- Say what stays the same before what changes.
- When action is needed, say so in the second line, with the date.
- Link a guide for anything that takes more than two steps.
- Never include a secret, a webhook URL or a real person's data.

Template:

```text
<Area> change: <one line, what changed>
When: <date it takes effect> · Action needed: <none | yes, by <date>>

Who is affected: <which callers, and how a team can tell it is one of them, e.g. "webhooks that post Slack-formatted JSON", "SNS topics subscribed to /hook">.
What stays the same: <URLs, behaviour or fields that do not change>.
What changes: Before, <old behaviour>. Now, <new behaviour>.
What you need to do: <steps, or "nothing">. Guide: <link>.
How to check: <what the caller sees, e.g. a response header, a channel notice, the delivery log>.
Questions or an exception: <contact or channel>.
```

## Where it goes

- The PR body's "Change notice" section, ready to paste.
- The session's final message, after the commands and before the next prompt (and after the user announcement, if there is one).
- For an action-needed change, the advance notice also goes in the session's final message for the session that plans the PR, so it can be sent before the merge.
