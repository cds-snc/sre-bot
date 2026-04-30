# ADR Horizontal-Vertical Review Methodology

**Purpose:** Systematic gap, ambiguity, and conflict detection across an ADR corpus. Validates completeness and internal consistency independent of existing metadata cross-references.  
**Scope:** Reusable reference procedure — defines the review methodology and outcome mapping format.  
**Trigger:** Pre-implementation validation gate. Before code changes begin, confirm the normative ADR corpus is internally consistent and complete.

> **This is not a challenge review.** Challenge reviews validate a single ADR against external standards and platform reality (Section 2 of the review template). This review validates **relationships between ADRs** — whether norms across the corpus are consistent, complete, and correctly stratified by tier. The two exercises are complementary but distinct.

---

## 1. Problem Statement

When an ADR program produces multiple canonical ADRs across tiered governance (Tier-0 through Tier-5), each ADR is typically challenge-reviewed individually against external standards and platform reality. However, this leaves **cross-ADR consistency unvalidated** — each review validates the ADR in isolation or against its declared `constrained_by` and `impacts` metadata.

This creates three categories of risk:

| Risk | Description | Example |
|------|-------------|---------|
| **Gap** | A concern that should be governed but no ADR addresses it, or an ADR addresses it partially | Two ADRs both assume "the other one" governs error retry behavior, so neither does |
| **Ambiguity** | Two or more ADRs use overlapping language that could be interpreted as governing the same concern differently | ADR-X says "providers must be singletons" and ADR-Y says "services should use factory pattern" — which wins? |
| **Conflict** | Two ADRs contain norms that cannot both be satisfied simultaneously | ADR-X Standard 3 mandates behavior A; ADR-Y Standard 5 mandates behavior ¬A for the same scope |

Existing metadata (`constrained_by`, `impacts`, `related_records`) may be incomplete, circular, or stale. **This review deliberately ignores metadata cross-references** and evaluates ADR content on its own terms.

A key deliverable is a **rebuilt cross-reference map** — an accurate, evidence-based mapping of which ADRs actually constrain, impact, or relate to each other based on norm content analysis rather than authoring-time assumptions.

---

## 2. Methodology

### 2.1 Review Axes

The review operates on two axes, applied to the tiered ADR hierarchy:

```
Tier 0:  [governance] ←──horizontal──→ ...
              │
              vertical
              ↓
Tier 1:  [principle A] ←→ [principle B] ←→ ...
              │
              vertical
              ↓
Tier 2:  [standard A] ←→ [standard B] ←→ ...
              │
              vertical
              ↓
Tier 3:  [domain contract A] ←→ ...
              │
              vertical
              ↓
Tier 4:  [feature decision A] ←→ ...
```

**Horizontal review:** Compare every ADR within a tier against every other ADR in the same tier. Detect intra-tier conflicts, overlapping scope, redundant norms, and gaps between adjacent concerns.

**Vertical review:** Compare each ADR against every ADR in the tier directly above it. Detect constraint violations (child contradicts parent), missing derivation (child doesn't trace to any parent norm), and orphaned norms (child creates a norm that should exist at the parent tier).

### 2.2 Review Order

The review proceeds top-down, completing horizontal before vertical at each tier:

| Step | Axis | Scope | Description |
|------|------|-------|-------------|
| 1 | Horizontal | Tier 0 | All Tier-0 ADRs against each other. Self-consistency check if single ADR. |
| 2 | Horizontal | Tier 1 | All Tier-1 ADRs against each other. N ADRs → N(N-1)/2 pairwise comparisons. |
| 3 | Vertical | Tier 0 → 1 | Each Tier-1 ADR against every Tier-0 ADR. |
| 4 | Horizontal | Tier 2 | All Tier-2 ADRs against each other. Use domain clustering (§2.5) for large sets. |
| 5 | Vertical | Tier 1 → 2 | Each Tier-2 ADR against every Tier-1 ADR. |
| 6 | Horizontal | Tier 3 | All Tier-3 ADRs against each other. |
| 7 | Vertical | Tier 2 → 3 | Each Tier-3 ADR against every Tier-2 ADR. |
| 8 | Horizontal | Tier 4 | All Tier-4 ADRs against each other. |
| 9 | Vertical | Tier 3 → 4 | Each Tier-4 ADR against every Tier-3 ADR. |
| 10 | Vertical | Tier 2 → 4 | Each Tier-4 ADR against every Tier-2 ADR. |

**Note on Tier-5:** Tier-5 records (migration/deprecation instructions) are not normative architecture. They are validated against their governing ADRs during vertical review but do not participate in horizontal review.

### 2.3 Comparison Budget

For a corpus with $T_n$ ADRs at tier $n$:

- **Horizontal comparisons per tier:** $\frac{T_n(T_n - 1)}{2}$
- **Vertical comparisons (tier $n$ → $n+1$):** $T_n \times T_{n+1}$
- **Total comparisons:** Sum of all horizontal and vertical comparisons across all tiers.

Tier-2 horizontal typically dominates. Use domain clustering (§2.5) to manage large comparison sets.

### 2.4 What the Reviewer Checks at Each Comparison

For each pair (ADR-A, ADR-B):

**Horizontal checks (same tier):**

| Check | Question |
|-------|----------|
| **H1 — Scope overlap** | Do A and B govern any of the same concerns? If yes, do they agree? |
| **H2 — Term consistency** | Do A and B use the same term to mean different things, or different terms for the same thing? |
| **H3 — Norm conflict** | Does any standard/principle in A contradict a standard/principle in B? |
| **H4 — Gap between** | Is there a concern that falls between A and B that neither governs? |
| **H5 — Redundancy** | Does A restate a norm from B (or vice versa) without adding specificity? If yes, which is authoritative? |

**Vertical checks (parent tier → child tier):**

| Check | Question |
|-------|----------|
| **V1 — Derivation** | Does every norm in the child trace to (or deliberately extend) a parent norm? |
| **V2 — Contradiction** | Does any child norm contradict a parent norm? |
| **V3 — Tier bleed** | Does the child contain norms that belong at the parent tier (too general for the child's scope)? |
| **V4 — Missing parent** | Does the child assume a constraint that no parent ADR establishes? (Indicates a gap at the parent tier.) |
| **V5 — Orphan extension** | Does the child extend a parent norm in a way that should be back-propagated to the parent? |
| **V6 — No relationship** | Does the child have no traceable relationship to any ADR in the parent tier? If so, record this — it may indicate a missing intermediate ADR, a misclassified tier, or an isolated concern that should be evaluated for correct placement. |

### 2.5 Domain Clustering for Large Tiers

When a tier contains many ADRs (e.g., 15+ Tier-2 records), group them by functional domain and compare within clusters first, then across clusters:

| Step | Comparisons | Purpose |
|------|-------------|---------|
| Intra-cluster | Within each domain group | Catch tight-domain conflicts and redundancies |
| Inter-cluster | Across domain groups | Catch cross-cutting concerns and boundary disputes |

Example cluster categories (adapt to your corpus):

| Cluster | Domain |
|---------|--------|
| Governance | Plugin registration, taxonomy |
| Data & Results | Operation results, API response, validation |
| Delivery & Runtime | Build-release-run, port binding, shutdown, background execution |
| Settings & Providers | Configuration, provider discovery, import boundaries, service contracts |
| Platform & Integration | Feature interaction, platform services, messaging |
| Quality & Security | Testing, security, rate-limiting |

---

## 3. Outcome Mapping Format

Each finding is recorded in a structured table with severity classification and resolution tracking.

### 3.1 Finding Record

| Field | Description |
|-------|-------------|
| **ID** | Sequential: `HV-NNN` (H = horizontal finding, V = vertical finding) |
| **Step** | Which review step (1–10) produced the finding |
| **Type** | `Gap` / `Ambiguity` / `Conflict` / `Redundancy` |
| **Severity** | `Critical` (blocks implementation) / `Major` (requires amendment before implementation) / `Minor` (track, fix opportunistically) / `Note` (observation, no action required) |
| **ADRs** | Which ADRs are involved |
| **Check** | Which check triggered (H1–H5, V1–V6) |
| **Description** | Concise statement of the finding |
| **Evidence** | Specific norms/standards quoted from each ADR |
| **Resolution** | `Unresolved` / `Amendment needed: ADR-NNNN` / `New ADR needed` / `Accepted as-is (rationale)` |
| **Resolution Date** | When resolved |

### 3.2 Summary Dashboard

After all steps complete, produce a summary:

```markdown
## Review Summary

| Severity | Gap | Ambiguity | Conflict | Redundancy | Total |
|----------|-----|-----------|----------|------------|-------|
| Critical |     |           |          |            |       |
| Major    |     |           |          |            |       |
| Minor    |     |           |          |            |       |
| Note     |     |           |          |            |       |
| **Total**|     |           |          |            |       |

**Completion:**
- Steps completed: X / 10
- Comparisons completed: X / Y
- Findings: X total (Y unresolved)
- Implementation gate: PASS / BLOCKED (N critical findings)
```

### 3.3 Implementation Gate Criteria

| Criterion | Threshold |
|-----------|-----------|
| Critical findings | 0 unresolved |
| Major findings | 0 unresolved (all amended or accepted with rationale) |
| Minor findings | Tracked — resolution not required before implementation |
| Notes | Logged — no action required |

Implementation may begin only when the gate criteria are met.

---

## 4. Execution Rules

| Rule | Rationale |
|------|-----------|
| **Ignore metadata** | Existing `constrained_by`, `impacts`, `related_records` may be incomplete or circular. Read the ADR body text, not the metadata header. |
| **Read the norms, not the intent** | Compare what the ADR *mandates* (standards, principles, rules), not what the Context section *describes*. Context motivates; norms govern. |
| **Quote, don't paraphrase** | Every finding must cite the specific standard/principle text from each involved ADR. No interpretive summaries. |
| **One finding per issue** | Do not bundle multiple issues into one finding. Each gets its own ID and resolution track. |
| **Classify conservatively** | When unsure between Major and Minor, classify as Major. Downgrade after investigation. |
| **Complete horizontal before vertical** | Do not start vertical review for a tier until all horizontal comparisons for that tier are recorded. Horizontal findings may reveal scope overlaps that change vertical interpretation. |
| **Record "no finding" steps** | If a step produces zero findings, record it as complete with zero findings. This proves the step was executed, not skipped. |
| **Tier-5 passthrough** | Tier-5 records are checked during vertical review only — confirm the migration/deprecation instructions don't contradict their governing ADR's current norms. They do not participate in horizontal review. |

---

## 5. Execution Procedure

### Step-by-Step

1. **Inventory** all ADRs in the corpus. Group by tier. Compute comparison budget (§2.3).
2. **Load** all ADR body texts for the tier under review (ignore metadata headers).
3. **Horizontal pass:** For each pair, apply checks H1–H5. Record findings immediately.
4. **Horizontal summary:** Count findings by type and severity. Identify any that require resolution before proceeding.
5. **Resolve critical/major horizontal findings** before starting vertical review for that tier. Minor findings and notes are tracked but don't block.
6. **Vertical pass:** For each child ADR, apply checks V1–V6 against every parent-tier ADR. Record findings.
7. **Vertical summary:** Count findings. Identify any that require resolution.
8. **Resolve critical/major vertical findings** before moving to the next tier.
9. **Advance to next tier** (horizontal, then vertical). Repeat steps 2–8.
10. **Final summary:** Produce the summary dashboard (§3.2). Evaluate against gate criteria (§3.3).

### Batching for Large Tiers

For large horizontal comparison sets (e.g., Tier-2):

1. Complete all intra-cluster comparisons first (within each domain cluster from §2.5).
2. Then complete inter-cluster comparisons in systematic cluster-pair order.
3. Record findings per cluster pair for traceability.

---

## 6. Output Artifacts

| Artifact | Purpose |
|----------|---------|
| Finding records | Individual issue tracking with severity, evidence, and resolution |
| Summary dashboard | Aggregate status and gate assessment |
| Rebuilt cross-reference map | Accurate ADR relationship mapping based on norm-content analysis |
| ADR amendments | Fix conflicts, gaps, or ambiguities identified by the review |
| ADR metadata corrections | Update `constrained_by`, `impacts`, `related_records` to match verified relationships |
| Change log entries | Audit trail for all amendments |
| Wave tracker updates | If new ADRs are needed |
| Migration map updates | If new ADRs are allocated |

### Cross-Reference Map Structure

The rebuilt cross-reference map should include:

| Section | Content |
|---------|---------|
| **Verified Constraint Graph** | For each ADR: current vs. verified `constrained_by`, with deltas and finding references |
| **Verified Impact Graph** | For each ADR: current vs. verified `impacts`, with deltas |
| **Verified Related Records** | Same-tier relationships discovered during horizontal review |
| **Orphan Analysis** | ADRs with no verified vertical relationship to the tier above |
| **Metadata Correction Plan** | Consolidated diff for all metadata changes to apply |

---

## 7. Governance Reference

- **ADR-0044:** ADR Governance and Operating Model (Tier-0 authority)
- **ADR-0051:** ADR Taxonomy and Classification Enforcement Standard
- **Review template:** `templates/adr-challenge-review-template.md`
- **Metadata template:** `templates/adr-metadata-reference.md`
