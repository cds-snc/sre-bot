"""Canonical typed models for spreadsheet provider results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SheetCell:
    """A cell returned by a spreadsheet provider."""

    formatted_value: str | None
    link: str | None = None
    provider: str | None = None
