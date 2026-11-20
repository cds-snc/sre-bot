# User announcement for a behaviour change

A PR that changes what end users see or do gets a short announcement the team posts in Slack when the PR ships, followed by screenshots. Changes that count: a command, modal, button, message, notice or permission that looks or works differently. Changes that don't: refactors, moves, dark layers with no consumer, logging and configuration.

The agent drafts the announcement and a screenshot list. Both go in the session's final message and in a "User announcement" section of the PR body.

## Announcement

Write for the people who use the bot, not for developers. Keep it to two or three short paragraphs:

1. **Greeting and topic**: one line naming the feature that changed, for example "Hi everyone, a few changes to incident roles are now live." Cover only this release, with no programme background or rebuild context.
2. **What changed**:
   - Start with what stays the same and how people reach it (the command or button and where to use it).
   - Then give "Before, … Now …" for each change users will notice, and say which new parts are optional.
   - Mention where something is now kept only if users would look for it there.
3. **Closing line**: "Screenshots below. If anything looks off, let us know!"

Prose rules:
- Plain words and full sentences.
- Commands in backticks, exactly as typed.
- Roles and features by the names users see in Slack.
- No task ids, PR numbers, package names or internal terms (record, adapter, cutover).
- A removed feature: say what replaces it, or that it is gone.
- A change people must act on: say it plainly in the second paragraph.

Template:

```text
Hi everyone, <one line: which feature changed in this release>.

<What stays the same and how to reach it: `/command` in <where>.> Before, <old behaviour>. Now <new behaviour> (<optional parts>). <Any second visible change, same pattern.>

Screenshots below. If anything looks off, let us know!
```

## Screenshot list

One numbered item per screenshot, three to five in all, each giving:

- **Shows**: the surface, for example the roles modal, the channel announcement or the stale-channel notice.
- **Steps**: the exact steps to reach it from a clean start, for example "In a test incident channel, run `/sre incident roles manage`, assign a Communications Lead, submit."
- **Capture**: what must be in frame and in what state, for example "the modal with all five role fields, two filled".
- **Where**: the environment. Use a test incident whose title starts with `TEST`, never a real incident, and no real people's names beyond the team's own.

Capture the French surface too when the change touches a bilingual message or a modal with a locale toggle. List the screenshots in the order they go under the announcement.
