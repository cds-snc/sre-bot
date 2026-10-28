"""The committed app/.env.example is exactly what bin/generate_env_example.py writes.

The file is read at test time and compared with the generator's output; a settings
change that adds, removes or redescribes an environment-only name fails here until
make env-example is run and the diff committed.
"""

import pytest

from bin import generate_env_example as generator

pytestmark = pytest.mark.unit


def test_committed_env_example_matches_the_settings_classes() -> None:
    entries, _ = generator.collect()

    # Compared as a bool, so a failure names the fix without printing the file.
    matches = generator.OUTPUT.read_text(encoding="utf-8") == generator.render(entries)

    assert matches, "app/.env.example differs from the settings classes: run make env-example"
