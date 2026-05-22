"""Dev smoke tests for the Google Workspace directory provider.

Exercises every method exposed by the directory core service so that
returned canonical models can be visually inspected in logs.
"""

from typing import Any

import structlog
from structlog.stdlib import BoundLogger

from infrastructure.directory import get_directory_provider
from infrastructure.operations import OperationResult
from integrations.slack.parser import (
    Argument,
    ArgumentParsingError,
    ArgumentType,
    CommandArgumentParser,
)
from integrations.slack.models import CommandPayload

logger: BoundLogger = structlog.get_logger()

_GOOGLE_DEV_ARGUMENT_PARSER = CommandArgumentParser(
    [
        Argument(name="user_email", type=ArgumentType.EMAIL, required=True),
        Argument(name="group_email", type=ArgumentType.EMAIL, required=True),
    ]
)


def _log_failure(log: BoundLogger, result: OperationResult[Any]) -> None:
    log.error(
        "smoke_test_failed",
        status=result.status,
        message=result.message,
        error_code=result.error_code,
    )


def _parse_command_inputs(command_payload: CommandPayload | None) -> tuple[str, str]:
    """Parse user and group emails from the dev command payload text."""

    raw_text = command_payload.text if command_payload is not None else ""
    parsed = _GOOGLE_DEV_ARGUMENT_PARSER.parse(raw_text)
    return (
        str(parsed["user_email"]).strip().lower(),
        str(parsed["group_email"]).strip().lower(),
    )


def smoke_warmup() -> None:
    """Verify provider connectivity."""
    log = logger.bind(smoke="warmup")
    result = get_directory_provider().warmup()
    if result.is_success:
        log.info("warmup_ok")
    else:
        _log_failure(log, result)


def smoke_get_user(user_email: str) -> None:
    """Return a single canonical DirectoryUser."""
    log = logger.bind(smoke="get_user", user_email=user_email)
    result = get_directory_provider().get_user(user_email)
    if result.is_success and result.data is not None:
        user = result.data
        log.info(
            "get_user_ok",
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            provider_user_id=user.provider_user_id,
        )
    else:
        _log_failure(log, result)


def smoke_list_users() -> None:
    """Return a small page of canonical DirectoryUsers."""
    log = logger.bind(smoke="list_users")
    result = get_directory_provider().list_users(limit=3)
    if result.is_success and result.data is not None:
        users = result.data
        log.info("list_users_ok", count=len(users))
        for user in users:
            log.info("user", email=user.email, is_active=user.is_active)
    else:
        _log_failure(log, result)


def smoke_get_group_members(group_email: str) -> None:
    """Return the canonical member list for a group."""
    log = logger.bind(smoke="get_group_members", group_email=group_email)
    result = get_directory_provider().get_group_members(group_email)
    if result.is_success and result.data is not None:
        members = result.data
        log.info("get_group_members_ok", count=len(members))
        for member in members:
            log.info("member", email=member.email, role=member.role)
    else:
        _log_failure(log, result)


def smoke_check_membership(user_email: str, group_email: str) -> None:
    """Check whether the user is a member of the group."""
    log = logger.bind(
        smoke="check_membership",
        user_email=user_email,
        group_email=group_email,
    )
    result = get_directory_provider().check_membership(group_email, user_email)
    if result.is_success and result.data is not None:
        m = result.data
        log.info(
            "check_membership_ok",
            is_member=m.is_member,
            group_slug=m.group_slug,
        )
    else:
        _log_failure(log, result)


def smoke_list_groups(group_email: str) -> str | None:
    """Return the canonical group email for an exact group lookup."""
    log = logger.bind(smoke="list_groups", group_email=group_email)
    result = get_directory_provider().list_groups(query=f"email={group_email}")
    if result.is_success and result.data is not None:
        groups = result.data
        log.info("list_groups_ok", count=len(groups))
        if not groups:
            log.warning("group_not_found", requested_group_email=group_email)
            return None

        for group in groups:
            log.info(
                "group",
                email=group.group_email,
                slug=group.group_slug,
                name=group.name,
            )
        first_group = groups[0]
        return str(first_group.group_email)
    else:
        _log_failure(log, result)
        return None


def google_service_command(
    ack,
    client,
    body,
    respond,
    command_payload: CommandPayload | None = None,
) -> None:
    """Handle Google service command."""
    ack()
    try:
        user_email, group_email = _parse_command_inputs(command_payload)
    except ArgumentParsingError as exc:
        respond(
            "Usage: /sre dev google <user_email> <group_email>\n"
            f"Argument parsing error: {exc.message}"
        )
        return

    respond(
        "Running Google directory provider smoke tests for "
        f"{user_email} and {group_email}..."
    )
    smoke_warmup()
    smoke_get_user(user_email)
    smoke_list_users()
    resolved_group_email = smoke_list_groups(group_email)
    if resolved_group_email is not None:
        smoke_get_group_members(resolved_group_email)
        smoke_check_membership(user_email, resolved_group_email)
    else:
        respond(
            "Group lookup returned no exact match; skipped membership-related smoke tests."
        )
    respond("Google directory provider smoke tests completed.")
