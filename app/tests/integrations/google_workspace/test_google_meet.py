"""Test google_meet.py functions."""
git
from unittest.mock import patch
from integrations.google_workspace import google_meet


def test_create_google_meet_with_valid_title():
    """Test create_google_meet with a title."""
    title = "TestTitle"
    expected = "https://g.co/meet/TestTitle"
    assert google_meet.create_google_meet(title) == expected


@patch("integrations.google_workspace.google_meet.datetime")
def test_create_google_meet_without_title(date_time_mock):
    """Test create_google_meet without a title."""
    date_time_mock.now.return_value.strftime.return_value = "2021-06-01"
    expected = "https://g.co/meet/Meeting-Rencontre-2021-06-01"
    assert google_meet.create_google_meet() == expected


def test_create_google_meet_with_title_too_long():
    """Test create_google_meet with a title that is too long."""
    title = (
        "Testing-title-that-is-much-too-long-for-google-meet-and"
        "-it-should-be-truncated"
    )
    expected = (
        "https://g.co/meet/Testing-title-that-is-much-too-long-for-google-meet-and-it-s"
    )
    assert google_meet.create_google_meet(title) == expected


def test_create_google_meet_with_title_with_spaces():
    """Test create_google_meet with a title that has spaces."""
    title = "Testing title with spaces"
    expected = "https://g.co/meet/Testing-title-with-spaces"
    assert google_meet.create_google_meet(title) == expected


def test_create_google_meet_with_title_too_long_and_spaces():
    """Test create_google_meet with a title that is too long and has spaces."""
    title = (
        "Testing title that is much too long for google"
        " meet and it should be truncated"
    )
    expected = (
        "https://g.co/meet/Testing-title-that-is-much-too-"
        "long-for-google-meet-and-it-s"
    )
    assert google_meet.create_google_meet(title) == expected
    assert len(google_meet.create_google_meet(title)) == 78


def test_create_google_meet_with_title_special_characters():
    """Test create_google_meet with a title that has special characters."""
    title = "Testing title with special @!@#$!@# characters !@#$%^&*()"
    expected = "https://g.co/meet/Testing-title-with-special-characters"
    assert google_meet.create_google_meet(title) == expected


def test_create_google_meet_with_title_too_long_and_special_characters():
    """Test create_google_meet with a title that is too long
      and has special characters."""
    title = (
        "Testing title that is much too long for google"
        " meet and it should be truncated !@#$%^&*()"
    )
    expected = (
        "https://g.co/meet/Testing-title-that-is-much-too-"
        "long-for-google-meet-and-it-s"
    )
    assert google_meet.create_google_meet(title) == expected
    assert len(google_meet.create_google_meet(title)) == 78
