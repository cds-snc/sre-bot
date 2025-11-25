"""Feature-level fixtures for i18n system tests.

Provides specific mocks and fixtures for locale resolution and translation scenarios.
"""

import pytest
import yaml

from infrastructure.i18n import YAMLTranslationLoader


@pytest.fixture
def temp_translations_dir(tmp_path):
    """Create temporary directory with sample YAML translation files.

    Returns a directory structure like:
    - incident.en-US.yml
    - incident.fr-FR.yml
    - role.en-US.yml
    - role.fr-FR.yml
    """
    # Create sample en-US translations
    en_us_incident = {
        "incident": {
            "created": "Incident {{incident_id}} created",
            "resolved": "Incident {{incident_id}} resolved",
            "invalid_status": "Invalid status: {{status}}",
        }
    }
    with open(tmp_path / "incident.en-US.yml", "w") as f:
        yaml.dump(en_us_incident, f)

    en_us_role = {
        "role": {
            "created": "Role {{role_name}} created",
            "deleted": "Role {{role_name}} deleted",
            "invalid_name": "Role names must start with 'role_'",
        }
    }
    with open(tmp_path / "role.en-US.yml", "w") as f:
        yaml.dump(en_us_role, f)

    # Create sample fr-FR translations
    fr_fr_incident = {
        "incident": {
            "created": "Incident {{incident_id}} créé",
            "resolved": "Incident {{incident_id}} résolu",
            "invalid_status": "Statut invalide: {{status}}",
        }
    }
    with open(tmp_path / "incident.fr-FR.yml", "w") as f:
        yaml.dump(fr_fr_incident, f)

    fr_fr_role = {
        "role": {
            "created": "Rôle {{role_name}} créé",
            "deleted": "Rôle {{role_name}} supprimé",
            "invalid_name": "Les noms de rôle doivent commencer par 'role_'",
        }
    }
    with open(tmp_path / "role.fr-FR.yml", "w") as f:
        yaml.dump(fr_fr_role, f)

    return tmp_path


@pytest.fixture
def yaml_loader(temp_translations_dir):
    """Create YAMLTranslationLoader for temporary translations directory."""
    return YAMLTranslationLoader(temp_translations_dir, use_cache=False)


@pytest.fixture
def yaml_loader_with_cache(temp_translations_dir):
    """Create YAMLTranslationLoader with caching enabled."""
    return YAMLTranslationLoader(temp_translations_dir, use_cache=True)


@pytest.fixture
def sample_translation_data():
    """Sample translation data for testing."""
    return {
        "incident": {
            "created": "Incident {{incident_id}} created",
            "resolved": "Incident {{incident_id}} resolved",
        },
        "role": {
            "created": "Role {{role_name}} created",
        },
    }


@pytest.fixture
def accept_language_headers():
    """Collection of Accept-Language headers for testing."""
    return {
        "simple_en": "en",
        "specific_en_us": "en-US",
        "with_quality": "en-US,en;q=0.9,fr;q=0.8",
        "multiple": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "wildcard": "en-US,en;q=0.9,*;q=0.8",
        "invalid_quality": "en;q=invalid,fr",
    }
