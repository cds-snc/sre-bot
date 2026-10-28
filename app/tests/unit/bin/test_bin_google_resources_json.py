"""Unit tests for the GOOGLE_RESOURCES extraction helper.

``google_resources`` is fed hand-written ``.env`` texts in the quoting forms an SSM blob line can take, so the
helper is pinned to read each the way python-dotenv and ``GoogleResourcesConfig`` do. No SSM access.
"""

import pytest

from bin.google_resources_json import google_resources

pytestmark = pytest.mark.unit

EXPECTED = {"inc": {"f": "folder-id"}, "tal": {"tech": "notes-id"}}


@pytest.mark.parametrize(
    "line",
    [
        'GOOGLE_RESOURCES = "{\\"inc\\": {\\"f\\": \\"folder-id\\"}, \\"tal\\": {\\"tech\\": \\"notes-id\\"}}"',
        """GOOGLE_RESOURCES = '{"inc": {"f": "folder-id"}, "tal": {"tech": "notes-id"}}'""",
        """GOOGLE_RESOURCES={"inc": {"f": "folder-id"}, "tal": {"tech": "notes-id"}}""",
    ],
    ids=["double-quoted-escaped", "single-quoted", "bare"],
)
def test_each_quoting_form_of_the_blob_line_parses_to_the_same_mapping(line: str) -> None:
    """Escaped double quotes, single quotes and a bare value all yield the mapping the app would read."""
    assert google_resources(f"OTHER = 'x'\n{line}\nLAST = 1\n") == EXPECTED


def test_the_line_is_found_when_the_second_blob_follows_the_first() -> None:
    """entry.sh appends the infrastructure blob; the helper reads the concatenation, as the app's .env is."""
    text = 'A = 1\nGOOGLE_RESOURCES = \'{"inc": {"f": "folder-id"}, "tal": {"tech": "notes-id"}}\'\n' + "B = 2\n"

    assert google_resources(text) == EXPECTED


def test_a_missing_line_is_an_error_that_names_the_line() -> None:
    with pytest.raises(ValueError, match="no GOOGLE_RESOURCES line"):
        google_resources("A = 1\n")


def test_invalid_json_is_an_error_that_never_contains_the_value() -> None:
    """A malformed value is reported by position only, so the error can be printed safely."""
    with pytest.raises(ValueError) as caught:
        google_resources("GOOGLE_RESOURCES = '{secret-id-123'\n")

    assert "secret-id-123" not in str(caught.value)
