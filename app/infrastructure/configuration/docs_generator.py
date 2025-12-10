"""Generate documentation from Pydantic settings classes."""

import inspect
from pathlib import Path
from typing import Any, Type

from pydantic_settings import BaseSettings


def generate_settings_docs(
    settings_class: Type[BaseSettings],
    output_file: Path,
    title: str = "Configuration Reference",
) -> None:
    """Generate Markdown documentation for a settings class.

    Args:
        settings_class: The Settings class to document
        output_file: Output Markdown file path
        title: Document title
    """
    lines = [
        f"# {title}\n",
        "_Auto-generated from Pydantic settings classes_\n",
        f"**Generated:** `{Path(__file__).name}`\n",
        "---\n",
    ]

    # Get all settings sections
    settings_instance = settings_class()

    for field_name, field_info in settings_class.model_fields.items():
        field_value = getattr(settings_instance, field_name, None)

        # Skip primitive fields (handled separately)
        if not isinstance(field_value, BaseSettings):
            continue

        # Generate section for this settings class
        section_lines = _generate_section_docs(field_name, type(field_value))
        lines.extend(section_lines)

    # Write to file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines))
    print(f"✅ Documentation generated: {output_file}")


def _generate_section_docs(
    section_name: str,
    settings_class: Type[BaseSettings],
) -> list[str]:
    """Generate documentation for a single settings section.

    Args:
        section_name: Name of the settings section (e.g., "slack")
        settings_class: The settings class type

    Returns:
        List of markdown lines
    """
    lines = [
        f"\n## {section_name.replace('_', ' ').title()}\n",
        f"**Class:** `{settings_class.__name__}`\n",
    ]

    # Add docstring if available
    if settings_class.__doc__:
        docstring = inspect.cleandoc(settings_class.__doc__)
        lines.append(f"{docstring}\n")

    # Generate field table
    lines.extend(
        [
            "| Field | Type | Default | Environment Variable | Description |",
            "|-------|------|---------|---------------------|-------------|",
        ]
    )

    for field_name, field_info in settings_class.model_fields.items():
        field_type = _format_type(field_info.annotation)
        default_value = _format_default(field_info.default)
        env_var = field_info.alias or field_name.upper()
        description = field_info.description or "_No description_"

        lines.append(
            f"| `{field_name}` | `{field_type}` | `{default_value}` | `{env_var}` | {description} |"
        )

    lines.append("")  # Blank line between sections
    return lines


def _format_type(annotation: Any) -> str:
    """Format type annotation for display."""
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _format_default(default: Any) -> str:
    """Format default value for display."""
    if default is None:
        return "_None_"
    if isinstance(default, str):
        return f'"{default}"' if default else '""'
    if isinstance(default, (list, dict)):
        return "[]" if not default else str(default)
    return str(default)


if __name__ == "__main__":
    import sys
    from pathlib import Path as PathLib

    # Add parent directory to path to allow imports
    app_dir = PathLib(__file__).parent.parent.parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    from infrastructure.configuration.settings import Settings

    output = PathLib(__file__).parent.parent.parent.parent / "docs" / "CONFIGURATION.md"
    generate_settings_docs(
        settings_class=Settings,
        output_file=output,
        title="SRE Bot Configuration Reference",
    )
