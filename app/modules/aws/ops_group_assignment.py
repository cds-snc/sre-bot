import json
from core.config import settings
from core.logging import get_module_logger

from integrations.aws import identity_store, organizations, sso_admin


AWS_OPS_GROUP_NAME = settings.aws_feature.AWS_OPS_GROUP_NAME


logger = get_module_logger()


def execute():
    """Assign the AWS Ops group to member accounts."""
    # if the feature is not enabled, exit
    if not AWS_OPS_GROUP_NAME:
        return
    aws_ops_group_id = identity_store.get_group_id(AWS_OPS_GROUP_NAME)
    if not aws_ops_group_id:
        status = {
            "status": "failed",
            "message": (
                f"Ops group '{AWS_OPS_GROUP_NAME}' not found in AWS Identity Center."
            ),
        }
        logger.error("ops_group_not_found", group_name=AWS_OPS_GROUP_NAME)
        return status

    organizations_accounts = organizations.list_organization_accounts()
    account_assignments = sso_admin.list_account_assignments_for_principal(
        principal_id=aws_ops_group_id, principal_type="GROUP"
    )
    assigned_account_ids = {
        assignment["AccountId"] for assignment in account_assignments
    }

    # get the accounts not yet assigned
    unassigned_accounts = [
        account
        for account in organizations_accounts
        if account.get("Id") not in assigned_account_ids
        and account.get("Status") == "ACTIVE"
    ]

    if not unassigned_accounts:
        status = {
            "status": "ok",
            "message": (
                f"Ops group '{AWS_OPS_GROUP_NAME}' is already assigned to all active accounts."
            ),
        }
        logger.info(
            "all_accounts_already_assigned",
            group_name=AWS_OPS_GROUP_NAME,
            total_accounts=len(organizations_accounts),
        )
        return status

    # assign the ops group to unassigned accounts
    for account in unassigned_accounts:
        account_id = account.get("Id")
        if not account_id:
            logger.error(
                "account_missing_id",
                account=json.dumps(account, default=str),
            )
            continue
        logger.info(
            "assigning_ops_group_to_account",
            aws_ops_group_id=aws_ops_group_id,
            account_name=account.get("Name"),
            account_id=account_id,
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
                    f"Ops group '{AWS_OPS_GROUP_NAME}' assigned to account '{account.get('Name')}'."
                ),
            }
            logger.info(
                "ops_group_assigned_to_account",
                group_name=AWS_OPS_GROUP_NAME,
                account_name=account.get("Name"),
                account_id=account_id,
            )
        else:
            status = {
                "status": "failed",
                "message": (
                    f"Failed to assign Ops group '{AWS_OPS_GROUP_NAME}' to account '{account.get('Name')}'."
                ),
            }
            logger.error(
                "failed_to_assign_ops_group_to_account",
                group_name=AWS_OPS_GROUP_NAME,
                account_name=account.get("Name"),
                account_id=account_id,
            )
    return status
