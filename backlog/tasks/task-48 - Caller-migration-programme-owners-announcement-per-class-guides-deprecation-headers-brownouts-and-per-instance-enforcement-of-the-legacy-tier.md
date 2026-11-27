---
id: TASK-48
title: >-
  Caller migration programme: owners, announcement, per-class guides,
  deprecation headers, brownouts and per-instance enforcement of the legacy tier
status: To Do
assignee: []
created_date: 2026-07-24 13:59
updated_date: '2026-11-25T20:52:00Z'
labels:
  - security
  - webhooks
milestone: m-4
dependencies:
  - TASK-47
  - TASK-37.6.1
  - TASK-194
references:
  - decisions/webhooks.md
  - decisions/security.md
  - https://github.com/cds-snc/sre-bot/issues/1343
  - decisions/plugin-architecture.md
priority: medium
ordinal: 72000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The caller-migration programme and the burn-down of the legacy secret-URL tier (decisions/security.md Webhooks; decisions/webhooks.md Caller migration; TASK-168 research packet section 5, row 48, Q8 phases 1 to 6, OQ27 and OQ28). Per instance, never big-bang. Ends the legacy no-dedupe exception.

End state per caller class: GitHub Actions workflows and Azure Sentinel or Logic Apps playbooks call the owning feature's API with their own identity (class 1, TASK-194), with HMAC as the fallback; AWS SNS topics keep their URL and protocol (owned topics: SignatureVersion 2, a subscription DLQ, a longer delivery policy; owned custom publishers move to the native protocol or the API); scripts and SaaS posting Slack-shaped JSON sign with the Standard Webhooks tier (TASK-47) and stop sending interactive and impersonation fields; unknown senders are found by the inventory.

Phases:
1. Inventory and owners: every instance has a required owner (backfilled in TASK-37.4.1) and a caller class from the TASK-46 fingerprints; unknown instances get a notice in their channel.
2. Announce: one announcement with the end state and a dated timeline (the sunset date is set at planning, after the inventory), a migration guide per caller class with copy-paste snippets (where the guides live is decided at planning), and a bot DM to each owner listing their instances.
3. Opt-in window (monitor): legacy-tier responses carry Deprecation (RFC 9745), Sunset (RFC 8594) and Link rel="deprecation" headers; the bot posts a rate-limited notice in the instance's channel; SRE gets a weekly compliance report by owner.
4. Brownouts: short, announced enforcement windows before the sunset date.
5. Enforce per instance (auth_tier legacy -> monitor -> enforce); exceptions are written, time-boxed and owned.
6. Remove the legacy tier.

Out of scope: the HMAC mechanism (TASK-47), machine principals (TASK-194), the management API (TASK-37.6.1).

Size: ~200 production LOC plus communications.
Production: prod, per instance.
Revert / blast radius: per instance, set the tier back to monitor.
Change notice: a series: the announcement with the sunset date, per-class guides, Deprecation and Sunset headers plus channel notices, each brownout, per-instance enforcement. User-facing: the channel notices the bot posts and the announcement (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every instance has an owner and a caller class from the inventory; unknown instances get a notice in their channel; a report enumerates the remaining legacy-tier population by owner so the burn-down is measurable (test + report)
- [ ] #2 The announcement with the sunset date and a migration guide per caller class are published, and each owner gets a DM listing their instances and detected class (review)
- [ ] #3 Legacy-tier responses carry Deprecation, Sunset and Link rel="deprecation" headers, with the Sunset date no earlier than the Deprecation date, and the bot posts a rate-limited notice in the instance's channel (test)
- [ ] #4 An instance in monitor logs would_reject for a missing or invalid signature and the request is still accepted (test)
- [ ] #5 An operator advances one instance's auth_tier legacy -> monitor -> enforce through WebhookAdmin without affecting any other instance (test)
- [ ] #6 GitHub Actions senders move to a feature API with an OIDC token (class 1) as the reference migration, with Standard Webhooks HMAC as the documented fallback (documented + test)
- [ ] #7 Brownout windows are announced and run before the sunset date; every exception is written, time-boxed and owned (review)
- [ ] #8 When the legacy population is zero, the legacy tier and the no-dedupe exception are removed and decisions/security.md marks the exception closed (review)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 18:41

---

Now operates on the packaged webhooks feature: the auth_mode field, service surface, and origin fingerprint all live in app/packages/webhooks after TASK-37. Monitor-then-enforce burn-down targets the packaged auth_mode=none legacy records; no legacy modules/slack CRUD involved. Depends on TASK-47 (HMAC tier in the package).

---

created: 2026-11-25T20:52:00Z

---

2026-11-25 re-cut (TASK-168, human-approved). Old title "Monitor-then-enforce migration of legacy unsigned webhook senders"; it becomes the caller-migration programme (TASK-168 packet Q8 phases 1-6). Old ACs, verbatim (short), and where each intent now lives:
- #1 "A legacy webhook can be placed in monitor mode where an invalid/absent signature is logged as would_reject but the request is still accepted" -> new AC #4.
- #2 "An operator flow advances a single webhook_id through none -> monitor -> hmac without affecting other webhook IDs" -> new AC #5 (auth_tier legacy -> monitor -> enforce through WebhookAdmin, TASK-37.6.1).
- #3 "The GitHub Actions sender is migrated to a signed (HMAC and/or CIDR-pinned) tier as the reference migration" -> new AC #6: GitHub Actions moves to class 1 (a feature API with an OIDC token, TASK-194); HMAC is the fallback.
- #4 "A report/query enumerates the remaining auth_mode=none webhook population so the exception burn-down is measurable" -> new AC #1.
Old dependency TASK-47 kept; TASK-37.6.1 (owners, auth_tier, notices) and TASK-194 (class 1 guides) added. Nothing is archived.

---
<!-- COMMENTS:END -->
