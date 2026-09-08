"""Settings contract for the shared Google Drive infrastructure capability."""

from infrastructure.drive.settings import DriveSettings, get_drive_settings


class TestDriveSettings:
    def test_drive_settings_defaults(self):
        settings = DriveSettings(_env_file=None)

        assert settings.provider == "google"

    def test_drive_settings_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("DRIVE_PROVIDER", "google")

        settings = DriveSettings()

        assert settings.provider == "google"


class TestDriveSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_drive_settings.cache_clear()

        assert get_drive_settings() is get_drive_settings()
