"""Behavior tests for the instance language policy (decisions/languages.md).

ConfiguredLanguagePolicy is pure: it is built from the ordered shared list and
the supported set, so each test states both and asserts the languages returned.
Shared posts follow the instance list; a direct interaction follows the user's
language of choice, matched on its primary language subtag (RFC 4647 lookup),
else the first configured language; a request naming no language gets the
instance list.
"""

import pytest

from contracts.languages import LanguagePolicy
from contracts.workplace import WorkplaceSystem
from server.languages.policy import ConfiguredLanguagePolicy

pytestmark = pytest.mark.unit

SUPPORTED = ("en-US", "fr-FR")


def _policy(*shared: str) -> ConfiguredLanguagePolicy:
    return ConfiguredLanguagePolicy(shared=shared, supported=SUPPORTED)


def _shared(policy: ConfiguredLanguagePolicy) -> tuple[str, ...]:
    return policy.shared_languages(system=WorkplaceSystem.SLACK, tenant="T0SLACK", conversation_id="C0INCIDENT")


def test_the_policy_implements_the_contract() -> None:
    assert isinstance(_policy("en-US", "fr-FR"), LanguagePolicy)


@pytest.mark.parametrize("shared", [("en-US", "fr-FR"), ("fr-FR", "en-US"), ("en-US",), ("fr-FR",)])
def test_shared_posts_use_the_configured_languages_in_order(shared: tuple[str, ...]) -> None:
    """The order and the set are the instance's, whichever conversation is asked about."""
    assert _shared(_policy(*shared)) == shared


@pytest.mark.parametrize("locale", [None, "", "  "])
def test_a_request_naming_no_language_is_answered_in_the_instance_languages(locale: str | None) -> None:
    assert _policy("fr-FR", "en-US").reply_languages(locale) == ("fr-FR", "en-US")


@pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
def test_a_supported_language_is_answered_in_that_language(locale: str) -> None:
    assert _policy("en-US", "fr-FR").reply_languages(locale) == (locale,)


def test_a_user_choice_outside_the_instance_list_is_still_honoured() -> None:
    """Direct interactions follow the user's choice, not the instance list (D3): a French user of an English-only instance."""
    assert _policy("en-US").reply_languages("fr-FR") == ("fr-FR",)


@pytest.mark.parametrize(("locale", "expected"), [("en-GB", "en-US"), ("en-CA", "en-US"), ("fr-CA", "fr-FR"), ("FR-ca", "fr-FR")])
def test_a_regional_variant_is_matched_on_its_language(locale: str, expected: str) -> None:
    assert _policy("en-US", "fr-FR").reply_languages(locale) == (expected,)


@pytest.mark.parametrize("shared", [("en-US", "fr-FR"), ("fr-FR", "en-US")])
def test_an_unsupported_language_falls_back_to_the_first_configured(shared: tuple[str, ...]) -> None:
    """Spanish has no catalogue: the user gets the instance's first language, never a raw key."""
    assert _policy(*shared).reply_languages("es-ES") == (shared[0],)
