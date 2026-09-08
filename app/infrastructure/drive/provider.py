"""Provider-agnostic contract for Drive operations."""

from typing import Protocol, runtime_checkable

from infrastructure.drive.models import DriveFile
from infrastructure.operations import OperationResult


@runtime_checkable
class DriveProvider(Protocol):
    """Shared operations for files and folders in a document drive."""

    def list_files(self, parent_id: str) -> OperationResult[list[DriveFile]]:
        """List non-folder files directly within a parent folder."""
        ...

    def list_folders(self, parent_id: str) -> OperationResult[list[DriveFile]]:
        """List folders directly within a parent folder."""
        ...

    def copy_file_to_folder(
        self,
        source_file_id: str,
        name: str,
        source_parent_id: str,
        destination_folder_id: str,
    ) -> OperationResult[DriveFile]:
        """Copy a file and move the copy into the requested destination folder."""
        ...
