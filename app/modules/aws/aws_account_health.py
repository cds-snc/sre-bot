import arrow
import boto3  # type: ignore
import os
from slack_bolt import Ack
from slack_sdk import WebClient
from logging import Logger

from integrations.aws import organizations

AUDIT_ROLE_ARN = os.environ["AWS_AUDIT_ACCOUNT_ROLE_ARN"]
LOGGING_ROLE_ARN = os.environ.get("AWS_LOGGING_ACCOUNT_ROLE_ARN")
ORG_ROLE_ARN = os.environ.get("AWS_ORG_ACCOUNT_ROLE_ARN")


def assume_role_client(client_type, role=ORG_ROLE_ARN, region="ca-central-1"):
    client = boto3.client("sts")

    response = client.assume_role(
        RoleArn=role, RoleSessionName="SREBot_Org_Account_Role"
    )

    session = boto3.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )

    return session.client(client_type, region_name=region)


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
            "config": get_config_summary(account_id),
            "guardduty": get_guardduty_summary(account_id),
            "securityhub": get_securityhub_summary(account_id),
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


def get_config_summary(account_id):
    client = assume_role_client("config", role=AUDIT_ROLE_ARN)
    response = client.describe_aggregate_compliance_by_config_rules(
        ConfigurationAggregatorName="aws-controltower-GuardrailsComplianceAggregator",
        Filters={
            "AccountId": account_id,
            "ComplianceType": "NON_COMPLIANT",
        },
    )
    return len(response["AggregateComplianceByConfigRules"])


def get_guardduty_summary(account_id):
    client = assume_role_client("guardduty", role=LOGGING_ROLE_ARN)
    detector_id = client.list_detectors()["DetectorIds"][0]
    response = client.get_findings_statistics(
        DetectorId=detector_id,
        FindingStatisticTypes=[
            "COUNT_BY_SEVERITY",
        ],
        FindingCriteria={
            "Criterion": {
                "accountId": {"Eq": [account_id]},
                "service.archived": {"Eq": ["false", "false"]},
                "severity": {"Gte": 7},
            }
        },
    )

    return sum(response["FindingStatistics"]["CountBySeverity"].values())


def get_securityhub_summary(account_id):
    client = assume_role_client("securityhub", role=LOGGING_ROLE_ARN)
    response = client.get_findings(
        Filters={
            "AwsAccountId": [{"Value": account_id, "Comparison": "EQUALS"}],
            "ComplianceStatus": [
                {"Value": "FAILED", "Comparison": "EQUALS"},
            ],
            "RecordState": [
                {"Value": "ACTIVE", "Comparison": "EQUALS"},
            ],
            "SeverityProduct": [
                {
                    "Gte": 70,
                    "Lte": 100,
                },
            ],
            "Title": get_ignored_security_hub_issues(),
            "UpdatedAt": [
                {"DateRange": {"Value": 1, "Unit": "DAYS"}},
            ],
            "WorkflowStatus": [
                {"Value": "NEW", "Comparison": "EQUALS"},
            ],
        }
    )
    issues = 0
    # Loop response for NextToken
    while True:
        issues += len(response["Findings"])
        if "NextToken" in response:
            response = client.get_findings(NextToken=response["NextToken"])
        else:
            break
    return issues


def get_ignored_security_hub_issues():
    ignored_issues = [
        "IAM.6 Hardware MFA should be enabled for the root user",
        '1.14 Ensure hardware MFA is enabled for the "root" account',
    ]

    return list(map(lambda t: {"Value": t, "Comparison": "NOT_EQUALS"}, ignored_issues))


def health_view_handler(ack: Ack, body, logger: Logger, client: WebClient):
    ack()

    account_id = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["value"]

    account_name = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["text"]["text"]

    account_info = get_account_health(account_id)

    blocks = {
        "type": "modal",
        "callback_id": "health_view",
        "title": {"type": "plain_text", "text": "AWS - Health Check"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Health check for *{account_name}*: ({account_id})",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""
*Cost:*

{account_info['cost']['last_month']['start_date']} - {account_info['cost']['last_month']['end_date']}: ${account_info['cost']['last_month']['amount']} USD
{account_info['cost']['current_month']['start_date']} - {account_info['cost']['current_month']['end_date']}: ${account_info['cost']['current_month']['amount']} USD
                        """,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""
*Security:*

{"✅" if account_info['security']['config'] == 0 else "❌"} Config ({account_info['security']['config']} issues)\n
{"✅" if account_info['security']['guardduty'] == 0 else "❌"} GuardDuty ({account_info['security']['guardduty']} issues)\n
{"✅" if account_info['security']['securityhub'] == 0 else "❌"} SecurityHub ({account_info['security']['securityhub']} issues)\n
                        """,
                },
            },
        ],
    }

    client.views_open(
        trigger_id=body["trigger_id"],
        view=blocks,
    )


def request_health_modal(client: WebClient, body):
    accounts = organizations.list_organization_accounts()
    options = [
        {
            "text": {
                "type": "plain_text",
                "text": f"{account['Name']} ({account['Id']})",
            },
            "value": account["Id"],
        }
        for account in accounts
    ]
    options.sort(key=lambda x: x["text"]["text"].lower())
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "aws_health_view",
            "title": {"type": "plain_text", "text": "AWS - Account health"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "block_id": "account",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select an account to view | Choisissez un compte à afficher",
                        },
                        "options": options,
                        "action_id": "account",
                    },
                    "label": {"type": "plain_text", "text": "Account", "emoji": True},
                }
            ],
        },
    )
