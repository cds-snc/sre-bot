"""Unit tests for groups provider base classes and contracts.

Tests cover:
- OperationStatus enum
- OperationResult class and factory methods
- ProviderCapabilities dataclass
- Provider capability checking functions
"""

import pytest
from modules.groups.providers.base import (
    OperationStatus,
    OperationResult,
    ProviderCapabilities,
    provider_supports,
    provider_provides_role_info,
)


# ============================================================================
# OperationStatus Tests
# ============================================================================


@pytest.mark.unit
class TestOperationStatus:
    """Test OperationStatus enum."""

    def test_operation_status_success(self):
        """Test SUCCESS status value."""
        assert OperationStatus.SUCCESS.value == "success"

    def test_operation_status_transient_error(self):
        """Test TRANSIENT_ERROR status value."""
        assert OperationStatus.TRANSIENT_ERROR.value == "transient_error"

    def test_operation_status_permanent_error(self):
        """Test PERMANENT_ERROR status value."""
        assert OperationStatus.PERMANENT_ERROR.value == "permanent_error"

    def test_operation_status_unauthorized(self):
        """Test UNAUTHORIZED status value."""
        assert OperationStatus.UNAUTHORIZED.value == "unauthorized"

    def test_operation_status_not_found(self):
        """Test NOT_FOUND status value."""
        assert OperationStatus.NOT_FOUND.value == "not_found"

    def test_operation_status_enum_membership(self):
        """Test all enum members are accessible."""
        statuses = [
            OperationStatus.SUCCESS,
            OperationStatus.TRANSIENT_ERROR,
            OperationStatus.PERMANENT_ERROR,
            OperationStatus.UNAUTHORIZED,
            OperationStatus.NOT_FOUND,
        ]
        assert len(statuses) == 5


# ============================================================================
# OperationResult Tests
# ============================================================================


@pytest.mark.unit
class TestOperationResultBasics:
    """Test OperationResult dataclass basics."""

    def test_operation_result_construction(self):
        """Test basic construction."""
        result = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Operation completed",
        )
        assert result.status == OperationStatus.SUCCESS
        assert result.message == "Operation completed"

    def test_operation_result_with_data(self):
        """Test construction with data."""
        data = {"key": "value"}
        result = OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data=data,
        )
        assert result.data == data

    def test_operation_result_with_error_code(self):
        """Test construction with error code."""
        result = OperationResult(
            status=OperationStatus.PERMANENT_ERROR,
            message="Error",
            error_code="NOT_FOUND",
        )
        assert result.error_code == "NOT_FOUND"

    def test_operation_result_with_retry_after(self):
        """Test construction with retry_after."""
        result = OperationResult(
            status=OperationStatus.TRANSIENT_ERROR,
            message="Rate limited",
            retry_after=60,
        )
        assert result.retry_after == 60

    def test_operation_result_defaults(self):
        """Test default values."""
        result = OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
        )
        assert result.data is None
        assert result.error_code is None
        assert result.retry_after is None


@pytest.mark.unit
class TestOperationResultFactories:
    """Test OperationResult factory methods."""

    def test_success_factory_minimal(self):
        """Test success factory with minimal parameters."""
        result = OperationResult.success()
        assert result.status == OperationStatus.SUCCESS
        assert result.message == "ok"
        assert result.data is None

    def test_success_factory_with_data(self):
        """Test success factory with data."""
        data = {"id": "123"}
        result = OperationResult.success(data=data, message="Created")
        assert result.status == OperationStatus.SUCCESS
        assert result.data == data
        assert result.message == "Created"

    def test_error_factory_minimal(self):
        """Test error factory with minimal parameters."""
        result = OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            "Not found",
        )
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.message == "Not found"

    def test_error_factory_with_error_code(self):
        """Test error factory with error code."""
        result = OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            "Not found",
            error_code="404",
        )
        assert result.error_code == "404"

    def test_error_factory_with_retry_after(self):
        """Test error factory with retry_after."""
        result = OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            "Rate limited",
            retry_after=30,
        )
        assert result.retry_after == 30

    def test_transient_error_factory(self):
        """Test transient_error convenience factory."""
        result = OperationResult.transient_error("Timeout", error_code="TIMEOUT")
        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.message == "Timeout"
        assert result.error_code == "TIMEOUT"

    def test_permanent_error_factory(self):
        """Test permanent_error convenience factory."""
        result = OperationResult.permanent_error(
            "Invalid input", error_code="VALIDATION_ERROR"
        )
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.message == "Invalid input"
        assert result.error_code == "VALIDATION_ERROR"


# ============================================================================
# ProviderCapabilities Tests
# ============================================================================


@pytest.mark.unit
class TestProviderCapabilities:
    """Test ProviderCapabilities dataclass."""

    def test_capabilities_defaults(self):
        """Test default capability values."""
        caps = ProviderCapabilities()
        assert caps.supports_user_creation is False
        assert caps.supports_user_deletion is False
        assert caps.supports_group_creation is False
        assert caps.supports_group_deletion is False
        assert caps.supports_member_management is True
        assert caps.is_primary is False
        assert caps.provides_role_info is False
        assert caps.supports_batch_operations is False
        assert caps.max_batch_size == 1

    def test_capabilities_custom_values(self):
        """Test capabilities with custom values."""
        caps = ProviderCapabilities(
            supports_user_creation=True,
            is_primary=True,
            supports_batch_operations=True,
            max_batch_size=100,
        )
        assert caps.supports_user_creation is True
        assert caps.is_primary is True
        assert caps.supports_batch_operations is True
        assert caps.max_batch_size == 100

    def test_capabilities_dataclass_fields(self):
        """Test that capabilities has expected fields."""
        caps = ProviderCapabilities()
        assert hasattr(caps, "supports_user_creation")
        assert hasattr(caps, "supports_user_deletion")
        assert hasattr(caps, "supports_group_creation")
        assert hasattr(caps, "supports_group_deletion")
        assert hasattr(caps, "supports_member_management")
        assert hasattr(caps, "is_primary")
        assert hasattr(caps, "provides_role_info")
        assert hasattr(caps, "supports_batch_operations")
        assert hasattr(caps, "max_batch_size")

    def test_capabilities_from_config_empty(self, monkeypatch):
        """Test from_config with no settings."""
        monkeypatch.setattr(
            "modules.groups.providers.base.settings",
            type("obj", (object,), {})(),
        )
        caps = ProviderCapabilities.from_config("test_provider")
        assert caps.supports_member_management is True
        assert caps.max_batch_size == 1

    def test_capabilities_from_config_with_mock_settings(self, monkeypatch):
        """Test from_config with mocked settings."""
        import types

        mock_settings = types.SimpleNamespace(
            groups=types.SimpleNamespace(
                providers={
                    "test": {
                        "capabilities": {
                            "supports_user_creation": True,
                            "provides_role_info": True,
                            "max_batch_size": 50,
                        }
                    }
                }
            )
        )
        monkeypatch.setattr(
            "modules.groups.providers.base.settings",
            mock_settings,
        )
        caps = ProviderCapabilities.from_config("test")
        assert caps.supports_user_creation is True
        assert caps.provides_role_info is True
        assert caps.max_batch_size == 50

    def test_capabilities_batch_size_configuration(self):
        """Test batch size can be configured."""
        caps = ProviderCapabilities(max_batch_size=250)
        assert caps.max_batch_size == 250


@pytest.mark.unit
class TestProviderSupportsFunctions:
    """Test provider capability checking functions."""

    def test_provider_supports_existing_capability(self, monkeypatch):
        """Test checking for an existing capability."""
        import types

        mock_settings = types.SimpleNamespace(
            groups=types.SimpleNamespace(
                providers={
                    "test": {
                        "capabilities": {
                            "supports_batch_operations": True,
                        }
                    }
                }
            )
        )
        monkeypatch.setattr(
            "modules.groups.providers.base.settings",
            mock_settings,
        )
        assert provider_supports("test", "supports_batch_operations") is True

    def test_provider_supports_missing_capability(self, monkeypatch):
        """Test checking for a missing capability."""
        import types

        mock_settings = types.SimpleNamespace(
            groups=types.SimpleNamespace(
                providers={
                    "test": {
                        "capabilities": {
                            "supports_batch_operations": False,
                        }
                    }
                }
            )
        )
        monkeypatch.setattr(
            "modules.groups.providers.base.settings",
            mock_settings,
        )
        assert provider_supports("test", "supports_user_creation") is False

    def test_provider_provides_role_info(self, monkeypatch):
        """Test role info checking function."""
        import types

        mock_settings = types.SimpleNamespace(
            groups=types.SimpleNamespace(
                providers={
                    "test": {
                        "capabilities": {
                            "provides_role_info": True,
                        }
                    }
                }
            )
        )
        monkeypatch.setattr(
            "modules.groups.providers.base.settings",
            mock_settings,
        )
        assert provider_provides_role_info("test") is True

    def test_provider_provides_role_info_false(self, monkeypatch):
        """Test role info checking when false."""
        import types

        mock_settings = types.SimpleNamespace(
            groups=types.SimpleNamespace(
                providers={
                    "test": {
                        "capabilities": {
                            "provides_role_info": False,
                        }
                    }
                }
            )
        )
        monkeypatch.setattr(
            "modules.groups.providers.base.settings",
            mock_settings,
        )
        assert provider_provides_role_info("test") is False

    def test_provider_supports_with_exception(self, monkeypatch):
        """Test provider_supports returns False on exception."""
        monkeypatch.setattr(
            "modules.groups.providers.base.settings",
            type("obj", (object,), {})(),
        )
        result = provider_supports("unknown", "supports_user_creation")
        assert result is False


@pytest.mark.unit
class TestOperationResultComparison:
    """Test OperationResult comparison and equality."""

    def test_operation_result_with_same_values(self):
        """Test results with same values are equal."""
        result1 = OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
        )
        result2 = OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
        )
        # Dataclass equality
        assert result1 == result2

    def test_operation_result_with_different_status(self):
        """Test results with different status are not equal."""
        result1 = OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
        )
        result2 = OperationResult(
            status=OperationStatus.PERMANENT_ERROR,
            message="ok",
        )
        assert result1 != result2

    def test_operation_result_with_different_message(self):
        """Test results with different message are not equal."""
        result1 = OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
        )
        result2 = OperationResult(
            status=OperationStatus.SUCCESS,
            message="done",
        )
        assert result1 != result2


@pytest.mark.unit
class TestOperationResultEdgeCases:
    """Test OperationResult edge cases."""

    def test_operation_result_with_nested_data(self):
        """Test result with nested data structures."""
        data = {
            "user": {
                "id": "123",
                "email": "user@example.com",
                "groups": ["admin", "developers"],
            }
        }
        result = OperationResult.success(data=data)
        assert result.data["user"]["id"] == "123"
        assert "admin" in result.data["user"]["groups"]

    def test_operation_result_with_empty_data(self):
        """Test result with empty data dict."""
        result = OperationResult.success(data={})
        assert result.data == {}

    def test_operation_result_with_large_retry_after(self):
        """Test result with large retry_after value."""
        result = OperationResult.transient_error(
            "Rate limited",
            error_code="RATE_LIMIT",
        )
        result.retry_after = 3600  # 1 hour
        assert result.retry_after == 3600

    def test_operation_result_with_none_values(self):
        """Test result explicitly with None values."""
        result = OperationResult(
            status=OperationStatus.SUCCESS,
            message="test",
            data=None,
            error_code=None,
            retry_after=None,
        )
        assert result.data is None
        assert result.error_code is None
        assert result.retry_after is None
