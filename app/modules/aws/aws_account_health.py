from typing import Any, Literal

import arrow
import structlog
from botocore.exceptions import BotoCoreError, ClientError
from slack_bolt import Ack
from slack_sdk import WebClient

from infrastructure.operations import OperationResult
from packages.aws_platform.adapters.config import ConfigAdapter, build_config_adapter
from packages.aws_platform.adapters.cost_explorer import CostExplorerAdapter, build_cost_explorer_adapter
from packages.aws_platform.adapters.guard_duty import GuardDutyAdapter, build_guard_duty_adapter
from packages.aws_platform.adapters.organizations import build_organizations_adapter
from packages.aws_platform.adapters.security_hub import SecurityHubAdapter, build_security_hub_adapter

logger = structlog.get_logger()

type SecuritySummary = int | Literal["not_enabled"] | None

GUARDDUTY_NOT_ENABLED: Literal["not_enabled"] = "not_enabled"

_HEALTH_CHECK_FAILED_MESSAGE = (
    "⚠️ Could not load the health check. Please try again later.\n"
    "Impossible de charger la vérification de santé. Veuillez réessayer plus tard."
)
_ACCOUNTS_LIST_FAILED_MESSAGE = (
    "⚠️ Could not list AWS accounts. Please try again later.\nImpossible de lister les comptes AWS. Veuillez réessayer plus tard."
)


def _failure_fields(result: OperationResult[Any]) -> dict[str, Any]:
    """Return the structured log fields describing a non-success adapter result."""
    return {"status": result.status.value, "error_code": result.error_code, "error": result.message}


def get_account_health(account_id: str) -> dict[str, Any]:
    """Collect last and current month cost plus Config, GuardDuty and Security Hub summaries.

    Each adapter is built once per check. A failed lookup leaves its field as None
    (rendered as unavailable) instead of failing the whole check.
    """
    current_month_start = arrow.utcnow().floor("month")
    cost_explorer_adapter = build_cost_explorer_adapter()
    config_adapter = build_config_adapter()
    guard_duty_adapter = build_guard_duty_adapter()
    security_hub_adapter = build_security_hub_adapter()

    return {
        "account_id": account_id,
        "cost": {
            "last_month": _month_cost(cost_explorer_adapter, account_id, current_month_start.shift(months=-1)),
            "current_month": _month_cost(cost_explorer_adapter, account_id, current_month_start),
        },
        "security": {
            "config": get_config_summary(config_adapter, account_id),
            "guardduty": get_guardduty_summary(guard_duty_adapter, account_id),
            "securityhub": get_securityhub_summary(security_hub_adapter, account_id),
        },
    }


def _month_cost(cost_explorer_adapter: CostExplorerAdapter, account_id: str, month_start: arrow.Arrow) -> dict[str, Any]:
    """Return one month's displayed range and spend.

    Cost Explorer's End is exclusive, so the query ends on the next month's first
    day while the displayed range ends on the month's last day.
    """
    next_month_start = month_start.shift(months=1)
    start_date = month_start.format("YYYY-MM-DD")
    return {
        "start_date": start_date,
        "end_date": next_month_start.shift(days=-1).format("YYYY-MM-DD"),
        "amount": get_account_spend(cost_explorer_adapter, account_id, start_date, next_month_start.format("YYYY-MM-DD")),
    }


def get_account_spend(cost_explorer_adapter: CostExplorerAdapter, account_id: str, start_date: str, end_date: str) -> str | None:
    """Return the account's formatted unblended cost from start_date to the exclusive end_date.

    Returns None when the lookup fails.
    """
    result = cost_explorer_adapter.get_cost_and_usage(
        time_period={"Start": start_date, "End": end_date},
        granularity="MONTHLY",
        metrics=["UnblendedCost"],
        filter_expression={"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [account_id]}},
        group_by=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
    )
    if not result.is_success:
        logger.error(
            "aws_health_cost_lookup_failed",
            account_id=account_id,
            start=start_date,
            end=end_date,
            **_failure_fields(result),
        )
        return None
    results_by_time = result.data or []
    groups = results_by_time[0].get("Groups", []) if results_by_time else []
    if not groups:
        return "0.00"
    return "{:0,.2f}".format(float(groups[0]["Metrics"]["UnblendedCost"]["Amount"]))


def get_config_summary(config_adapter: ConfigAdapter, account_id: str) -> int | None:
    """Return the number of non-compliant Config rules for the account, or None when the lookup fails."""
    config_name = "aws-controltower-GuardrailsComplianceAggregator"
    filters = {
        "AccountId": account_id,
        "ComplianceType": "NON_COMPLIANT",
    }
    result = config_adapter.describe_aggregate_compliance_by_config_rules(config_name, filters)
    if not result.is_success:
        logger.error("aws_health_config_lookup_failed", account_id=account_id, **_failure_fields(result))
        return None
    return len(result.data or [])


def get_guardduty_summary(guard_duty_adapter: GuardDutyAdapter, account_id: str) -> SecuritySummary:
    """Return the count of unarchived high-severity GuardDuty findings.

    Returns "not_enabled" when there is no detector and None when a lookup fails.
    """
    detectors_result = guard_duty_adapter.list_detectors()
    if not detectors_result.is_success:
        logger.error("aws_health_guardduty_detectors_failed", account_id=account_id, **_failure_fields(detectors_result))
        return None
    detector_ids = detectors_result.data or []
    if not detector_ids:
        logger.info("aws_health_guardduty_not_enabled", account_id=account_id)
        return GUARDDUTY_NOT_ENABLED

    finding_criteria = {
        "Criterion": {
            "accountId": {"Eq": [account_id]},
            "service.archived": {"Eq": ["false"]},
            "severity": {"Gte": 7},
        }
    }
    statistics_result = guard_duty_adapter.get_findings_statistics(detector_ids[0], finding_criteria)
    if not statistics_result.is_success:
        logger.error(
            "aws_health_guardduty_statistics_failed",
            account_id=account_id,
            detector_id=detector_ids[0],
            **_failure_fields(statistics_result),
        )
        return None
    return sum((statistics_result.data or {}).values())


def get_securityhub_summary(security_hub_adapter: SecurityHubAdapter, account_id: str) -> int | None:
    """Return the number of active failed high-severity Security Hub findings, or None when the lookup fails."""
    filters: dict[str, Any] = {
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
    result = security_hub_adapter.get_findings(filters)
    if not result.is_success:
        logger.error("aws_health_securityhub_lookup_failed", account_id=account_id, **_failure_fields(result))
        return None
    return len(result.data or [])


def get_ignored_security_hub_issues() -> list[dict[str, str]]:
    ignored_issues = [
        "IAM.6 Hardware MFA should be enabled for the root user",
        '1.14 Ensure hardware MFA is enabled for the "root" account',
    ]

    return [{"Value": t, "Comparison": "NOT_EQUALS"} for t in ignored_issues]


def _cost_line(period: dict[str, Any]) -> str:
    """Render one month's cost, or a warning when the lookup failed."""
    amount = "⚠️ unavailable" if period["amount"] is None else f"${period['amount']} USD"
    return f"{period['start_date']} - {period['end_date']}: {amount}"


def _security_line(label: str, summary: SecuritySummary) -> str:
    """Render one security service summary, warning when unavailable or not enabled."""
    if summary is None:
        return f"⚠️ {label} (unavailable)"
    if summary == GUARDDUTY_NOT_ENABLED:
        return f"⚠️ {label} (not enabled)"
    return f"{'✅' if summary == 0 else '❌'} {label} ({summary} issues)"


def _error_view(title: str, message: str) -> dict[str, Any]:
    """Return a closable modal showing a single error message and no submit button."""
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": title},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": message}}],
    }


def health_view_handler(ack: Ack, body: dict[str, Any], client: WebClient) -> None:
    ack()
    log = logger.bind()
    log.info(
        "aws_health_request_received",
    )
    account_id = body["view"]["state"]["values"]["account"]["account"]["selected_option"]["value"]

    account_name = body["view"]["state"]["values"]["account"]["account"]["selected_option"]["text"]["text"]

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
    )["view"]["id"]

    # AWS errors that are raised rather than classified (role assumption, unmapped codes) must
    # not leave the loading modal spinning; programmer errors still propagate.
    try:
        account_info = get_account_health(account_id)
    except ClientError, BotoCoreError:
        log.exception("aws_health_check_failed", account_id=account_id)
        client.views_update(view_id=view_id, view=_error_view("AWS - Health Check", _HEALTH_CHECK_FAILED_MESSAGE))
        return

    cost = account_info["cost"]
    security = account_info["security"]
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

{_cost_line(cost["last_month"])}
{_cost_line(cost["current_month"])}
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

{_security_line("Config", security["config"])}\n
{_security_line("GuardDuty", security["guardduty"])}\n
{_security_line("SecurityHub", security["securityhub"])}\n
                        """,
                },
            },
        ],
    }

    client.views_update(view_id=view_id, view=blocks)


def request_health_modal(client: WebClient, body: dict[str, Any]) -> None:
    trigger_id = body["trigger_id"]
    error_view = _error_view("AWS - Account health", _ACCOUNTS_LIST_FAILED_MESSAGE)
    try:
        accounts_result = build_organizations_adapter().list_organization_accounts()
    except ClientError, BotoCoreError:
        logger.exception("aws_health_accounts_list_failed")
        client.views_open(trigger_id=trigger_id, view=error_view)
        return
    if not accounts_result.is_success:
        logger.error("aws_health_accounts_list_failed", **_failure_fields(accounts_result))
        client.views_open(trigger_id=trigger_id, view=error_view)
        return

    options = [
        {
            "text": {
                "type": "plain_text",
                "text": f"{account['Name']} ({account['Id']})",
            },
            "value": account["Id"],
        }
        for account in accounts_result.data or []
    ]
    options.sort(key=lambda x: x["text"]["text"].lower())
    client.views_open(
        trigger_id=trigger_id,
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
