"""Provider-agnostic contract for Drive operations."""

from typing import Protocol, runtime_checkable

from infrastructure.drive.models import DriveFile
from infrastructure.operations import OperationResult


@runtime_checkable
class DriveProvider(Protocol):
    """Shared operations for files and folders in a document drive."""

    def warmup(self) -> OperationResult[None]:
        """Validate connectivity and credentials with a cheap API call."""
        ...

    def health_check(self) -> OperationResult[None]:
        """Return a fast local liveness result without a remote API call."""
        ...

    def create_folder(
        self, name: str, parent_folder_id: str, *, fields: str | None = None, delegated_user_email: str | None = None
    ) -> OperationResult[DriveFile]: ...

    def list_folders(
        self,
        parent_folder_id: str,
        query: str | None = None,
        *,
        fields: str | None = None,
        delegated_user_email: str | None = None,
    ) -> OperationResult[list[DriveFile]]:
        """List folders directly within a parent folder."""
        ...

    def list_files(
        self, parent_folder_id: str, *, fields: str | None = None, delegated_user_email: str | None = None
    ) -> OperationResult[list[DriveFile]]:
        """List non-folder files directly within a parent folder."""
        ...

    def find_files_by_name(
        self,
        name: str,
        parent_folder_id: str | None = None,
        *,
        fields: str | None = None,
        delegated_user_email: str | None = None,
    ) -> OperationResult[list[DriveFile]]: ...

    def create_file_from_template(
        self,
        name: str,
        parent_folder_id: str,
        template_id: str,
        *,
        fields: str | None = None,
        delegated_user_email: str | None = None,
    ) -> OperationResult[DriveFile]: ...

    def copy_file_to_folder(
        self,
        file_id: str,
        name: str,
        source_parent_id: str,
        destination_folder_id: str,
        *,
        delegated_user_email: str | None = None,
    ) -> OperationResult[DriveFile]:
        """Copy a file and move the copy into the requested destination folder."""
        ...
