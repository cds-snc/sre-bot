"""Incident-owned Drive adapter.

Generic file and folder operations route through the configured DriveProvider.
Incident-specific metadata and template health checks remain temporary pass-throughs
to the legacy Google Drive integration until that integration is retired.
"""

from types import ModuleType
from typing import Any, cast

import structlog

from infrastructure.configuration.integrations.google import get_google_resources_config
from infrastructure.drive.factory import get_drive_provider
from infrastructure.drive.models import DriveFile
from infrastructure.operations import OperationResult
from integrations.google_workspace import google_drive as legacy_google_drive

logger = structlog.get_logger()
INCIDENT_TEMPLATE = get_google_resources_config().incident_template_id


def get_legacy_google_drive() -> ModuleType:
    return legacy_google_drive


def _to_dict(file: DriveFile) -> dict[str, Any]:
    return {"id": file.id, "name": file.name}


def _log_failure(event: str, result: OperationResult[Any]) -> None:
    logger.warning(
        event,
        status=result.status.value,
        error_code=result.error_code,
        retry_after=result.retry_after,
    )


def list_folder_files(parent_folder_id: str) -> list[dict[str, Any]]:
    result = get_drive_provider().list_files(parent_folder_id)
    if not result.is_success:
        _log_failure("incident_drive_list_files_failed", result)
        return []
    return [_to_dict(file) for file in result.data or []]


def list_child_folders(parent_folder_id: str) -> list[dict[str, Any]]:
    result = get_drive_provider().list_folders(parent_folder_id)
    if not result.is_success:
        _log_failure("incident_drive_list_folders_failed", result)
        return []
    return [_to_dict(file) for file in result.data or [] if file.name and "Templates" not in file.name]


def create_folder(name: str, parent_folder_id: str) -> dict[str, Any] | None:
    result = get_drive_provider().create_folder(name, parent_folder_id)
    if not result.is_success:
        _log_failure("incident_drive_create_folder_failed", result)
        return None
    if result.data is None:
        return None
    return _to_dict(result.data)


def create_document_from_template(name: str, parent_folder_id: str, template_id: str) -> dict[str, Any] | None:
    result = get_drive_provider().create_file_from_template(name, parent_folder_id, template_id)
    if not result.is_success:
        _log_failure("incident_drive_create_document_failed", result)
        return None
    if result.data is None:
        return None
    return _to_dict(result.data)


def find_document_by_channel_name(channel_name: str) -> dict[str, Any] | None:
    result = get_drive_provider().find_files_by_name(channel_name)
    if not result.is_success:
        _log_failure("incident_drive_find_document_failed", result)
        return None

    matches = result.data or []
    if not matches:
        return None

    document = matches[0]
    metadata = get_legacy_google_drive().list_metadata(document.id, fields="id, name, appProperties")
    return {"id": document.id, "appProperties": metadata.get("appProperties", {})}


def add_metadata(file_id: str, key: str, value: str) -> dict[str, Any]:
    return cast("dict[str, Any]", get_legacy_google_drive().add_metadata(file_id, key, value))


def delete_metadata(file_id: str, key: str) -> dict[str, Any]:
    return cast("dict[str, Any]", get_legacy_google_drive().delete_metadata(file_id, key))


def get_metadata(file_id: str, fields: str | None = None) -> dict[str, Any]:
    return cast("dict[str, Any]", get_legacy_google_drive().list_metadata(file_id, fields=fields))


def incident_drive_healthcheck() -> bool:
    healthy = False
    try:
        metadata = get_metadata(INCIDENT_TEMPLATE)
        if metadata is not None:
            healthy = "id" in metadata
        logger.info(
            "google_drive_healthcheck_success",
            status="healthy" if healthy else "unhealthy",
        )
    except Exception as error:
        logger.exception("google_drive_healthcheck_failed", error=str(error))

    return healthy
