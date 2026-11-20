---
id: TASK-190
title: Linear-time email and IP matching in the Slack webhook helpers
status: Done
assignee: []
created_date: '2026-11-20T15:23:00Z'
updated_date: '2026-11-20T22:07:00Z'
labels:
  - security
  - webhooks
milestone: m-5
dependencies: []
references:
  - integrations/slack/users.py
  - decisions/security.md
priority: high
ordinal: 531000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Finding F-A from TASK-36.2 (2026-11-20). integrations/slack/users.py:207 replace_users_emails_with_mention matches emails with r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" via re.findall; the unanchored repeated local part backtracks quadratically on text without an '@' (measured: 8 KB 0.07 s, 16 KB 0.31 s, 32 KB 1.21 s; ~80 s CPU extrapolated for a body under the 262144-byte cap). It runs on the unauthenticated POST /hook/{webhook_id} route (modules/webhooks/slack.py:34 and recursively over blocks via users.py:238), synchronously, so one sender can hold a worker. Fix the matcher so it is linear in input length while matching the same addresses (for example bound the scan by locating '@' first and expanding the local and domain parts, or a pattern without nested ambiguity), keep the mention replacement behaviour, and keep the TASK-36.2 legacy_surface webhook pins unchanged. Single side PR from main; the webhooks rebuild (TASK-168, TASK-37.x) replaces this path later.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Matching an adversarial input of 262144 bytes without an address completes within a bounded time in a unit test (well under one second), and the time grows linearly with input length
- [x] #2 Every address the current pattern matches in tests/integrations/slack/test_users.py is still matched and replaced with the same mention; non-addresses stay untouched
- [x] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; mypy then pytest once each, sequentially, at the end
- [x] #4 IP_ADDRESS_PATTERN in modules/webhooks/slack.py matches in linear time (262144-byte adversarial IPv6-like input well under one second in a unit test) and links exactly the addresses it links today
- [x] #5 The TASK-36.2 webhook pins (tests/integration/legacy_surface -k webhook) pass unchanged
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-20 against main 4bc8ee98 and the TASK-36.2 pins on task-36.2-webhook-route-pin (eed1c3af, PR #1882 open, not merged).

Context. POST /hook/{webhook_id} (api/v1/routes/webhooks.py:129-130) runs map_emails_to_slack_users then hydrate_ip_addresses over text and every string in blocks, synchronously, on an unauthenticated route with a 262144-byte body cap (server_settings.webhook_max_body_bytes). Two patterns backtrack super-linearly there:
- F-A, email: integrations/slack/users.py:207 r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}". Every start position inside a run re-scans the run. Measured on main: 2 KB 0.005 s, 4 KB 0.019-0.059 s (x4 per doubling).
- F-H (new, found while planning), IP: modules/webhooks/slack.py:17 IP_ADDRESS_PATTERN, IPv6 branch (?:[hex]{1,4}:){2,}[hex:.]* followed by (?![\w/:-]). The groups and the tail overlap, so a failing lookahead retries every split. Measured: "1:"*n+"g" 0.5 KB 0.0016 s, 1 KB 0.0063 s, 2 KB 0.034 s (x4-5 per doubling); extrapolated several minutes of CPU at the cap. Worse than F-A, same route, same fix class: folded in (OQ1).

Approach (Python 3.11+ possessive quantifiers and atomic groups, docs.python.org/3/library/re.html; OWASP ReDoS: remove ambiguity between adjacent repeats rather than add timeouts):
1. integrations/slack/users.py: module-level EMAIL_PATTERN = re.compile(r"(?<![a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]++@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"); replace_users_emails_with_mention uses EMAIL_PATTERN.findall. A match may only start where a local-part run starts, and the local part never gives back, so each run is scanned once and each '@' once: linear. Only difference from today (400k-string differential fuzz): a second "address" glued onto the end of a previous one ("a@b.com_x@c.org" yields only a@b.com, today also "_x@c.org"); such tokens are not addresses and would fail lookup (OQ2). Measured: 262144 bytes, six adversarial shapes, 0.004-0.007 s each.
2. modules/webhooks/slack.py IP_ADDRESS_PATTERN IPv6 branch becomes (?:[hex]{1,4}:){2,}+(?:[hex:.]*+(?![\w/:-])|[hex:.]*(?=\.)). Proof sketch: inside a [hex:.] run the outer lookahead can only pass before a '.' or at the run's end, and giving back groups never adds such a position, so "longest run, else back off to the last '.'" is exactly today's result. Differential fuzz over 400k random strings: 0 differences. Measured at 262144 bytes: 0.001-0.011 s. IPv4 branch and the lookbehind unchanged.
3. Leave the mention replacement, lookups, logging and the dict walkers unchanged. No settings, no new module, no import or seam change.
4. decisions/security.md Webhooks clause "controls bind regardless of auth state": add that body text processing is linear in body size (no backtracking-prone patterns on untrusted text), with the Python re and OWASP ReDoS sources; Checks line gets the adversarial-input test. Changes entry dated at implementation (OQ3).

Tests first (TDD, all fail today on time or are new pins):
- tests/integrations/slack/test_users.py (existing file, extend): replace_users_emails_with_mention over 262144 bytes of each adversarial shape (no '@', '@' with no dot, dotted domain without TLD, "a@" repeated, '.' run) finishes under 0.5 s with a mocked client and makes no lookup; parametrized address table (dots, plus, percent, hyphenated and multi-label domains, two addresses, address inside <mailto:...|...>) asserts the same lookups and mentions as today; non-addresses ("x@y.c", "@x.com", "a@b") make no lookup. Linearity (AC #1): the 262144-byte run is under 0.5 s where today's pattern takes over a minute; no ratio assertion (flaky on shared runners), the absolute bound at the cap is the guard.
- tests/modules/webhooks/test_webhooks_slack.py (existing, extend): link_ip_addresses_to_geolocate over 262144 bytes of "1:"*n+"g", "ab:"*n+"z" and "1:1:"+"1."*n+"g" under 0.5 s and unchanged; IPv6 followed by "./" still links (the back-off branch, "fe80::1./x"); existing IPv4/IPv6/link/invalid tests unchanged.
- Route level: the 36.2 pins (tests/integration/legacy_surface -k webhook) run unchanged. If #1882 has merged when implementation starts, the just-under-cap test pads "text" instead of "username" in this PR (route-level regression guard, docstring updated); if not, that one-line change is handed to TASK-37.4 by comment (OQ4).

AC to step to test: #1 -> step 1, adversarial users tests; #2 -> step 1, address table and existing replace tests; #3 -> step 3, legacy_surface pins; #4 -> gates; #5 (added) -> step 2, IP tests.

Size: 2 production files, ~6 production LOC changed; ~120 test LOC; 1 ADR sentence. One subsystem (legacy webhook helpers). Size gate: pass.

Blast radius and rollback: changes what text the bot rewrites in forwarded webhook posts only. Wrong outcome is a missed mention or a missed geolocate link, not a failed post. One git revert restores today. Merge deploys; no terraform, IAM, SSM or env-name change, so no deploy-checks.

Assumptions to verify at implementation: runner speed keeps 262144-byte runs well under 0.5 s (measured 0.011 s worst here); test_users.py has no existing timing helper (use time.perf_counter, no new dependency).

Out of scope, handed off by comment: one users_lookupByEmail call per match is unbounded (a 262144-byte body of distinct addresses is ~30k Slack calls) -> TASK-168 (webhooks rebuild; cap or batch lookups) and TASK-49 (rate limit per sender) as F-I.

Gates: ruff, targeted tests during TDD; check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams; then full mypy, then full pytest, once each, sequentially.

CodeQL evidence (human, 2026-11-20): CodeQL default setup scans Actions and Python, last scan of main within the hour; no py/polynomial-redos or py/redos alert, open or closed, on any branch. The only open CodeQL alerts are 'Workflow does not contain permissions' (#16, #18, #19, #22, unrelated). So CodeQL doesn't follow the webhook payload from the request through the Pydantic model and the dict walk into these regexes; the cap-sized adversarial tests are the only guard.

Decisions (human-approved 2026-11-20, after a program-scope assessment against the ADRs, doc-11, doc-15 and doc-16):
- OQ1 fold F-H (IP_ADDRESS_PATTERN) into this task: yes; title renamed.
- OQ2 an address glued onto the end of a previous one is no longer matched: accepted. No ADR sets matching rules; migration.md makes the 36.2 pins the contract and they don't pin this; precedent 36.2 OQ5 (unpinned legacy quirks go to the rebuild). TASK-168 comment: the rebuilt matcher is linear, token-bounded, and bounds Slack lookups (F-I).
- OQ3 ADR gap: security.md binds a size cap, revocation and a rate limit, but nothing bounds CPU per byte, and a backtracking re match holds the GIL (measured: a second thread got 1 tick in 0.65 s), so one request stalls the whole process. security.md "Request limits" gains: handling an untrusted body is linear in its size; patterns over untrusted text have no overlapping repeats (possessive or atomic where needed); each has a cap-sized adversarial test; CodeQL py/redos and py/polynomial-redos are a backstop only (they don't trace a payload through model parsing). Checks line and a 2026-11-20 Changes entry. Sources: CWE-1333, OWASP ASVS 5.0 (L3 regex requirement), CodeQL py/polynomial-redos and py/redos query help, Python re possessive quantifiers (3.11+). TASK-168 comment carries the rule into the rewritten webhooks.md.
- OQ4 AC #3 reworded to "pins pass unchanged" (old #3 removed, new #5; old #4/#5 are now #3/#4). The just-under-cap pin padding a scanned field moves to TASK-37.4 (owns the harness; cutover deletes the modules/webhooks unit tests, so only a route-level guard survives), with a TASK-168 comment.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed
- integrations/slack/users.py: module-level EMAIL_ADDRESS_PATTERN, (?<![a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]++@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}; replace_users_emails_with_mention uses it. A match starts only where a run of local-part characters starts, and the local part never gives back, so matching is linear. The only change in what matches (OQ2, accepted): an address glued onto the end of the previous one.
- modules/webhooks/slack.py: in the IPv6 branch of IP_ADDRESS_PATTERN the groups are possessive and the tail is either the whole run or the run up to its last dot. Same matches as before (0 differences over 400k fuzzed strings), linear time.
- decisions/security.md: Request limits amended (linear body handling, no overlapping repeats on untrusted text, a cap-sized adversarial test per pattern, CodeQL only a backstop), a Checks line and a 2026-11-20 Changes entry.
- Tests: tests/integrations/slack/test_users.py gains the cap-sized adversarial shapes (5), an address table (7) and non-addresses (4). tests/modules/webhooks/test_webhooks_slack.py gains the cap-sized IPv6-like shapes (4) and dot-after-IPv6 cases (3).

Evidence
- Red: the 9 cap-sized tests ran past a 100 s timeout on the old patterns; the 7 behaviour pins (address table, non-addresses, dot-after-IPv6) passed on the old code, so they pin today's results.
- Linear growth (best of 5; email no-'@', email dotted domain, IP hex groups, IP two-digit groups): 32 KiB 0.58/1.19/1.51/1.16 ms; 64 KiB 0.94/1.65/2.63/2.37 ms; 128 KiB 1.90/3.29/5.66/5.84 ms; 256 KiB 3.70/6.55/10.50/8.90 ms.
- TASK-36.2 pins: run from a scratch copy of this tree with the task-36.2-webhook-route-pin tests (eed1c3af): pytest tests/integration/legacy_surface -k webhook, 80 passed, 169 deselected.
- Gates: ruff check clean; check-import-contracts 15 kept, 0 broken; settings-key-ownership OK; package-shape OK (3 baselined); test-seams no net-new (47 and 12 baselined); mypy 40 errors in 13 files, all pre-existing, none in touched files; pytest tests --ignore=tests/smoke 8004 passed.

Handed off (applied in the row 21, TASK-168, session; #1882 also edits TASK-37.4 and TASK-168, so editing them here would conflict):
- TASK-37.4 AC: before cutover, the just-under-cap pin pads text and a blocks string, and the route serves it well within the integration budget (OQ4).
- TASK-168 comments: the rebuilt matcher is linear and token-bounded and bounds Slack lookups (OQ2, F-I: one users_lookupByEmail call per match, unbounded); the rewritten webhooks.md carries the linear-processing rule into the interpret and render stages (OQ3); keep the 37.4 padding AC in the re-cut.

For the human: review the PR. No deploy checks: no terraform, IAM, SSM or env-name change.

2026-11-20: closed by the agent: PR #1883 merged 2026-11-20 (ac8f8186); all ACs checked.

2026-11-20 correction: TASK-190 merged as #1883 (ac8f8186); #1882 is TASK-36.2.
<!-- SECTION:NOTES:END -->
