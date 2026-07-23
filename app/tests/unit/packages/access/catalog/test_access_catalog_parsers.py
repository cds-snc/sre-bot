"""Unit tests for packages.access.catalog.parsers."""

from packages.access.catalog.parsers import (
    AwsCatalogSlugParser,
    FallbackCatalogSlugParser,
)

# ---------------------------------------------------------------------------
# Helpers / Factories
# ---------------------------------------------------------------------------


def make_aws_parser(known_envs=None):
    """Factory for AwsCatalogSlugParser with optional known_envs."""
    return AwsCatalogSlugParser(known_envs=set(known_envs or ["dev", "staging", "prod"]))


# ---------------------------------------------------------------------------
# FallbackCatalogSlugParser
# ---------------------------------------------------------------------------


def test_fallback_should_return_unparsed_with_raw_token():
    # Arrange
    parser = FallbackCatalogSlugParser()

    # Act
    result = parser.parse("anything-goes-here")

    # Assert
    assert result.raw == "anything-goes-here"
    assert result.parsed is False
    assert result.product == ""
    assert result.env is None
    assert result.role == ""


def test_fallback_should_handle_empty_token():
    # Arrange
    parser = FallbackCatalogSlugParser()

    # Act
    result = parser.parse("")

    # Assert
    assert result.raw == ""
    assert result.parsed is False


# ---------------------------------------------------------------------------
# AwsCatalogSlugParser — happy paths
# ---------------------------------------------------------------------------


def test_aws_parser_should_parse_product_env_role_token():
    # Arrange
    parser = make_aws_parser()

    # Act
    result = parser.parse("platform-prod-admin")

    # Assert
    assert result.parsed is True
    assert result.product == "platform"
    assert result.env == "prod"
    assert result.role == "admin"
    assert result.service is None
    assert result.resource is None


def test_aws_parser_should_parse_product_env_role_service():
    # Arrange
    parser = make_aws_parser()

    # Act
    result = parser.parse("platform-staging-readonly-ec2")

    # Assert
    assert result.parsed is True
    assert result.product == "platform"
    assert result.env == "staging"
    assert result.role == "readonly"
    assert result.service == "ec2"
    assert result.resource is None


def test_aws_parser_should_parse_product_env_role_service_resource():
    # Arrange
    parser = make_aws_parser()

    # Act
    result = parser.parse("platform-prod-admin-s3-bucket")

    # Assert
    assert result.parsed is True
    assert result.product == "platform"
    assert result.env == "prod"
    assert result.role == "admin"
    assert result.service == "s3"
    assert result.resource == "bucket"


def test_aws_parser_should_parse_hyphenated_product_with_env():
    # Arrange  — product name contains a hyphen (e.g. "data-platform")
    parser = make_aws_parser()

    # Act
    result = parser.parse("data-platform-dev-engineer")

    # Assert — "dev" is env_index=2, product = "data-platform"
    assert result.parsed is True
    assert result.product == "data-platform"
    assert result.env == "dev"
    assert result.role == "engineer"


def test_aws_parser_should_parse_product_role_when_no_env_segment():
    # Arrange  — token has no env qualifier
    parser = make_aws_parser()

    # Act
    result = parser.parse("platform-admin")

    # Assert  — product=platform, env=None, role=admin
    assert result.parsed is True
    assert result.product == "platform"
    assert result.env is None
    assert result.role == "admin"


def test_aws_parser_should_normalise_token_to_lowercase():
    # Arrange
    parser = make_aws_parser()

    # Act
    result = parser.parse("Platform-PROD-Admin")

    # Assert
    assert result.parsed is True
    assert result.product == "platform"
    assert result.env == "prod"
    assert result.role == "admin"


# ---------------------------------------------------------------------------
# AwsCatalogSlugParser — edge / failure cases
# ---------------------------------------------------------------------------


def test_aws_parser_should_return_unparsed_for_single_segment_token():
    # Arrange
    parser = make_aws_parser()

    # Act
    result = parser.parse("onlyone")

    # Assert
    assert result.parsed is False
    assert result.raw == "onlyone"


def test_aws_parser_should_return_unparsed_when_env_found_at_index_zero():
    # Arrange  — token starts with an env segment; product is missing
    parser = make_aws_parser()

    # Act
    result = parser.parse("prod-admin")

    # Assert  — "prod" at index 0, env_index condition requires >= 1
    # Falls through to no-env branch: product="prod", role="admin"
    assert result.parsed is True
    assert result.product == "prod"
    assert result.env is None
    assert result.role == "admin"


def test_aws_parser_should_be_case_insensitive_for_known_envs():
    # Arrange  — known_envs stored in lowercase; token env is cased
    parser = AwsCatalogSlugParser(known_envs={"PROD", "dev"})

    # Act
    result = parser.parse("platform-PROD-admin")

    # Assert  — normalisation ensures match
    assert result.parsed is True
    assert result.env == "prod"


def test_aws_parser_should_handle_empty_known_envs():
    # Arrange  — no envs configured → always falls back to Product-Role
    parser = AwsCatalogSlugParser(known_envs=set())

    # Act
    result = parser.parse("platform-prod-admin")

    # Assert  — "prod" is treated as role, "admin" as service
    assert result.parsed is True
    assert result.product == "platform"
    assert result.env is None
    assert result.role == "prod"
    assert result.service == "admin"
