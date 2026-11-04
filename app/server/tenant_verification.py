"""Host tenant verifier: asks each vendor which tenant this instance's credentials act in.

Slack is verified with auth.test, and the returned ids are judged by
check_slack_tenant, the same rule the inbound tenant guard applies to every request
(decisions/workplace-systems.md rule 3). Other systems are unsupported until a
batch writer needs them, and fail closed.

The settings and the Web client are read per call, so building the verifier at
startup makes no vendor call.
"""

import structlog

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from integrations.slack.client import classify_slack_error, get_slack_web_client
from integrations.slack.settings import get_slack_settings
from server.slack.tenant_guard import check_slack_tenant

logger = structlog.get_logger(__name__)


class HostTenantVerifier:
    """TenantVerifier for the systems the host can verify: Slack today."""

    def verified_tenant(self, system: WorkplaceSystem) -> OperationResult[str]:
        """Return the tenant id the vendor confirmed, or why it could not be confirmed."""
        if system is WorkplaceSystem.SLACK:
            return _verify_slack()
        return OperationResult.permanent_error(f"No tenant verifier for {system.value}", ErrorCode.UNSUPPORTED_OPERATION)


def _verify_slack() -> OperationResult[str]:
    tenant = get_slack_settings().tenant
    if tenant is None:
        return OperationResult.permanent_error("Slack has no [slack.tenant] entry", ErrorCode.CONFIG_NOT_CONFIGURED)

    try:
        response = get_slack_web_client().auth_test()
    except Exception as exc:
        return _failed_call(exc)

    team_id = _vendor_id(response.get("team_id"))
    enterprise_id = _vendor_id(response.get("enterprise_id"))
    mismatch = check_slack_tenant(tenant, team_id=team_id, enterprise_id=enterprise_id)
    if mismatch is not None:
        logger.warning(
            "tenant_verification_mismatch",
            system=WorkplaceSystem.SLACK.value,
            expected_team_id=mismatch.expected_team_id,
            expected_enterprise_id=mismatch.expected_enterprise_id,
            received_team_id=mismatch.received_team_id,
            received_enterprise_id=mismatch.received_enterprise_id,
        )
        return OperationResult.error(
            OperationStatus.UNAUTHORIZED,
            (
                "Slack tenant mismatch: "
                f"expected team_id={mismatch.expected_team_id} enterprise_id={mismatch.expected_enterprise_id}; "
                f"received team_id={mismatch.received_team_id} enterprise_id={mismatch.received_enterprise_id}"
            ),
            ErrorCode.TENANT_MISMATCH,
        )
    return OperationResult.success(data=tenant.tenant_id)


def _failed_call(exc: Exception) -> OperationResult[str]:
    """Map a failed auth.test to its classified status, naming the Slack code or the exception type only."""
    try:
        status, code, retry_after = classify_slack_error(exc)
    except Exception:
        # Unclassified: the exception text may echo request detail, so only its type is kept.
        logger.warning("tenant_verification_failed", system=WorkplaceSystem.SLACK.value, error_type=type(exc).__name__)
        return OperationResult.permanent_error(f"Slack auth.test failed: {type(exc).__name__}", ErrorCode.TENANT_CHECK_FAILED)
    logger.warning("tenant_verification_failed", system=WorkplaceSystem.SLACK.value, slack_error=code)
    return OperationResult.error(
        status, f"Slack auth.test failed: {code}", ErrorCode.TENANT_CHECK_FAILED, retry_after=retry_after
    )


def _vendor_id(value: object) -> str | None:
    """Return a non-blank string id, else None: auth.test omits enterprise_id outside Enterprise orgs."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
