"""Talent settings: the [talent] table of the configuration files.

The folder and template ids are non-public values (decisions/configuration.md): declared
empty in base.toml, set only from the environment as TALENT__<FIELD>.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only


class TalentSettings(ConfigurationSlice):
    """Where a new hiring role's folder is created and the templates it is filled from.

    Environment only (non-public values): TALENT__INTERNAL_FOLDER_ID, TALENT__TEMPLATES_FOLDER_ID,
    TALENT__SCORING_GUIDE_TEMPLATE_ID, TALENT__CORE_VALUES_INTERVIEW_NOTES_ID,
    TALENT__TECHNICAL_INTERVIEW_NOTES_ID, TALENT__INTAKE_FORM_TEMPLATE_ID,
    TALENT__PHONE_SCREEN_TEMPLATE_ID, TALENT__RECRUITMENT_FEEDBACK_TEMPLATE_ID,
    TALENT__PANELIST_GUIDEBOOK_TEMPLATE_ID.
    """

    model_config = SettingsConfigDict(toml_table_header=("talent",), env_prefix="TALENT__")

    internal_folder_id: str = env_only("Google Drive folder each role's folder is created in.", "codespaces", default="")
    templates_folder_id: str = env_only("Google Drive folder holding the hiring templates.", "codespaces", default="")
    scoring_guide_template_id: str = env_only("Google Docs template of the scoring guide.", "codespaces", default="")
    core_values_interview_notes_id: str = env_only(
        "Google Docs template of the core values interview notes.", "codespaces", default=""
    )
    technical_interview_notes_id: str = env_only(
        "Google Docs template of the technical interview notes.", "codespaces", default=""
    )
    intake_form_template_id: str = env_only("Google Docs template of the intake form.", "codespaces", default="")
    phone_screen_template_id: str = env_only("Google Docs template of the phone screen.", "codespaces", default="")
    recruitment_feedback_template_id: str = env_only(
        "Google Docs template of the recruitment feedback.", "codespaces", default=""
    )
    panelist_guidebook_template_id: str = env_only("Google Docs template of the panelist guidebook.", "codespaces", default="")


@lru_cache(maxsize=1)
def get_talent_settings() -> TalentSettings:
    """Return the process-wide [talent] slice."""
    return TalentSettings()
