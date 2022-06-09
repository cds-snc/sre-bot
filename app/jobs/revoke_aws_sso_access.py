from integrations import aws_sso
from models import aws_access_requests
from commands.utils import log_ops_message
import logging

logging.basicConfig(level=logging.INFO)


def revoke_aws_sso_access(client):
    for request in aws_access_requests.get_expired_requests():
        account_id = request["account_id"]["S"]
        account_name = request["account_name"]["S"]
        user_id = request["user_id"]["S"]
        email = request["email"]["S"]
        access_type = request["access_type"]["S"]
        created_at = request["created_at"]["N"]

        logging.info(
            f"Revoking access to {account_name} ({account_id}) for <@{user_id}> with access type: {access_type}"
        )

        try:
            aws_user_id = aws_sso.get_user_id(email)
            aws_sso.remove_permissions_for_user(aws_user_id, account_id, access_type)
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
            logging.error(
                f"Failed to revoke access to {account_name} ({account_id}) for <@{user_id}> with access type: {access_type}"
            )
            logging.error(e)
