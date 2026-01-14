"""Unit tests for BaseResponseFormatter abstract class."""

import pytest
from typing import Any, Dict, Optional

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.platforms.formatters.base import BaseResponseFormatter


class ConcreteResponseFormatter(BaseResponseFormatter):
    """Concrete implementation of BaseResponseFormatter for testing."""

    def format_success(
        self,
        data: Dict[str, Any],
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mock format_success implementation."""
        return {
            "type": "success",
            "message": message or "Success",
            "data": data,
        }

    def format_error(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Mock format_error implementation."""
        return {
            "type": "error",
            "message": message,
            "error_code": error_code,
            "details": details,
        }

    def format_info(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Mock format_info implementation."""
        return {
            "type": "info",
            "message": message,
            "data": data,
        }


class MockTranslator:
    """Mock translator for testing."""

    def translate(self, key: str, locale: str = "en", **kwargs) -> str:
        """Mock translate method."""
        if locale == "fr":
            return f"[FR] {key}"
        return f"[EN] {key}"


@pytest.mark.unit
class TestBaseResponseFormatter:
    """Test BaseResponseFormatter abstract base class."""

    def test_cannot_instantiate_abstract_base_class(self):
        """Test that BaseResponseFormatter cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            BaseResponseFormatter()  # type: ignore

        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_concrete_formatter_initialization(self):
        """Test initializing a concrete formatter implementation."""
        formatter = ConcreteResponseFormatter()

        assert formatter.locale == "en"
        assert formatter._translator is None

    def test_formatter_with_custom_locale(self):
        """Test formatter with custom locale."""
        formatter = ConcreteResponseFormatter(locale="fr")

        assert formatter.locale == "fr"

    def test_formatter_with_translator(self):
        """Test formatter with translator instance."""
        translator = MockTranslator()
        formatter = ConcreteResponseFormatter(translator=translator)

        assert formatter._translator is translator

    def test_format_success(self):
        """Test format_success() returns success payload."""
        formatter = ConcreteResponseFormatter()
        data = {"user_id": "123", "action": "completed"}

        result = formatter.format_success(data, message="Operation successful")

        assert result["type"] == "success"
        assert result["message"] == "Operation successful"
        assert result["data"] == data

    def test_format_success_without_message(self):
        """Test format_success() with default message."""
        formatter = ConcreteResponseFormatter()
        data = {"status": "ok"}

        result = formatter.format_success(data)

        assert result["type"] == "success"
        assert result["message"] == "Success"
        assert result["data"] == data

    def test_format_error(self):
        """Test format_error() returns error payload."""
        formatter = ConcreteResponseFormatter()

        result = formatter.format_error(
            message="Something went wrong",
            error_code="ERR_001",
            details={"field": "email", "issue": "invalid"},
        )

        assert result["type"] == "error"
        assert result["message"] == "Something went wrong"
        assert result["error_code"] == "ERR_001"
        assert result["details"]["field"] == "email"

    def test_format_error_minimal(self):
        """Test format_error() with only message."""
        formatter = ConcreteResponseFormatter()

        result = formatter.format_error(message="Error occurred")

        assert result["type"] == "error"
        assert result["message"] == "Error occurred"
        assert result["error_code"] is None
        assert result["details"] is None

    def test_format_info(self):
        """Test format_info() returns info payload."""
        formatter = ConcreteResponseFormatter()

        result = formatter.format_info(
            message="Processing...",
            data={"progress": 50},
        )

        assert result["type"] == "info"
        assert result["message"] == "Processing..."
        assert result["data"]["progress"] == 50

    def test_format_info_without_data(self):
        """Test format_info() with message only."""
        formatter = ConcreteResponseFormatter()

        result = formatter.format_info(message="System ready")

        assert result["type"] == "info"
        assert result["message"] == "System ready"
        assert result["data"] is None

    def test_format_warning_delegates_to_info(self):
        """Test format_warning() delegates to format_info() by default."""
        formatter = ConcreteResponseFormatter()

        result = formatter.format_warning(
            message="Warning: Low disk space",
            data={"available_gb": 5},
        )

        # Default implementation should delegate to format_info
        assert result["type"] == "info"
        assert result["message"] == "Warning: Low disk space"
        assert result["data"]["available_gb"] == 5


@pytest.mark.unit
class TestFormatOperationResult:
    """Test format_operation_result() method."""

    def test_format_successful_operation_result(self):
        """Test formatting a successful OperationResult."""
        formatter = ConcreteResponseFormatter()
        result = OperationResult.success(
            data={"user_id": "123"},
            message="User created successfully",
        )

        formatted = formatter.format_operation_result(result)

        assert formatted["type"] == "success"
        assert formatted["message"] == "User created successfully"
        assert formatted["data"]["user_id"] == "123"

    def test_format_error_operation_result(self):
        """Test formatting a failed OperationResult."""
        formatter = ConcreteResponseFormatter()
        result = OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message="User not found",
            error_code="USER_NOT_FOUND",
            data={"user_id": "999"},
        )

        formatted = formatter.format_operation_result(result)

        assert formatted["type"] == "error"
        assert formatted["message"] == "User not found"
        assert formatted["error_code"] == "USER_NOT_FOUND"
        assert formatted["details"]["user_id"] == "999"

    def test_format_transient_error_result(self):
        """Test formatting a transient error OperationResult."""
        formatter = ConcreteResponseFormatter()
        result = OperationResult.transient_error(
            message="Network timeout",
            error_code="TIMEOUT",
        )

        formatted = formatter.format_operation_result(result)

        assert formatted["type"] == "error"
        assert formatted["message"] == "Network timeout"
        assert formatted["error_code"] == "TIMEOUT"

    def test_format_operation_result_without_message(self):
        """Test formatting OperationResult with no message."""
        formatter = ConcreteResponseFormatter()
        result = OperationResult(
            status=OperationStatus.PERMANENT_ERROR,
            message=None,
        )

        formatted = formatter.format_operation_result(result)

        assert formatted["type"] == "error"
        assert formatted["message"] == "An error occurred"


@pytest.mark.unit
class TestTranslation:
    """Test translation integration."""

    def test_translate_without_translator(self):
        """Test translate() returns key when translator not set."""
        formatter = ConcreteResponseFormatter()

        result = formatter.translate("greeting.hello")

        assert result == "greeting.hello"

    def test_translate_with_translator(self):
        """Test translate() uses translator when available."""
        translator = MockTranslator()
        formatter = ConcreteResponseFormatter(translator=translator)

        result = formatter.translate("greeting.hello")

        assert result == "[EN] greeting.hello"

    def test_translate_with_french_locale(self):
        """Test translate() respects locale setting."""
        translator = MockTranslator()
        formatter = ConcreteResponseFormatter(translator=translator, locale="fr")

        result = formatter.translate("greeting.hello")

        assert result == "[FR] greeting.hello"

    def test_translate_with_substitutions(self):
        """Test translate() passes kwargs to translator."""
        translator = MockTranslator()
        formatter = ConcreteResponseFormatter(translator=translator)

        # MockTranslator doesn't actually use kwargs, but verify it's called
        result = formatter.translate("greeting.hello", name="Alice")

        assert "[EN]" in result


@pytest.mark.unit
class TestLocaleManagement:
    """Test locale get/set operations."""

    def test_get_locale(self):
        """Test locale property getter."""
        formatter = ConcreteResponseFormatter(locale="fr")

        assert formatter.locale == "fr"

    def test_set_locale(self):
        """Test set_locale() changes locale."""
        formatter = ConcreteResponseFormatter(locale="en")

        formatter.set_locale("fr")

        assert formatter.locale == "fr"

    def test_locale_affects_translation(self):
        """Test changing locale affects translation."""
        translator = MockTranslator()
        formatter = ConcreteResponseFormatter(translator=translator, locale="en")

        result_en = formatter.translate("test.key")
        assert result_en == "[EN] test.key"

        formatter.set_locale("fr")
        result_fr = formatter.translate("test.key")
        assert result_fr == "[FR] test.key"


@pytest.mark.unit
class TestFormatterRepr:
    """Test __repr__ string representation."""

    def test_repr_with_default_locale(self):
        """Test __repr__ shows locale."""
        formatter = ConcreteResponseFormatter()

        repr_str = repr(formatter)

        assert "ConcreteResponseFormatter" in repr_str
        assert "locale='en'" in repr_str

    def test_repr_with_custom_locale(self):
        """Test __repr__ shows custom locale."""
        formatter = ConcreteResponseFormatter(locale="fr")

        repr_str = repr(formatter)

        assert "locale='fr'" in repr_str


@pytest.mark.unit
class TestAbstractMethodEnforcement:
    """Test that abstract methods must be implemented."""

    def test_missing_format_success_raises_error(self):
        """Test that missing format_success() raises TypeError."""

        class IncompleteFormatter(BaseResponseFormatter):
            def format_error(self, message, error_code=None, details=None):
                return {}

            def format_info(self, message, data=None):
                return {}

        with pytest.raises(TypeError) as exc_info:
            IncompleteFormatter()  # type: ignore

        assert "format_success" in str(exc_info.value)

    def test_missing_format_error_raises_error(self):
        """Test that missing format_error() raises TypeError."""

        class IncompleteFormatter(BaseResponseFormatter):
            def format_success(self, data, message=None):
                return {}

            def format_info(self, message, data=None):
                return {}

        with pytest.raises(TypeError) as exc_info:
            IncompleteFormatter()  # type: ignore

        assert "format_error" in str(exc_info.value)

    def test_missing_format_info_raises_error(self):
        """Test that missing format_info() raises TypeError."""

        class IncompleteFormatter(BaseResponseFormatter):
            def format_success(self, data, message=None):
                return {}

            def format_error(self, message, error_code=None, details=None):
                return {}

        with pytest.raises(TypeError) as exc_info:
            IncompleteFormatter()  # type: ignore

        assert "format_info" in str(exc_info.value)
