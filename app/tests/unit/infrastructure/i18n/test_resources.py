"""Tests for i18n resource registry and startup flow."""

from pathlib import Path

import pytest

from infrastructure.i18n.resources import I18nResourceRegistry, I18nResourceSpec


class TestI18nResourceSpec:
    """Test I18nResourceSpec dataclass validation."""

    def test_valid_spec_creation(self) -> None:
        """Test creating a valid resource spec."""
        spec = I18nResourceSpec(
            owner="packages.test",
            path="/test/locales",
            required=True,
            format="yaml",
            domain="test",
        )
        assert spec.owner == "packages.test"
        assert spec.path == "/test/locales"
        assert spec.required is True
        assert spec.format == "yaml"
        assert spec.domain == "test"

    def test_spec_with_defaults(self) -> None:
        """Test spec creation with default values."""
        spec = I18nResourceSpec(
            owner="packages.test",
            path="/test/locales",
        )
        assert spec.required is True
        assert spec.format == "yaml"
        assert spec.domain == "default"

    def test_spec_invalid_empty_owner(self) -> None:
        """Test that empty owner raises ValueError."""
        with pytest.raises(ValueError, match="owner must not be empty"):
            I18nResourceSpec(owner="", path="/test/locales")

    def test_spec_invalid_empty_path(self) -> None:
        """Test that empty path raises ValueError."""
        with pytest.raises(ValueError, match="path must not be empty"):
            I18nResourceSpec(owner="packages.test", path="")

    def test_spec_invalid_format(self) -> None:
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="format must be 'yaml' or 'json'"):
            I18nResourceSpec(
                owner="packages.test",
                path="/test/locales",
                format="toml",
            )


class TestI18nResourceRegistry:
    """Test I18nResourceRegistry collection and validation."""

    def test_registry_creation(self) -> None:
        """Test creating an empty registry."""
        registry = I18nResourceRegistry()
        assert registry.get_resource_count() == 0
        assert registry.list_specs() == []
        assert registry.list_paths() == []

    def test_registry_register_single(self) -> None:
        """Test registering a single resource."""
        registry = I18nResourceRegistry()
        spec = I18nResourceSpec(
            owner="packages.test",
            path="/test/locales",
        )
        registry.register(spec)

        assert registry.get_resource_count() == 1
        assert spec in registry.list_specs()
        assert "/test/locales" in registry.list_paths()

    def test_registry_register_multiple(self) -> None:
        """Test registering multiple resources."""
        registry = I18nResourceRegistry()
        spec1 = I18nResourceSpec(owner="pkg1", path="/path1")
        spec2 = I18nResourceSpec(owner="pkg2", path="/path2")

        registry.register(spec1)
        registry.register(spec2)

        assert registry.get_resource_count() == 2
        assert registry.list_paths() == ["/path1", "/path2"]

    def test_registry_deduplication(self) -> None:
        """Test that duplicate paths are deduplicated."""
        registry = I18nResourceRegistry()
        spec1 = I18nResourceSpec(owner="pkg1", path="/shared/locales")
        spec2 = I18nResourceSpec(owner="pkg2", path="/shared/locales")

        registry.register(spec1)
        registry.register(spec2)

        # Only the first should be registered
        assert registry.get_resource_count() == 1
        assert registry.list_specs() == [spec1]

    def test_registry_validate_paths_all_exist(self) -> None:
        """Test validation when all required paths exist."""
        registry = I18nResourceRegistry()

        # Use existing temp directories
        temp_dir1 = Path("/tmp")
        temp_dir2 = Path("/var")

        spec1 = I18nResourceSpec(
            owner="core",
            path=str(temp_dir1),
            required=True,
        )
        spec2 = I18nResourceSpec(
            owner="pkg",
            path=str(temp_dir2),
            required=True,
        )

        registry.register(spec1)
        registry.register(spec2)

        result = registry.validate_paths()
        assert result.is_success

    def test_registry_validate_paths_missing_required(self) -> None:
        """Test validation fails when required paths are missing."""
        registry = I18nResourceRegistry()
        spec = I18nResourceSpec(
            owner="pkg",
            path="/nonexistent/missing/path",
            required=True,
        )
        registry.register(spec)

        result = registry.validate_paths()
        assert not result.is_success
        assert "missing" in result.message.lower()

    def test_registry_validate_paths_missing_optional(self) -> None:
        """Test validation warns but passes for missing optional paths."""
        registry = I18nResourceRegistry()
        spec = I18nResourceSpec(
            owner="pkg",
            path="/nonexistent/missing/path",
            required=False,
        )
        registry.register(spec)

        result = registry.validate_paths()
        assert result.is_success


class TestI18nResourceRegistryIntegration:
    """Integration tests for i18n resource registry."""

    def test_registry_workflow(self) -> None:
        """Test complete registry workflow: register, list, validate."""
        registry = I18nResourceRegistry()

        # Register core resources
        core_spec = I18nResourceSpec(
            owner="core",
            path=str(Path("/tmp")),
            required=True,
            domain="core",
        )
        registry.register(core_spec)

        assert registry.get_resource_count() == 1
        assert len(registry.list_specs()) == 1
        assert len(registry.list_paths()) == 1

        # Validate
        validation = registry.validate_paths()
        assert validation.is_success

    def test_registry_collection_from_multiple_sources(self) -> None:
        """Test collecting specs from multiple simulated sources."""
        registry = I18nResourceRegistry()

        # Simulate multiple packages registering
        packages = [
            I18nResourceSpec(owner="pkg.a", path=str(Path("/tmp")), domain="a"),
            I18nResourceSpec(owner="pkg.b", path=str(Path("/var")), domain="b"),
        ]

        for spec in packages:
            registry.register(spec)

        assert registry.get_resource_count() == 2
        paths = registry.list_paths()
        assert str(Path("/tmp")) in paths
        assert str(Path("/var")) in paths
