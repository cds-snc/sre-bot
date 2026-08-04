---
status: Accepted
date: 2026-07-29
applies: target
scope: Ownership and enforcement level of the dependency-vulnerability quality gate.
---

# Dependency Scanning

## Context

Renovate (`renovate.json`, extends `cds-snc/renovate-config`) opens dependency-update PRs automatically — that is the update *mechanism*, and it already works. The open question this record answers is separate: does a known-vulnerable dependency block CI, and who triages a finding? Today the answer is nothing and nobody. `.github/workflows/docker_vulnerability_scan.yml` (Trivy) exists but triggers only on `workflow_dispatch` — its schedule is disabled in-file ("Disabling schedule until the Trivy action supports specifying the Docker image architecture") — so it never runs automatically and gates nothing. `.github/workflows/ossf-scorecard.yml` runs on push-to-`main` and a weekly schedule and forwards results to Sentinel — a supply-chain health signal for observability, not a PR gate. No tool scans Python (`uv`) dependencies for known CVEs anywhere in CI. A vulnerable dependency can merge and ship today with no automated signal at merge time.

## Decision

**A blocking CI gate, scoped to severity and directness.** A new step in `ci_code.yml`, run on every PR, scans Python dependencies against `uv.lock` for known vulnerabilities (`uv run pip-audit`; re-evaluate `osv-scanner` if `pip-audit`'s advisory coverage proves insufficient). A **Critical or High** severity finding on a **direct** dependency fails the build — no `|| true` ([toolchain.md](toolchain.md)'s rule). A Medium/Low finding, or a finding confined to a transitive dependency, is logged but does not fail the build — blocking on transitive noise the team often cannot fix same-day would make the gate something people route around, not respect.

**Triage owner is a role, not a person.** The PR author triages first (same as any other failing check); unresolved after 2 business days escalates to the repo maintainer / on-call SRE. A team of one-to-few makes a named individual owner brittle ([governance.md](governance.md)'s "smallest system that works" ethos) — the role is stable even as people rotate.

**Renovate is unaffected.** This record governs whether an *already-merged* vulnerable dependency blocks CI, not how updates are proposed; Renovate PRs continue to open and are reviewed like any other PR, now with this new check running over them too.

**The Docker/Trivy scan and the OSSF scorecard stay observability, not gates.** Re-enabling `docker_vulnerability_scan.yml`'s schedule (once the upstream Trivy architecture limitation clears) is a tolerated follow-up, not a precondition for this record — it scans the shipped image, a different asset than the dependency graph this record covers.

## Consequences

- A new CI step and a newly-recorded triage responsibility where none existed.
- Direct-dependency-only blocking scope keeps the gate actionable; transitive/Medium/Low findings stay visible without becoming a merge blocker the team can't act on same-day.
- `ossf-scorecard.yml` and the Docker scan remain periodic health signals, reviewed on their own cadence, not per-PR gates.

## Checks

- `ci_code.yml` runs a Python dependency-vulnerability scan on every PR; a Critical/High finding on a direct dependency fails the job.
- No `|| true` around the new step.
- This record's Checks do not yet pass on `main` — honest `applies: target`.

## Migration

Ticket: TASK-66 — wire `pip-audit` into `ci_code.yml` as a blocking step for Critical/High findings on direct dependencies; re-enable `docker_vulnerability_scan.yml`'s schedule once the upstream Trivy architecture limitation is confirmed resolved; flip this record's `applies` to `now` once the Checks pass on `main`. Tolerated until closed: no automated dependency-vulnerability gate exists; Renovate PRs are reviewed with no extra scanning.
