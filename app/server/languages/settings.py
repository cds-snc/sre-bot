"""Instance languages settings slice, read from the [languages] table.

``shared`` is the ordered list of languages a shared or generic message uses
(decisions/languages.md). The organisation sets it for its jurisdiction: under
the TBS Directive on Official Languages for Communications and Services 6.1.1,
French comes first when the issuing office is in Quebec; an adopter may use
one language. Each entry must be a language the app supports (has catalogues
for), checked statically in the configuration phase (decisions/configuration.md).
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice
from infrastructure.i18n.models import Locale

SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(locale.value for locale in Locale)


class LanguageSettings(ConfigurationSlice):
    """The instance's languages for shared and generic messages."""

    model_config = SettingsConfigDict(toml_table_header=("languages",), env_prefix="LANGUAGES__")

    shared: tuple[str, ...] = Field(
        default=("en-US", "fr-FR"),
        description="Languages of shared and generic messages, in display order; each one the app supports.",
    )

    @field_validator("shared")
    @classmethod
    def _supported_once_each(cls, shared: tuple[str, ...]) -> tuple[str, ...]:
        if not shared:
            raise ValueError("needs at least one language")
        for language in shared:
            if language not in SUPPORTED_LANGUAGES:
                raise ValueError(f"{language} is not supported; supported: {', '.join(SUPPORTED_LANGUAGES)}")
        if len(set(shared)) != len(shared):
            raise ValueError("lists a language more than once")
        return shared


@lru_cache(maxsize=1)
def get_language_settings() -> LanguageSettings:
    """Return the process-wide `LanguageSettings` singleton."""

    return LanguageSettings()
