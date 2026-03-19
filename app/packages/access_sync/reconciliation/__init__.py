"""Access Sync reconciliation sub-package.

Drift detection and scheduled convergence execution.
This is a v1 skeleton — the full reconciliation engine is a future milestone.

Planned reconciliation flow:
  1. List all users who are members of any managed authn group in the IDP.
  2. For each user, call AccessSyncService.sync_user per registered platform.
  3. Collect drift records (users present on platform but not in IDP, etc.).
  4. Emit RECONCILIATION_COMPLETED event with a drift summary.
  5. Persist a reconciliation checkpoint in the SyncRunStore.
"""
