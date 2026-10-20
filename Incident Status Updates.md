# Incident Management - Status Updates

We're gradually improving SRE Bot's incident management features. The latest
change we're testing is `/sre incident status-update`: a way to prepare, review
and keep track of bilingual incident updates directly in Slack.

This is an early-stage feature, and we'll continue refining it as we learn from
your experience. Future enhancements will let product teams tailor update
formats and drafting guidance to their own communication standards. For now,
everyone starts with a shared format.

When you're responding to an incident, you can use it to explain what's affected,
how users are impacted and what your team is doing next. You can write the update
yourself or, when available, ask AI to help you draft it. Both English and French
versions stay together so you can review them before sharing.

**You stay in control: nothing is automatically posted to a channel or status
page. Approving an update prepares text for you to copy and share.**

Here's what you can expect when you try it.

## 1. Start in your incident channel

When you're ready to prepare an update, run this command in your incident's
Slack channel:

```text
/sre incident status-update
```

A **Status updates** window opens, visible only to you. After a brief loading
message, you will see:

- **New update** if there is no pending draft.
- The existing English and French draft and a **Review** button if someone has
  already started one. A note identifies how and when it was created.
- An **Approved updates** list, or a message saying none have been approved yet.

The window is private, but saved drafts and approved updates belong to the
incident: other responders can open them through the same command.

*Screenshot: the Status updates window, showing New update or a pending draft.*

## 2. Prepare your update

Select **New update** to start writing, or **Review** to pick up the pending
draft. You don't need to use AI to get started. If you've already approved an
update for this incident, its content is used as a starting point so you don't
have to write everything again.

The **Review update** form includes:

- **Stage:** Investigating, Identified, Monitoring or Resolved.
- English and French fields for **Affected service**, **Impact**,
  **Current action** and **Workaround**.
- **Save draft** to keep your work without approving it. Incomplete drafts can
  be saved; look for the **Draft saved.** confirmation.
- **Approve** when both language versions are ready.

Fill in every text field in both languages before approving, including an
explicit statement when there is no workaround. Approval highlights blank
fields. The stage cannot move backwards from the latest approved update.

Use **Save draft** before leaving if you want to keep your edits; do not rely
on **Cancel** to save them.

*Screenshot: the review form, including both language sections and the buttons.*

## 3. Ask AI for help if you'd like

If AI is configured, the form also offers **Instructions for the AI (optional)**
and **Draft with AI**. You can still complete the whole update manually.

Leave the instructions empty to draft from the incident conversation, or give
guidance such as "do not name the vendor". AI uses the incident conversation and
your current form content to help prepare the draft.

After selecting **Draft with AI**, you may see
**Drafting the status update with AI. This usually takes up to a minute...**
The form then returns with the new draft for you to check and edit. AI drafting
does not approve or publish it.

If there are no new messages from people since the last approved update and you
have not supplied instructions, the content is carried forward with
"No new information since the last update." as the current action, without
calling AI.

For a security incident, or when its security flag cannot be checked, a warning
and confirmation checkbox appear before content can be sent to the AI model.
Only confirm if sharing that content is appropriate. You can instead continue
writing manually. If AI drafting fails, the form keeps your text and shows a
notice.

*Screenshot: AI instructions and Draft with AI; optionally, the security warning.*

## 4. Review it, then share it yourself

Once you're happy with both language versions, select **Approve**. After
**Saving the approval...**, you will see:

> Approved. Proofread, then copy into your product's channel. Nothing was posted.

Separate English and French text blocks are ready to copy. They include the
stage, affected service, impact, current action and workaround. Non-resolved
updates also include a next-update time in Eastern time; resolved updates omit
that line.

Proofread both versions, then copy and post them to the appropriate destination.
**Approval is not publication.**

*Screenshot: the approved, copy-ready English and French text.*

## 5. Let other responders know it's been shared

Run the command again and select **Open** beside the update in **Approved
updates**. Select **Mark as published** after you have shared it.

This helps other responders see which updates have been shared. It records who
marked the update published and when; it does not send any messages.
You can reverse the marker with **Mark as not published**. Use **Back** to
return to the overview. The list shows up to the latest 50 approved updates.

*Screenshot: a reopened update with its publication marker.*

## If something looks different

- **Not an incident channel:** run the command in the channel associated with
  the incident.
- **No channel history:** a first draft needs at least one message from a person
  in the incident channel.
- **No AI controls:** AI is not configured; use the manual fields.
- **Draft changed or approved elsewhere:** another responder updated it.
  Reopen the command to work from the latest version.
- **Loading or saving error:** read the notice and retry. Do not assume your
  changes were saved without a confirmation.

## Tell us how it goes

Your feedback is encouraged and appreciated, and will help shape these
improvements. Let the SRE team know what helps, what feels confusing, or what
doesn't work as expected. We'd also like to hear about your product's update
formats and communication standards so we can make this a better fit for your
team.
