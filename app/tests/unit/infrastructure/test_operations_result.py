"""Unit tests for OperationResult and OperationStatus in infrastructure.

Moved from tests/unit/modules/groups/providers/test_base_provider.py (OperationResult/Status parts).
"""

import pytest
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus


@pytest.mark.unit
class TestOperationStatus:
    def test_operation_status_success(self):
        assert OperationStatus.SUCCESS.value == "success"

    def test_operation_status_transient_error(self):
        assert OperationStatus.TRANSIENT_ERROR.value == "transient_error"

    def test_operation_status_permanent_error(self):
        assert OperationStatus.PERMANENT_ERROR.value == "permanent_error"

    def test_operation_status_unauthorized(self):
        assert OperationStatus.UNAUTHORIZED.value == "unauthorized"

    def test_operation_status_not_found(self):
        assert OperationStatus.NOT_FOUND.value == "not_found"


@pytest.mark.unit
class TestOperationResultFactories:
    def test_success_factory_minimal(self):
        result = OperationResult.success()
        assert result.status == OperationStatus.SUCCESS

    def test_success_factory_with_data(self):
        data = {"id": "123"}
        result = OperationResult.success(data=data, message="Created")
        assert result.status == OperationStatus.SUCCESS
        assert result.data == data

    def test_error_factory_minimal(self):
        result = OperationResult.error(OperationStatus.PERMANENT_ERROR, "Not found")
        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_error_factory_with_error_code(self):
        result = OperationResult.error(
            OperationStatus.PERMANENT_ERROR, "Not found", error_code="404"
        )
        assert result.error_code == "404"

    def test_transient_error_factory(self):
        result = OperationResult.transient_error("Timeout", error_code="TIMEOUT")
        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.message == "Timeout"

    def test_permanent_error_factory(self):
        result = OperationResult.permanent_error(
            "Invalid input", error_code="VALIDATION_ERROR"
        )
        assert result.status == OperationStatus.PERMANENT_ERROR


@pytest.mark.unit
class TestOperationResultEdgeCases:
    def test_operation_result_with_nested_data(self):
        data = {"user": {"id": "123", "groups": ["admin"]}}
        result = OperationResult.success(data=data)
        assert result.data["user"]["id"] == "123"

    def test_operation_result_with_empty_data(self):
        result = OperationResult.success(data={})
        assert result.data == {}


@pytest.mark.unit
class TestOperationResultObservability:
    """Test provider and operation fields for observability."""

    def test_success_with_provider_and_operation(self):
        result = OperationResult.success(
            data={"users": []},
            provider="google",
            operation="list_users",
        )
        assert result.provider == "google"
        assert result.operation == "list_users"
        assert result.is_success

    def test_error_with_provider_and_operation(self):
        result = OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            "Rate limited",
            error_code="RATE_LIMITED",
            retry_after=60,
            provider="aws",
            operation="list_groups",
        )
        assert result.provider == "aws"
        assert result.operation == "list_groups"
        assert result.retry_after == 60

    def test_provider_defaults_to_none(self):
        result = OperationResult.success(data={"test": "value"})
        assert result.provider is None

    def test_operation_defaults_to_none(self):
        result = OperationResult.permanent_error("Failed")
        assert result.operation is None


@pytest.mark.unit
class TestOperationResultMap:
    """Test map() method for transforming success values."""

    def test_map_transforms_success_value(self):
        result = OperationResult.success(data=5)
        doubled = result.map(lambda x: x * 2)
        assert doubled.is_success
        assert doubled.data == 10

    def test_map_preserves_error(self):
        error = OperationResult.permanent_error("Failed", error_code="ERR")
        mapped = error.map(lambda x: x * 2)
        assert not mapped.is_success
        assert mapped.status == OperationStatus.PERMANENT_ERROR
        assert mapped.error_code == "ERR"

    def test_map_preserves_observability_on_success(self):
        result = OperationResult.success(
            data="hello",
            provider="test",
            operation="greet",
        )
        mapped = result.map(str.upper)
        assert mapped.data == "HELLO"
        assert mapped.provider == "test"
        assert mapped.operation == "greet"

    def test_map_preserves_all_error_fields(self):
        error = OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            "Rate limited",
            error_code="RATE_LIMITED",
            retry_after=60,
            provider="google",
            operation="list_members",
        )
        mapped = error.map(lambda x: x * 2)
        assert mapped.status == OperationStatus.TRANSIENT_ERROR
        assert mapped.message == "Rate limited"
        assert mapped.error_code == "RATE_LIMITED"
        assert mapped.retry_after == 60
        assert mapped.provider == "google"
        assert mapped.operation == "list_members"

    def test_map_with_complex_transformation(self):
        result = OperationResult.success(data={"count": 5})
        transformed = result.map(lambda d: {**d, "doubled": d["count"] * 2})
        assert transformed.data == {"count": 5, "doubled": 10}


@pytest.mark.unit
class TestOperationResultBind:
    """Test bind() method for Railway-Oriented Programming."""

    def test_bind_chains_successful_operations(self):
        def add_one(x: int) -> OperationResult:
            return OperationResult.success(data=x + 1)

        def multiply_two(x: int) -> OperationResult:
            return OperationResult.success(data=x * 2)

        result = OperationResult.success(data=5).bind(add_one).bind(multiply_two)

        assert result.is_success
        assert result.data == 12  # (5 + 1) * 2

    def test_bind_stops_at_first_error(self):
        def add_one(x: int) -> OperationResult:
            return OperationResult.success(data=x + 1)

        def fail_always(x: int) -> OperationResult:
            return OperationResult.permanent_error("Failed", error_code="ERR")

        def should_not_run(x: int) -> OperationResult:
            # This should never execute
            raise AssertionError("Should not be called")

        result = (
            OperationResult.success(data=5)
            .bind(add_one)
            .bind(fail_always)
            .bind(should_not_run)
        )

        assert not result.is_success
        assert result.message == "Failed"
        assert result.error_code == "ERR"

    def test_bind_with_validation_pattern(self):
        def validate_positive(x: int) -> OperationResult:
            if x > 0:
                return OperationResult.success(data=x)
            return OperationResult.permanent_error(
                "Must be positive", error_code="INVALID"
            )

        # Valid case
        result = OperationResult.success(data=10).bind(validate_positive)
        assert result.is_success
        assert result.data == 10

        # Invalid case
        result = OperationResult.success(data=-5).bind(validate_positive)
        assert not result.is_success
        assert result.error_code == "INVALID"

    def test_bind_preserves_initial_error(self):
        def should_not_run(x: int) -> OperationResult:
            raise AssertionError("Should not be called")

        error = OperationResult.permanent_error("Initial error")
        result = error.bind(should_not_run)

        assert not result.is_success
        assert result.message == "Initial error"

    def test_bind_with_fetch_enrich_pattern(self):
        """Simulates real-world pattern: fetch → validate → enrich."""

        def fetch_user(user_id: int) -> OperationResult:
            if user_id == 999:
                return OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    "User not found",
                    error_code="NOT_FOUND",
                )
            return OperationResult.success(
                data={"id": user_id, "name": f"User{user_id}"}
            )

        def enrich_profile(user: dict) -> OperationResult:
            enriched = {**user, "display_name": f"Profile: {user['name']}"}
            return OperationResult.success(data=enriched)

        # Success path
        result = OperationResult.success(data=123).bind(fetch_user).bind(enrich_profile)
        assert result.is_success
        assert result.data["display_name"] == "Profile: User123"

        # Not found path
        result = OperationResult.success(data=999).bind(fetch_user).bind(enrich_profile)
        assert not result.is_success
        assert result.status == OperationStatus.NOT_FOUND


@pytest.mark.unit
class TestOperationResultUnwrapOr:
    """Test unwrap_or() for safe value extraction."""

    def test_unwrap_or_returns_value_on_success(self):
        result = OperationResult.success(data=42)
        value = result.unwrap_or(0)
        assert value == 42

    def test_unwrap_or_returns_default_on_error(self):
        error = OperationResult.permanent_error("Failed")
        value = error.unwrap_or(0)
        assert value == 0

    def test_unwrap_or_with_none_default(self):
        error = OperationResult.permanent_error("Failed")
        value = error.unwrap_or(None)
        assert value is None

    def test_unwrap_or_with_complex_default(self):
        error = OperationResult.permanent_error("Failed")
        default = {"fallback": True}
        value = error.unwrap_or(default)
        assert value == {"fallback": True}

    def test_unwrap_or_with_none_data(self):
        result = OperationResult.success(data=None)
        value = result.unwrap_or("default")
        assert value is None  # Returns actual None, not default


@pytest.mark.unit
class TestOperationResultUnwrap:
    """Test unwrap() for value extraction with exceptions."""

    def test_unwrap_returns_value_on_success(self):
        result = OperationResult.success(data=42)
        value = result.unwrap()
        assert value == 42

    def test_unwrap_raises_on_error(self):
        error = OperationResult.permanent_error("Failed", error_code="ERR")
        with pytest.raises(ValueError) as exc_info:
            error.unwrap()

        assert "Called unwrap() on error result" in str(exc_info.value)
        assert "Failed" in str(exc_info.value)
        assert "ERR" in str(exc_info.value)

    def test_unwrap_raises_on_transient_error(self):
        error = OperationResult.transient_error("Timeout")
        with pytest.raises(ValueError):
            error.unwrap()

    def test_unwrap_with_none_data(self):
        result = OperationResult.success(data=None)
        value = result.unwrap()
        assert value is None

    def test_unwrap_error_message_includes_status(self):
        error = OperationResult.error(
            OperationStatus.NOT_FOUND, "Not found", error_code="404"
        )
        with pytest.raises(ValueError) as exc_info:
            error.unwrap()

        assert "not_found" in str(exc_info.value)


@pytest.mark.unit
class TestOperationResultRailwayPattern:
    """Test complete Railway-Oriented Programming workflows."""

    def test_map_and_bind_composition(self):
        """Combine map and bind for complex workflows."""

        def double(x: int) -> int:
            return x * 2

        def validate_positive(x: int) -> OperationResult:
            if x > 0:
                return OperationResult.success(data=x)
            return OperationResult.permanent_error("Must be positive")

        def to_string(x: int) -> str:
            return f"Result: {x}"

        # Success path
        result = (
            OperationResult.success(data=5)
            .map(double)  # 10
            .bind(validate_positive)  # Still 10 (valid)
            .map(to_string)  # "Result: 10"
        )

        assert result.is_success
        assert result.data == "Result: 10"

        # Error path - negative after doubling
        result = (
            OperationResult.success(data=-3)
            .map(double)  # -6
            .bind(validate_positive)  # Fails here
            .map(to_string)  # Skipped
        )

        assert not result.is_success
        assert result.message == "Must be positive"

    def test_complex_chain_with_multiple_operations(self):
        """Test longer chain simulating real-world scenario."""

        def validate_id(user_id: int) -> OperationResult:
            if user_id > 0:
                return OperationResult.success(data=user_id, operation="validate")
            return OperationResult.permanent_error("Invalid ID")

        def fetch_user(user_id: int) -> OperationResult:
            users = {1: "Alice", 2: "Bob"}
            if user_id in users:
                return OperationResult.success(
                    data={"id": user_id, "name": users[user_id]},
                    provider="database",
                    operation="fetch",
                )
            return OperationResult.error(
                OperationStatus.NOT_FOUND, "User not found", error_code="NOT_FOUND"
            )

        def check_active(user: dict) -> OperationResult:
            # Simulate active check
            user["is_active"] = True
            return OperationResult.success(data=user, operation="check_active")

        # Success path
        result = (
            OperationResult.success(data=1)
            .bind(validate_id)
            .bind(fetch_user)
            .bind(check_active)
            .map(lambda u: u["name"].upper())
        )

        assert result.is_success
        assert result.data == "ALICE"

        # Not found path
        result = (
            OperationResult.success(data=999)
            .bind(validate_id)
            .bind(fetch_user)
            .bind(check_active)
            .map(lambda u: u["name"].upper())
        )

        assert not result.is_success
        assert result.status == OperationStatus.NOT_FOUND

        # Invalid ID path
        result = (
            OperationResult.success(data=-1)
            .bind(validate_id)
            .bind(fetch_user)
            .bind(check_active)
            .map(lambda u: u["name"].upper())
        )

        assert not result.is_success
        assert result.message == "Invalid ID"
