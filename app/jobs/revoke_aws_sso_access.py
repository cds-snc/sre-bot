from core.logging import get_module_logger
from integrations.aws import identity_store, sso_admin
from modules.aws import aws_access_requests
from modules.ops.notifications import log_ops_message

logger = get_module_logger()


def revoke_aws_sso_access(client):
    for request in aws_access_requests.get_expired_requests():
        account_id = request["account_id"]["S"]
        account_name = request["account_name"]["S"]
        user_id = request["user_id"]["S"]
        email = request["email"]["S"]
        access_type = request["access_type"]["S"]
        created_at = request["created_at"]["N"]

        logger.info(
            "revoking_aws_sso_access",
            account_name=account_name,
            account_id=account_id,
            user_id=user_id,
            email=email,
            access_type=access_type,
            created_at=created_at,
        )

        try:
            aws_user_id = identity_store.get_user_id(email)
            sso_admin.delete_account_assignment(aws_user_id, account_id, access_type)
            aws_access_requests.expire_request(
                account_id=account_id, created_at=created_at
            )
            msg = f"Revoked access to {account_name} ({account_id}) for <@{user_id}> ({email}) with access type: {access_type}"
            client.chat_postEphemeral(
                channel=user_id,
                user=user_id,
                text=msg,
            )
            log_ops_message(client, msg)

        except Exception as e:
            logger.error(
                "failed_to_revoke_aws_sso_access",
                account_name=account_name,
                account_id=account_id,
                user_id=user_id,
                email=email,
                access_type=access_type,
                error=str(e),
            )
