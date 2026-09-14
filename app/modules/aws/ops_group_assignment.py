import json

import structlog

from infrastructure.configuration.features.aws_ops import get_aws_feature_settings
from infrastructure.operations import OperationStatus
from integrations.aws import organizations, sso_admin
from packages.aws_platform.adapters.identity_center import build_identity_center_adapter

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

    organizations_accounts = organizations.list_organization_accounts()
    account_assignments = sso_admin.list_account_assignments_for_principal(principal_id=aws_ops_group_id, principal_type="GROUP")
    assigned_account_ids = {assignment["AccountId"] for assignment in account_assignments}

    # get the accounts not yet assigned
    unassigned_accounts = [
        account
        for account in organizations_accounts
        if account.get("Id") not in assigned_account_ids and account.get("Status") == "ACTIVE"
    ]

    if not unassigned_accounts:
        status = {
            "status": "ok",
            "message": (f"Ops group '{aws_feature_settings.AWS_OPS_GROUP_NAME}' is already assigned to all active accounts."),
        }
        log.info(
            "all_accounts_already_assigned",
            group_name=aws_feature_settings.AWS_OPS_GROUP_NAME,
            total_accounts=len(organizations_accounts),
        )
        return status

    # assign the ops group to unassigned accounts
    for account in unassigned_accounts:
        account_id = account.get("Id")
        if not account_id:
            log.error(
                "account_missing_id",
                account=json.dumps(account, default=str),
            )
            continue
        account_log = log.bind(account_id=account_id, account_name=account.get("Name"))
        account_log.info(
            "assigning_ops_group_to_account",
            aws_ops_group_id=aws_ops_group_id,
        )
        success = sso_admin.create_account_assignment(
            user_id=aws_ops_group_id,
            account_id=account_id,
            permission_set="write",
            principal_type="GROUP",
        )
        if success:
            status = {
                "status": "success",
                "message": (
                    f"Ops group '{aws_feature_settings.AWS_OPS_GROUP_NAME}' assigned to account '{account.get('Name')}'."
                ),
            }
            account_log.info(
                "ops_group_assigned_to_account",
                group_name=aws_feature_settings.AWS_OPS_GROUP_NAME,
            )
        else:
            status = {
                "status": "failed",
                "message": (
                    f"Failed to assign Ops group '{aws_feature_settings.AWS_OPS_GROUP_NAME}' to account '{account.get('Name')}'."
                ),
            }
            account_log.error(
                "failed_to_assign_ops_group_to_account",
                group_name=aws_feature_settings.AWS_OPS_GROUP_NAME,
            )
    return status
