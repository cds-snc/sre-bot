"""Unit tests for the email finder: the address shape, distinct results and the cap."""

import pytest

from capabilities.webhooks.domain.mentions import find_email_addresses

pytestmark = pytest.mark.unit


def test_addresses_are_found_in_order_with_lowercase_domains() -> None:
    text = "Owner: Jane.Doe@Example.CA, backup (ops+alerts@cds-snc.ca); see <it@example.com>."

    assert find_email_addresses(text, limit=10) == ("Jane.Doe@example.ca", "ops+alerts@cds-snc.ca", "it@example.com")


def test_each_address_is_returned_once() -> None:
    assert find_email_addresses("a@x.ca a@x.ca A@X.CA", limit=10) == ("a@x.ca", "A@x.ca")


def test_the_finder_stops_at_the_limit() -> None:
    text = " ".join(f"user{index}@example.com" for index in range(100))

    assert len(find_email_addresses(text, limit=10)) == 10


@pytest.mark.parametrize(
    "token",
    [
        "no-at-sign",
        "two@@example.com",
        "a@b@example.com",
        "@example.com",
        "user@",
        "user@localhost",
        "user@example.c",
        "user@-bad.com",
        "user@exa_mple.com",
        "user.@example.com",
        "us..er@example.com",
        "x" * 65 + "@example.com",
        "user@" + "a" * 64 + ".com",
        "usér@example.com",
        "user@example.123",
    ],
)
def test_a_token_that_is_not_an_address_is_ignored(token: str) -> None:
    assert find_email_addresses(token, limit=10) == ()
