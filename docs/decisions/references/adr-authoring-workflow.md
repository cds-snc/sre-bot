# ADR Authoring and Review Workflow

**Purpose:** Reference procedure for authoring, reviewing, and accepting ADRs in this project. Applies to all tiers.

---

## Lifecycle States

```
Proposed → Draft → Challenge Review ←→ Revise → Accepted → [Superseded]
```

| State | Meaning |
|-------|---------|
| **Proposed** | Target reserved in migration map; no body content yet |
| **Draft** | Body authored; awaiting challenge review |
| **Accepted** | Passed challenge review gate; normative and enforceable |
| **Superseded** | Replaced by a newer ADR; file moved to `adr/superseded/` |

---

## Authoring Procedure

### 1. Pre-Author Gate

- Verify the ADR has an allocated ID in the [migration map](adr-migration-map.md).
- Confirm all `constrained_by` ADRs are Accepted. If any are Draft or Proposed, author those first (start a new workflow instance for each blocker).
- Scan for any missing related records or cross-references that should be included in the new ADR.
- Read the challenge review template at `templates/adr-challenge-review-template.md`.
- **Tier-4 only:** Apply the Derivation Test (see §Tier-4 Feature ADR Derivation below) before proceeding.

### 2. Draft the ADR

- Use the metadata template at `templates/adr-metadata-reference.md` (18 required fields).
- Place the file at `adr/NNNN-<slug>.md`.
- Set `status: Draft`.
- Fill all normative sections: Context, Decision, Standards/Principles, Compliance, Migration.
- **Tier-4 only:** Fill the mandatory "Derivation from Higher-Tier ADRs" section (Constraint Derivation Table + Feature-Specific Decisions table). See the decision record template.

### 3. Challenge Review (Round 1)

- Execute review using `templates/adr-challenge-review-template.md`.
- Search online for authoritative sources to validate all claims and standards. Document findings in the review artifact.
- Save the review artifact to `reviews/adr-NNNN-review-YYYY-MM-DD.md`.
- Gate outcomes:
  - **PASS** → proceed to user decision (step 5).
  - **REVISE** → proceed to revision (step 4).

### 4. Revision (if REVISE)

- Address all blockers listed in the review.
- If revision reveals a **blocking dependency** on another ADR that doesn't exist yet:
  1. Pause this workflow.
  2. Start a new workflow instance for the blocking ADR.
  3. Complete that ADR through Accepted.
  4. Resume this workflow.
- After revision, run challenge review again (Round N+1). Save to `reviews/adr-NNNN-review-YYYY-MM-DD-rN.md`.
- Repeat steps 3–4 until PASS.

### 5. User Decision

- Present the PASS review to the user/owner.
- User confirms acceptance or requests further changes.
- If further changes requested → return to step 4.

### 6. Accept

- Set `status: Accepted` in the ADR metadata.
- Record acceptance in the [change log](adr-change-log.md).
- Update the [wave tracker](adr-wave-tracker.md) status.

### 7. Supersession (if applicable)

For each legacy ADR that this new ADR supersedes:

1. Update the legacy ADR metadata:
   - Set `status: Superseded`.
   - Set `superseded_by: ADR-NNNN`.
2. Move the legacy file to `adr/superseded/`.
3. Update any cross-references in other ADRs that pointed to the old file path.
4. Record all moves in the [change log](adr-change-log.md).
5. Update the [migration map](adr-migration-map.md) to reflect the supersession.
6. Update the [wave tracker](adr-wave-tracker.md) to reflect the supersession.
7. Perform a upstream and downstream impact analysis to identify any ADRs that reference the superseded ADR and update them to reference the new ADR if needed.

---

## Blocking ADR Resolution

When authoring or reviewing an ADR surfaces a gap that requires a new or amended ADR:

1. Log the blocker in the review artifact.
2. Allocate an ID for the blocking ADR in the migration map (or identify the existing ADR to amend).
3. Start a new workflow instance for that ADR.
4. Complete it through Accepted before resuming the blocked workflow.
5. Record the dependency resolution in the change log.

---

## Amendment Procedure

For additive or editorial changes to an Accepted ADR (e.g., adding cross-references, caveats, new standards discovered during downstream work):

1. Make the edit directly in the ADR file.
2. If the change is **normative** (alters standards, principles, or compliance rules), run a challenge review round on the amended sections only.
3. If the change is **editorial** (cross-references, caveats, typo fixes), no review round needed.
4. Record the amendment in the change log.

---

## Review Artifact Naming

```
reviews/adr-NNNN-review-YYYY-MM-DD.md        # Round 1 (or sole review on that date)
reviews/adr-NNNN-review-YYYY-MM-DD-r2.md      # Round 2 (or second review on same date)
reviews/adr-NNNN-review-YYYY-MM-DD-rN.md      # Round N
```

---

## Governance Reference

- **ADR-0044:** ADR Governance and Operating Model (Tier-0 authority)
- **ADR-0051:** ADR Taxonomy and Classification Enforcement Standard
- **Review template:** `templates/adr-challenge-review-template.md`
- **Metadata template:** `templates/adr-metadata-reference.md`

---

## Tier-4 Feature ADR Derivation

This section applies exclusively to Tier-4 ADRs (`Feature Decision` or `Integration Decision`).

### Core Principle

> A Tier-4 feature ADR must derive its constraints from settled higher-tier ADRs and address only decisions that are specific to the feature's domain. If the decision would apply to any other feature in the same situation, it belongs in a higher tier.

### Derivation Test

Before authoring a Tier-4 feature ADR, apply all four checks:

1. **Tier-bleed check:** For each norm in the proposed ADR, ask: "Would this apply to a hypothetical different feature with similar needs?" If yes → it belongs in Tier-2/3, not Tier-4.
2. **Constraint chain check:** Every Tier-4 ADR must have a non-empty `constrained_by` list that traces to settled Tier-1/2/3 ADRs. If you can't identify the constraining ADRs, either (a) the higher-tier ADR is missing (author it first), or (b) the decision is too platform-wide for Tier-4.
3. **Single-concern check:** The ADR must address exactly one feature-scoped decision. If the Context section describes problems at multiple tiers, split the record.
4. **Domain-specificity check:** The ADR's Standards/Principles section should reference domain entities, domain events, or domain workflows that don't exist outside this feature.

### Scoping Rules for Complex Features

For features with multiple distinct sub-functionalities (like access):

| Rule | Rationale |
|------|-----------|
| **One ADR per sub-feature concern** | Each sub-feature has its own domain model, lifecycle, and integration surface. Mixing recreates the legacy mixed-concern anti-pattern. |
| **Shared concerns get a separate ADR** | If common/ owns a decision (config loading, naming, event contracts), it gets its own Tier-4 ADR — not embedded in a sub-feature ADR. |
| **ADR-per-decision, not ADR-per-package** | The unit of decomposition is the *decision*, not the *directory*. A sub-feature with no feature-specific decisions beyond what higher tiers mandate doesn't need a Tier-4 ADR. |
| **Cross-sub-feature coordination is a separate decision** | If sub-features interact (e.g., "request approval triggers sync run"), the coordination contract is a separate Tier-4 ADR, not embedded in either sub-feature's ADR. |

### Mixed-Concern Anti-Pattern

Legacy feature ADRs frequently packed multiple tier concerns into a single record. When decomposing or superseding legacy feature ADRs:

1. **Identify each concern's proper tier** — map each norm to the tier it actually belongs in.
2. **Route higher-tier content to existing ADRs** — if a Tier-2 standard already governs the concern, it does not need restatement in the Tier-4 record.
3. **Author only the feature-specific residue** — the Tier-4 replacement contains only the domain-specific decisions not governed by any higher-tier ADR.
4. **Record the decomposition** — the Derivation Table explicitly shows which concerns are inherited vs. feature-specific.

### Freeze Zone Discipline for Legacy Feature Migration

Before migrating a legacy module to `app/packages/`, the following rules apply:

| Rule | Description |
|------|-------------|
| **F1** | No behavioral changes to frozen zones during infrastructure foundation work |
| **F2** | Bug fixes in frozen zones are permitted (existing infrastructure surface only) |
| **F3** | Frozen zones may receive passive updates from infrastructure (mechanical call-site updates for API changes) |
| **F4** | Thawing requires a Tier-4 ADR — before a frozen zone is migrated, its target architecture must pass challenge review |
| **F5** | One zone thaws at a time — never migrate two legacy modules simultaneously |
| **F6** | Raw infrastructure access (e.g., DynamoDB) must be abstracted before or during thaw |
| **F7** | Frozen support packages (`app/core/`, `app/integrations/`, `app/models/`, `app/locales/`, `app/utils/`) follow the same freeze rules as business zones |

### Migration Execution Order

Feature ADR authoring and module migration must follow this sequence:

1. **Phase 1 — Infrastructure Foundation:** Settings dissolution, provider restructuring, infrastructure service contracts, event dispatcher fix. Frozen zones untouched.
2. **Phase 2 — Access Feature Finalization:** Complete access sub-feature ADRs (Tier-4), access code completion against new infrastructure surface, Wave 2.5 execution (ADR-0068, 0069).
3. **Phase 3 — Legacy Module Migration:** Author Tier-4 ADR before each migration, then migrate one module at a time to `app/packages/`. Order: Incident → Webhooks → AWS Ops → SRE Ops/ATIP.
4. **Phase 4 — Legacy Cleanup:** Remove `app/modules/`, `app/core/`, `app/models/`, `app/locales/`, `app/utils/` after all consumers migrate.
