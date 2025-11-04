"""Performance tests for groups module.

These tests measure framework performance characteristics and validate
that the application meets basic performance requirements.

Note: These are unit performance tests focused on schema/model performance,
not load tests or end-to-end integration performance.
"""

import time
from datetime import datetime
from statistics import mean
from modules.groups.schemas import (
    AddMemberRequest,
    RemoveMemberRequest,
    ActionResponse,
    BulkOperationsRequest,
    OperationType,
)


class TestValidationPerformance:
    """Test performance of request validation."""

    def test_add_member_request_validation_speed(self):
        """Measure AddMemberRequest validation speed."""
        request_data = {
            "provider": "google",
            "group_id": "group-123",
            "member_email": "user@example.com",
        }

        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            try:
                AddMemberRequest(**request_data)
            except Exception:
                pass
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / iterations) * 1000
        assert avg_time_ms < 5.0, f"Validation took {avg_time_ms:.2f}ms per request"

    def test_remove_member_request_validation_speed(self):
        """Measure RemoveMemberRequest validation speed."""
        request_data = {
            "provider": "google",
            "group_id": "group-123",
            "member_email": "user@example.com",
        }

        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            try:
                RemoveMemberRequest(**request_data)
            except Exception:
                pass
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / iterations) * 1000
        assert avg_time_ms < 5.0, f"Validation took {avg_time_ms:.2f}ms per request"


class TestErrorHandlingPerformance:
    """Measure error handling performance."""

    def test_validation_error_generation_speed(self):
        """Validation error generation should be fast."""
        invalid_data = {
            "provider": "invalid_provider_name",
            "member_email": "not_an_email",
            "group_id": "",
        }

        timings = []
        for _ in range(100):
            start = time.perf_counter()
            try:
                AddMemberRequest(**invalid_data)
            except Exception:
                pass
            end = time.perf_counter()
            timings.append((end - start) * 1000)

        avg_time = mean(timings)

        # Error handling should be <5ms average
        assert avg_time < 5, f"Error handling avg {avg_time:.3f}ms exceeds target <5ms"


class TestModelCreationPerformance:
    """Measure model creation performance."""

    def test_action_response_creation_speed(self):
        """ActionResponse creation should be fast."""
        timings = []
        for i in range(100):
            start = time.perf_counter()
            ActionResponse(
                action=OperationType.ADD_MEMBER,
                success=True,
                group_id="group-123",
                member_email="user@example.com",
                provider="google",
                timestamp=time.time(),
            )
            end = time.perf_counter()
            timings.append((end - start) * 1000)

        avg_time = mean(timings)

        # Model creation should be <1ms average
        assert avg_time < 1, f"Model creation avg {avg_time:.3f}ms exceeds target <1ms"


class TestBulkOperationPerformance:
    """Measure bulk operation processing performance."""

    def test_bulk_operations_parsing_speed(self):
        """Parsing bulk operations should be fast."""
        bulk_data = {
            "operations": [
                {
                    "operation": OperationType.ADD_MEMBER,
                    "payload": {
                        "provider": "google",
                        "group_id": "group-123",
                        "member_email": f"user{i}@example.com",
                    },
                }
                for i in range(10)
            ]
        }

        timings = []
        for _ in range(100):
            start = time.perf_counter()
            BulkOperationsRequest(**bulk_data)
            end = time.perf_counter()
            timings.append((end - start) * 1000)

        avg_time = mean(timings)

        # Bulk operations parsing should be <5ms average
        assert avg_time < 5, f"Parsing avg {avg_time:.3f}ms exceeds target <5ms"
