import json

import structlog

from infrastructure.configuration.features.aws_ops import get_aws_feature_settings
from infrastructure.operations import OperationStatus
from packages.aws_platform.adapters.identity_center import build_identity_center_adapter
from packages.aws_platform.adapters.organizations import build_organizations_adapter
from packages.aws_platform.adapters.sso_admin import build_sso_admin_adapter

logger = structlog.get_logger()


def execute():
    """Assign the AWS Ops group to member accounts."""
    aws_feature_settings = get_aws_feature_settings()
    log = logger.bind()

    # if the feature is not enabled, exit
    if not aws_feature_settings.AWS_OPS_GROUP_NAME:
        return

    group_name = aws_feature_settings.AWS_OPS_GROUP_NAME
    group_result = build_identity_center_adapter().get_group_id(group_name)
    if group_result.status is OperationStatus.NOT_FOUND:
        status = {
            "status": "failed",
            "message": (f"Ops group '{group_name}' not found in AWS Identity Center."),
        }
        log.error("ops_group_not_found", group_name=group_name)
        return status
    # Any other failure (throttling, AccessDenied, ...) is reported with its cause
    # rather than as a missing group.
    if not group_result.is_success or not group_result.data:
        status = {
            "status": "failed",
            "message": (f"Failed to look up Ops group '{group_name}' in AWS Identity Center: {group_result.message}"),
        }
        log.error(
            "ops_group_lookup_failed",
            group_name=group_name,
            status=group_result.status.value,
            error_code=group_result.error_code,
            error=group_result.message,
        )
        return status
    aws_ops_group_id = group_result.data

    accounts_result = build_organizations_adapter().list_organization_accounts()
    if not accounts_result.is_success:
        log.error(
            "organization_accounts_lookup_failed",
            group_name=group_name,
            status=accounts_result.status.value,
            error_code=accounts_result.error_code,
            error=accounts_result.message,
        )
        return {
            "status": "failed",
            "message": f"Failed to list AWS Organization accounts: {accounts_result.message}",
        }

    sso_admin_adapter = build_sso_admin_adapter()
    assignments_result = sso_admin_adapter.list_account_assignments_for_principal(
        principal_id=aws_ops_group_id, principal_type="GROUP"
    )
    if not assignments_result.is_success:
        log.error(
            "ops_group_account_assignments_lookup_failed",
            group_name=group_name,
            status=assignments_result.status.value,
            error_code=assignments_result.error_code,
            error=assignments_result.message,
        )
        return {
            "status": "failed",
            "message": f"Failed to list account assignments for Ops group '{group_name}': {assignments_result.message}",
        }

    organizations_accounts = accounts_result.data or []
    assigned_account_ids = {assignment["AccountId"] for assignment in assignments_result.data or []}

    # get the accounts not yet assigned
    unassigned_accounts = [
        account
        for account in organizations_accounts
        if account.get("Id") not in assigned_account_ids and account.get("Status") == "ACTIVE"
    ]

    if not unassigned_accounts:
        status = {
            "status": "ok",
            "message": (f"Ops group '{group_name}' is already assigned to all active accounts."),
        }
        log.info(
            "all_accounts_already_assigned",
            group_name=group_name,
            total_accounts=len(organizations_accounts),
        )
        return status

    # assign the ops group to unassigned accounts; every outcome is collected so an
    # earlier failure is not masked by a later success
    assigned: list[str] = []
    failed: list[str] = []
    for account in unassigned_accounts:
        account_id = account.get("Id")
        if not account_id:
            log.error(
                "account_missing_id",
                account=json.dumps(account, default=str),
            )
            continue
        account_label = account.get("Name") or account_id
        account_log = log.bind(account_id=account_id, account_name=account.get("Name"))
        account_log.info(
            "assigning_ops_group_to_account",
            aws_ops_group_id=aws_ops_group_id,
        )
        assignment_result = sso_admin_adapter.create_account_assignment(
            user_id=aws_ops_group_id,
            account_id=account_id,
            permission_set="write",
            principal_type="GROUP",
        )
        if assignment_result.is_success and assignment_result.data:
            assigned.append(account_label)
            account_log.info(
                "ops_group_assigned_to_account",
                group_name=group_name,
            )
        else:
            failed.append(account_label)
            account_log.error(
                "failed_to_assign_ops_group_to_account",
                group_name=group_name,
                status=assignment_result.status.value,
                error_code=assignment_result.error_code,
                error=(assignment_result.message if not assignment_result.is_success else "assignment creation status FAILED"),
            )

    if failed:
        return {
            "status": "failed",
            "message": f"Failed to assign Ops group '{group_name}' to {len(failed)} account(s): {', '.join(failed)}.",
        }
    if assigned:
        return {
            "status": "success",
            "message": f"Ops group '{group_name}' assigned to {len(assigned)} account(s): {', '.join(assigned)}.",
        }
    return {
        "status": "failed",
        "message": f"No Ops group assignment made: {len(unassigned_accounts)} unassigned active account(s) have no Id.",
    }
