"""Integration test for geolocate package i18n resource registration hook."""

from pathlib import Path

from infrastructure.i18n.resources import I18nResourceRegistry, I18nResourceSpec


def test_geolocate_package_can_register_i18n_resources() -> None:
    """Test that geolocate package can register its i18n resources via hook."""
    # Simulate what happens during feature discovery
    registry = I18nResourceRegistry()

    # This is what geolocate's register_i18n_resources hookimpl does
    package_root = Path(__file__).resolve().parents[4] / "packages" / "geolocate"
    locales_path = package_root / "locales"

    spec = I18nResourceSpec(
        owner="packages.geolocate",
        path=str(locales_path),
        required=False,
        format="yaml",
        domain="geolocate",
    )
    registry.register(spec)

    # Validate resource was registered
    assert registry.get_resource_count() == 1
    assert locales_path.name in str(registry.list_paths()[0])
    assert registry.list_specs()[0].owner == "packages.geolocate"


def test_geolocate_locales_directory_exists() -> None:
    """Test that geolocate package has co-located locales directory."""
    package_root = Path(__file__).resolve().parents[4] / "packages" / "geolocate"
    locales_path = package_root / "locales"

    assert locales_path.exists(), f"geolocate locales directory missing: {locales_path}"
    assert locales_path.is_dir()

    # Verify translation files exist
    en_file = locales_path / "geolocate.en-US.yml"
    fr_file = locales_path / "geolocate.fr-FR.yml"

    assert en_file.exists(), f"Missing English translation: {en_file}"
    assert fr_file.exists(), f"Missing French translation: {fr_file}"


def test_geolocate_resource_validation_passes() -> None:
    """Test that geolocate's registered resource passes path validation."""
    registry = I18nResourceRegistry()

    package_root = Path(__file__).resolve().parents[4] / "packages" / "geolocate"
    locales_path = package_root / "locales"

    spec = I18nResourceSpec(
        owner="packages.geolocate",
        path=str(locales_path),
        required=False,
        format="yaml",
        domain="geolocate",
    )
    registry.register(spec)

    # Validate paths
    result = registry.validate_paths()
    assert result.is_success, f"Path validation failed: {result.message}"
