import arrow
import boto3
import os

ROLE_ARN = os.environ.get("AWS_ORG_ACCOUNT_ROLE_ARN")


def assume_role_client(client_type):
    client = boto3.client("sts")

    response = client.assume_role(
        RoleArn=ROLE_ARN, RoleSessionName="SREBot_Org_Account_Role"
    )

    session = boto3.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )

    return session.client(client_type)


def get_accounts():
    client = assume_role_client("organizations")
    response = client.list_accounts()
    accounts = {}
    # Loop response for NextToken
    while True:
        for account in response["Accounts"]:
            accounts[account["Id"]] = account["Name"]
        if "NextToken" in response:
            response = client.list_accounts(NextToken=response["NextToken"])
        else:
            break
    return dict(sorted(accounts.items(), key=lambda item: item[1]))


def get_account_health(account_id):
    last_day_of_current_month = arrow.utcnow().span("month")[1].format("YYYY-MM-DD")
    first_day_of_current_month = arrow.utcnow().span("month")[0].format("YYYY-MM-DD")
    last_day_of_last_month = (
        arrow.utcnow().shift(months=-1).span("month")[1].format("YYYY-MM-DD")
    )
    first_day_of_last_month = (
        arrow.utcnow().shift(months=-1).span("month")[0].format("YYYY-MM-DD")
    )

    data = {
        "account_id": account_id,
        "cost": {
            "last_month": {
                "start_date": first_day_of_last_month,
                "end_date": last_day_of_last_month,
                "amount": get_account_spend(
                    account_id, first_day_of_last_month, last_day_of_last_month
                ),
            },
            "current_month": {
                "start_date": first_day_of_current_month,
                "end_date": last_day_of_current_month,
                "amount": get_account_spend(
                    account_id, first_day_of_current_month, last_day_of_current_month
                ),
            },
        },
        "security": {
            "config": 0,
            "guardduty": 0,
            "securityhub": 0,
            "trusted_advisor": 0,
        },
    }

    return data


def get_account_spend(account_id, start_date, end_date):
    client = assume_role_client("ce")
    response = client.get_cost_and_usage(
        TimePeriod={"Start": start_date, "End": end_date},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[
            {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
        ],
        Filter={"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}},
    )
    if "Groups" in response["ResultsByTime"][0]:
        return "{:0,.2f}".format(
            float(
                response["ResultsByTime"][0]["Groups"][0]["Metrics"]["UnblendedCost"][
                    "Amount"
                ]
            )
        )
    else:
        return "0.00"
