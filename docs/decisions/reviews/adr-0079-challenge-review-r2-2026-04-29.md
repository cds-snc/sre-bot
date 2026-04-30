# ADR Challenge and Content Review (Round 2) — ADR-0079

**Purpose:** Secondary challenge review of ADR-0079: Queueing and Message-Broker Architecture Standard. This review evaluates the **revised** document produced after Round 1 findings were addressed. All judgments are anchored on authoritative best practices, codebase evidence, and cross-ADR consistency.

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0079: Queueing and Message-Broker Architecture Standard |
| **Reviewer Name & Title** | SRE Architecture Review, SRE Team |
| **Secondary Reviewers** | — |
| **Review Date** | 2026-04-29 |
| **Prior Review** | 2026-04-29 Round 1 — Gate Outcome: ⚪ REVISE |
| **Revalidation Due** | 2027-04-29 |
| **Gate Outcome** | ✅ **PASS** |
| **Outcome Rationale** | All Round 1 blockers resolved. Lifecycle phase numbers corrected throughout to match ADR-0046 Invariant 2 canonical ordering. Shutdown ordering corrected to reflect Transport-phase reverse order (step 2, not step 1). All three non-blocking corrections applied (daemon thread factual error, NotificationService classification wording, ADR-0058 metadata gap). No new normative issues identified. |

---

## 2. Round 1 Blocker Resolution Verification

| Round 1 Blocker | Status | Evidence |
|-----------------|--------|----------|
| **Lifecycle phase numbering — "phase 6 (transport phase)" in Context constraints** | ✅ Resolved | Corrected to "phase 5 (transport phase)" — matches ADR-0046 Invariant 2 Phase 5 (Transport). |
| **Lifecycle phase numbering — "phase 5 (plugin registration)" in Standard 2** | ✅ Resolved | Corrected to "phase 4 (feature activation — handlers, event subscribers, integrations)" — matches ADR-0046 Invariant 2 Phase 4 (Feature Activation). The label now matches the phase description exactly. |
| **Lifecycle phase numbering — "phase 6 (transport phase)" in Standard 5** | ✅ Resolved | Corrected to "phase 5 (transport phase)" — matches ADR-0046 Invariant 2 Phase 5 (Transport). |
| **Shutdown ordering — "shutdown phase 1 (first to stop)" in Standard 5** | ✅ Resolved | Corrected to "shutdown step 2 (reverse of phase 5 — background work stops first in step 1, then transport connections including queue consumers stop in step 2)". This matches ADR-0046 Invariant 4: reverse-order means Background (Phase 6) stops first, then Transport (Phase 5) stops second. |
| **Compliance section phase numbers — "phase 5 (plugin registration)" and "phase 6 (transport)"** | ✅ Resolved | Corrected to "phase 3 (discovery and registration)" for consumer registration, "phase 4 (feature activation)" for event handler registration, and "phase 5 (transport)" for consumer start. The three-phase progression is now explicit and matches ADR-0046 exactly. |

## 3. Non-Blocking Correction Verification

| Round 1 Non-Blocker | Status | Evidence |
|---------------------|--------|----------|
| **Daemon thread factual error** | ✅ Resolved | Context section corrected from "daemon thread" to "non-daemon thread". Verified: `ScheduleThread` in `app/jobs/scheduled_tasks.py` extends `threading.Thread` without setting `daemon=True`. |
| **NotificationService classification wording** | ✅ Resolved | Standard 4 corrected from "notification service (ADR-0077 Category A P2)" to "notification service (ADR-0077 P2 migration candidate)". This accurately reflects that NotificationService is a P2 migration candidate, not currently Category A. |
| **ADR-0058 metadata gap** | ✅ Resolved | ADR-0058 `related_records` updated to include `ADR-0079`. Metadata-only change, no normative impact. |

---

## 4. Phase Numbering Consistency Audit

Cross-checking all phase references in the revised document against ADR-0046 Invariant 2:

| ADR-0046 Phase | ADR-0046 Label | ADR-0079 Usage | Correct? |
|----------------|----------------|----------------|----------|
| Phase 3 | Discovery and Registration | Queue consumer registration via pluggy hookspecs (Compliance section) | ✅ |
| Phase 4 | Feature Activation (handlers, event subscribers, integrations) | Event handler registration (Standard 2, Compliance section) | ✅ |
| Phase 5 | Transport (WebSocket, message queues) | Queue consumer start (Context constraints, Standard 5, Compliance section) | ✅ |
| Phase 6 | Background (scheduled and background work) | Not referenced for queue consumers (correctly — queue consumers are Transport, not Background) | ✅ |
| Shutdown Step 1 | Background stops first (reverse of Phase 6) | Not claimed for queue consumers (correctly) | ✅ |
| Shutdown Step 2 | Transport stops second (reverse of Phase 5) | Queue consumer shutdown (Standard 5) | ✅ |

**Audit result:** All 6 phase references are consistent with ADR-0046 Invariant 2 and Invariant 4.

---

## 5. Normative Content Spot-Check

| Standard | Check | Result |
|----------|-------|--------|
| Standard 1 (Queue Abstraction) | Protocol contracts for MessageProducer/MessageConsumer, Category A classification | ✅ Unchanged from R1 — correctly aligned |
| Standard 2 (Event Dispatcher Remediation) | Phase 4 handler registration, pluggy hookspec pattern | ✅ Phase corrected; remediation path unchanged |
| Standard 3 (Delivery Semantics) | At-least-once with idempotent consumers | ✅ Unchanged from R1 — correctly aligned |
| Standard 4 (Dead-Letter Policy) | NotificationService classification wording | ✅ Corrected to P2 migration candidate |
| Standard 5 (Consumer Lifecycle) | Phase 5 startup, step 2 shutdown | ✅ Both corrected; lifecycle integration is now consistent |
| Standard 6 (Settings Partitioning) | QueueSettings with independent singleton | ✅ Unchanged from R1 — correctly aligned |
| Standard 7 (Evolution Phases) | 5-phase evolution model | ✅ Unchanged from R1 — correctly aligned |

---

## 6. Cross-ADR Contradiction Re-Check

| R1 Contradiction | Resolution |
|------------------|------------|
| Phase number mismatch with ADR-0046 (4 instances) | ✅ All corrected — zero contradictions remain |
| Shutdown ordering mismatch with ADR-0046 Invariant 4 | ✅ Corrected — Transport stops in step 2 |
| ADR-0058 missing `related_records` reference | ✅ Metadata updated |

**Contradiction audit result:** No cross-ADR contradictions remain.

---

## 7. Binary Gate Outcome

**GATE DECISION:**

✅ **PASS** → ADR-0079 is ready for user acceptance decision

**Resolution summary:**

- 2 primary blockers (phase numbering, shutdown ordering) — all resolved
- 3 non-blocking corrections (daemon thread, NotificationService wording, ADR-0058 metadata) — all resolved
- 0 new issues identified during R2

---

## 8. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | SRE Architecture Review |
| **Reviewer Title** | Senior SRE / Architecture |
| **Organization/Team** | SRE Team |
| **Sign-Off Date** | 2026-04-29 |
