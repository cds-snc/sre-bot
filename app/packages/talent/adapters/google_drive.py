"""Talent-owned Drive adapter.

Only this module reaches the Drive provider boundary on behalf of modules/role/role.py.
"""

from typing import Any

import structlog

from infrastructure.configuration.integrations.google import get_google_workspace_settings
from infrastructure.drive.factory import get_drive_provider
from infrastructure.operations import OperationResult

logger = structlog.get_logger()
BOT_EMAIL = get_google_workspace_settings().SRE_BOT_EMAIL


def _log_failure(event: str, result: OperationResult[Any]) -> None:
    logger.warning(
        event,
        status=result.status.value,
        error_code=result.error_code,
        retry_after=result.retry_after,
    )


def create_role_folder(name: str, parent_folder_id: str) -> dict[str, Any] | None:
    result = get_drive_provider().create_folder(name, parent_folder_id, delegated_user_email=BOT_EMAIL)
    if not result.is_success:
        _log_failure("talent_drive_create_folder_failed", result)
        return None
    if result.data is None:
        return None
    return {"id": result.data.id, "name": result.data.name}


def copy_template_to_role_folder(
    template_id: str,
    name: str,
    templates_folder_id: str,
    destination_folder_id: str,
) -> str | None:
    result = get_drive_provider().copy_file_to_folder(
        template_id,
        name,
        templates_folder_id,
        destination_folder_id,
        delegated_user_email=BOT_EMAIL,
    )
    if not result.is_success:
        _log_failure("talent_drive_copy_template_failed", result)
        return None
    if result.data is None:
        return None
    return result.data.id
