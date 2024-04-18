"""Testing AWS service (will be removed)"""
import os

from integrations.aws import identity_store, client as aws_client
from dotenv import load_dotenv

load_dotenv()


def aws_dev_command(client, body, respond):
    groups = identity_store.list_groups()
    if not groups:
        respond("There was an error retrieving the groups.")
        return
    respond(f"Found {len(groups)} groups.")
    for k, v in groups[0].items():
        print(f"{k}: {v}")

    users = identity_store.list_users()
    if not users:
        respond("There was an error retrieving the users.")
        return
    respond(f"Found {len(users)} users.")
