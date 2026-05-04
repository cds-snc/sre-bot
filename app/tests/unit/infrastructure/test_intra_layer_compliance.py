"""ADR-0076 intra-layer compliance tests.

Verifies that infrastructure packages obey Standard 2 (no runtime sibling
configuration imports) and Standard 3 (no sibling service construction outside
providers.py).  Tests are structural/AST-based where possible so they catch
regressions without executing real service code.

Governing ADR: ADR-0076 — Infrastructure Intra-Layer Import Standard.
"""

import ast
from pathlib import Path
from typing import Set
from unittest.mock import MagicMock, patch

import pytest
from infrastructure.audit.service import AuditTrailService
from infrastructure.identity.models import IdentitySource, User
from infrastructure.notifications.channels.chat import ChatChannel
from infrastructure.notifications.channels.email import EmailChannel
from infrastructure.notifications.channels.sms import SMSChannel
from infrastructure.storage.service import StorageService

_APP_ROOT = Path(__file__).parents[3]  # workspace/app/


def _read_source(relative: str) -> str:
    return (_APP_ROOT / relative).read_text(encoding="utf-8")


def _runtime_imports(source: str) -> Set[str]:
    """Return all top-level (non-TYPE_CHECKING-guarded) import module names."""
    tree = ast.parse(source)
    guarded: Set[ast.AST] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            # Matches `if TYPE_CHECKING:` and `if typing.TYPE_CHECKING:`
            is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            )
            if is_tc:
                for child in ast.walk(node):
                    guarded.add(id(child))

    imports: Set[str] = set()
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
    return imports


def _has_constructor_call(source: str, class_name: str) -> bool:
    """Return True if source contains a direct instantiation of class_name()."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == class_name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == class_name:
                return True
    return False


# ---------------------------------------------------------------------------
# Standard 3 — service.py files must not runtime-import sibling services
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStorageServiceCompliance:
    """storage/service.py must not runtime-import DynamoDBClient."""

    def test_dynamodb_client_not_runtime_imported(self):
        """DynamoDBClient must be under TYPE_CHECKING only."""
        source = _read_source("infrastructure/storage/service.py")
        runtime = _runtime_imports(source)
        assert "infrastructure.clients.aws.dynamodb" not in runtime, (
            "DynamoDBClient must not be imported at runtime in storage/service.py "
            "(ADR-0076 S3.3 — use TYPE_CHECKING)."
        )

    def test_storage_service_accepts_dynamodb_via_constructor(self):
        """StorageService still accepts a DynamoDBClient via its constructor."""
        mock_dynamo = MagicMock()
        service = StorageService(dynamodb=mock_dynamo)
        assert service is not None


@pytest.mark.unit
class TestAuditServiceCompliance:
    """audit/service.py must not runtime-import StorageService."""

    def test_storage_service_not_runtime_imported(self):
        """StorageService must be under TYPE_CHECKING only."""
        source = _read_source("infrastructure/audit/service.py")
        runtime = _runtime_imports(source)
        assert "infrastructure.storage.service" not in runtime, (
            "StorageService must not be imported at runtime in audit/service.py "
            "(ADR-0076 S3.3 — use TYPE_CHECKING)."
        )

    def test_audit_service_accepts_storage_via_constructor(self):
        """AuditTrailService still accepts a StorageService via its constructor."""
        mock_storage = MagicMock()
        service = AuditTrailService(storage=mock_storage)
        assert service is not None


@pytest.mark.unit
class TestSecurityCurrentUserCompliance:
    """security/current_user.py must not runtime-import IdentityService."""

    def test_identity_service_not_runtime_imported(self):
        """IdentityService must be under TYPE_CHECKING only."""
        source = _read_source("infrastructure/security/current_user.py")
        runtime = _runtime_imports(source)
        assert "infrastructure.identity.service" not in runtime, (
            "IdentityService must not be runtime-imported in security/current_user.py "
            "(ADR-0076 S3.3 — use TYPE_CHECKING)."
        )

    def test_identity_value_types_may_be_runtime_imported(self):
        """IdentitySource and User (value types) may be imported at runtime (S1)."""
        assert IdentitySource is not None
        assert User is not None


@pytest.mark.unit
class TestNotificationChannelCircuitBreakerCompliance:
    """Notification channels must not construct CircuitBreaker instances internally."""

    def test_chat_channel_does_not_construct_circuit_breaker(self):
        """ChatChannel must not instantiate CircuitBreaker (ADR-0076 S3.1)."""
        source = _read_source("infrastructure/notifications/channels/chat.py")
        assert not _has_constructor_call(source, "CircuitBreaker"), (
            "ChatChannel must not construct CircuitBreaker internally. "
            "Receive it via constructor injection (ADR-0076 S3.1)."
        )

    def test_email_channel_does_not_construct_circuit_breaker(self):
        """EmailChannel must not instantiate CircuitBreaker (ADR-0076 S3.1)."""
        source = _read_source("infrastructure/notifications/channels/email.py")
        assert not _has_constructor_call(source, "CircuitBreaker"), (
            "EmailChannel must not construct CircuitBreaker internally. "
            "Receive it via constructor injection (ADR-0076 S3.1)."
        )

    def test_sms_channel_does_not_construct_circuit_breaker(self):
        """SMSChannel must not instantiate CircuitBreaker (ADR-0076 S3.1)."""
        source = _read_source("infrastructure/notifications/channels/sms.py")
        assert not _has_constructor_call(source, "CircuitBreaker"), (
            "SMSChannel must not construct CircuitBreaker internally. "
            "Receive it via constructor injection (ADR-0076 S3.1)."
        )

    def test_circuit_breaker_not_runtime_imported_in_chat(self):
        """CircuitBreaker import in chat.py must be TYPE_CHECKING-guarded."""
        source = _read_source("infrastructure/notifications/channels/chat.py")
        runtime = _runtime_imports(source)
        assert "infrastructure.resilience.circuit_breaker" not in runtime, (
            "CircuitBreaker must not be runtime-imported in chat.py "
            "(ADR-0076 S3.3 — use TYPE_CHECKING)."
        )

    def test_circuit_breaker_not_runtime_imported_in_email(self):
        """CircuitBreaker import in email.py must be TYPE_CHECKING-guarded."""
        source = _read_source("infrastructure/notifications/channels/email.py")
        runtime = _runtime_imports(source)
        assert "infrastructure.resilience.circuit_breaker" not in runtime, (
            "CircuitBreaker must not be runtime-imported in email.py "
            "(ADR-0076 S3.3 — use TYPE_CHECKING)."
        )

    def test_circuit_breaker_not_runtime_imported_in_sms(self):
        """CircuitBreaker import in sms.py must be TYPE_CHECKING-guarded."""
        source = _read_source("infrastructure/notifications/channels/sms.py")
        runtime = _runtime_imports(source)
        assert "infrastructure.resilience.circuit_breaker" not in runtime, (
            "CircuitBreaker must not be runtime-imported in sms.py "
            "(ADR-0076 S3.3 — use TYPE_CHECKING)."
        )

    def test_chat_channel_works_without_circuit_breaker(self):
        """ChatChannel must function when circuit_breaker=None (no-op path)."""
        mock_manager = MagicMock()
        with patch(
            "infrastructure.notifications.channels.chat.SlackClientManager",
            return_value=mock_manager,
        ):
            channel = ChatChannel(circuit_breaker=None)
            assert channel is not None

    def test_email_channel_works_without_circuit_breaker(self):
        """EmailChannel must function when circuit_breaker=None."""
        mock_settings = MagicMock()
        mock_settings.GOOGLE_DELEGATED_ADMIN_EMAIL = "admin@example.com"
        channel = EmailChannel(
            google_workspace_settings=mock_settings,
            circuit_breaker=None,
        )
        assert channel is not None

    def test_sms_channel_works_without_circuit_breaker(self):
        """SMSChannel must function when circuit_breaker=None."""
        mock_settings = MagicMock()
        mock_settings.NOTIFY_API_URL = "https://notify.example.com"
        channel = SMSChannel(notify_settings=mock_settings, circuit_breaker=None)
        assert channel is not None
