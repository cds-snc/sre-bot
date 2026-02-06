import structlog
import arrow
from slack_bolt import Ack
from slack_sdk import WebClient

from integrations.aws import (
    organizations,
    security_hub,
    guard_duty,
    config,
    cost_explorer,
)

logger = structlog.get_logger()


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
    time_period = {"Start": start_date, "End": end_date}
    granularity = "MONTHLY"
    metrics = ["UnblendedCost"]
    group_by = [{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}]
    filter = {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}}
    response = cost_explorer.get_cost_and_usage(
        time_period, granularity, metrics, filter, group_by
    )
    if (
        "Groups" in response["ResultsByTime"][0]
        and len(response["ResultsByTime"][0]["Groups"]) > 0
    ):
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
    config_name = "aws-controltower-GuardrailsComplianceAggregator"
    filters = {
        "AccountId": account_id,
        "ComplianceType": "NON_COMPLIANT",
    }
    return len(
        config.describe_aggregate_compliance_by_config_rules(config_name, filters)
    )


def get_guardduty_summary(account_id):
    detector_ids = guard_duty.list_detectors()
    finding_criteria = {
        "Criterion": {
            "accountId": {"Eq": [account_id]},
            "service.archived": {"Eq": ["false", "false"]},
            "severity": {"Gte": 7},
        }
    }
    response = guard_duty.get_findings_statistics(detector_ids[0], finding_criteria)
    return sum(response["FindingStatistics"]["CountBySeverity"].values())


def get_securityhub_summary(account_id):
    filters = {
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
    response = security_hub.get_findings(filters)
    issues = 0
    if response:
        for res in response:
            issues += len(res["Findings"])
    return issues


def get_ignored_security_hub_issues():
    ignored_issues = [
        "IAM.6 Hardware MFA should be enabled for the root user",
        '1.14 Ensure hardware MFA is enabled for the "root" account',
    ]

    return list(map(lambda t: {"Value": t, "Comparison": "NOT_EQUALS"}, ignored_issues))


def health_view_handler(ack: Ack, body, client: WebClient):
    ack()
    log = logger.bind()
    log.info(
        "aws_health_request_received",
    )
    account_id = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["value"]

    account_name = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["text"]["text"]

    temporary_blocks = {
        "type": "modal",
        "callback_id": "health_view",
        "title": {"type": "plain_text", "text": "AWS - Health Check"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Health check for *{account_name}*:",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": """
:beach-ball: Loading data...""",
                },
            },
        ],
    }

    view_id = client.views_open(
        trigger_id=body["trigger_id"],
        view=temporary_blocks,
    )[
        "view"
    ]["id"]

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
                    "text": f"Health check for *{account_name}*:",
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

    client.views_update(view_id=view_id, view=blocks)


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
