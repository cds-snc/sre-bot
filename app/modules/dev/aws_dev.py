"""Testing AWS service (will be removed)"""
from integrations.aws import identity_store

# from modules.aws import sync_groups

# from integrations.aws import identity_store
from dotenv import load_dotenv

load_dotenv()


def aws_dev_command(client, body, respond):
    # user = identity_store.create_user("test.user@test_email.com", "Test", "User")
    # if not user:
    #     respond("There was an error creating the user.")
    #     return
    # respond(f"Created user with user_id: {user}")
    user_id = identity_store.get_user_id("test.user@test_email.com")
    if not user_id:
        respond("No user found.")
        return
    respond(f"Found user_id: {user_id}")
    # result = identity_store.delete_user(user_id)
    # if not result:
    #     respond("There was an error deleting the user.")
    #     return
    # if result:
    #     respond("User deleted.")
    # groups = identity_store.list_groups_with_membership()
    # if not groups:
    #     respond("There was an error retrieving the groups.")
    #     return
    # respond(f"Found {len(groups)} groups.")
    # for k, v in groups[0].items():
    #     print(f"{k}: {v}")
    # users = identity_store.list_users()
    # if not users:
    #     respond("There was an error retrieving the users.")
    #     return
    # respond(f"Found {len(users)} users.")

    # user = identity_store.get_user_id("guillaume.charest@cds-snc.ca")
    # if not user:
    #     respond("There was an error retrieving the user.")
    #     return
    # respond(f"Found user: {user}")

    # groups = identity_store.list_groups()
    # if not groups:
    #     respond("There was an error retrieving the groups.")
    #     return
    # respond(f"Found {len(groups)} groups.")

    # matching_groups = sync_groups.get_aws_google_groups()
    # if not matching_groups:
    #     respond("There was an error retrieving the groups.")
    #     return
    # print(f"Found {len(matching_groups[0])} AWS matching groups.")
    # print(f"Found {len(matching_groups[1])} Google matching groups.")
    # for group in matching_groups[0]:
    #     print(group)
    # # join each group in a multiline string
    # aws_groups = "\n".join(str(group) for group in matching_groups[0])
    # respond(f"aws_groups:\n{aws_groups}")
    # for group in matching_groups[1]:
    #     print(group)
    # for i in range(5):
    #     respond(f"google_group: {matching_groups[1][i]}")
