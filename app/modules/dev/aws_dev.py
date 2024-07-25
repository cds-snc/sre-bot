"""Testing AWS service (will be removed)"""

import logging

from integrations.aws import organizations

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def aws_dev_command(ack, client, body, respond):
    ack()
    response = organizations.list_organization_accounts()
    accounts = {account["Id"]: account["Name"] for account in response}
    accounts = dict(sorted(accounts.items(), key=lambda i: i[1]))
    formatted_accounts = ""
    for account in accounts.keys():
        formatted_accounts += f"{account}: {accounts[account]}\n"

    if not response:
        respond("Sync failed. See logs")
    else:
        logger.info(accounts)
        respond("Sync successful. See logs\n" + formatted_accounts)
