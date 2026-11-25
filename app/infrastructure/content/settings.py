"""Provisioned-content settings slice, read from the [content] table.

``root`` is where the deployment's content files live; the two limits are the instance
ceilings every kind is held to (a kind may set a lower one, never a higher one).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class ContentSettings(ConfigurationSlice):
    """Where provisioned content is read from and the ceilings it is held to."""

    model_config = SettingsConfigDict(toml_table_header=("content",), env_prefix="CONTENT__")

    root: Path = Field(
        default=Path("content"),
        description="Directory holding <owner>/<kind>/ content folders; relative paths resolve against the app directory.",
    )
    max_file_bytes: int = Field(default=16_384, gt=0, description="Largest content file the loader reads, in bytes.")
    max_items_per_kind: int = Field(default=200, gt=0, description="Most items one kind may have.")

    def resolved_root(self, app_directory: Path) -> Path:
        """Return the root as an absolute path, resolving a relative one against ``app_directory``."""
        return self.root if self.root.is_absolute() else app_directory / self.root


@lru_cache(maxsize=1)
def get_content_settings() -> ContentSettings:
    """Return the process-wide [content] slice."""
    return ContentSettings()
