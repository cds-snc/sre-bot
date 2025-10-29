from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import pytest

import modules.groups.orchestration as orch


class DummyOp:
    def __init__(self, status="SUCCESS", data=None, message=""):
        self.status = status
        self.data = data
        self.message = message


def _patch_operation_symbols(m_op_status="SUCCESS"):
    """
    Helper patch context to ensure OperationStatus.SUCCESS and
    OperationResult.transient_error are stable in tests.
    """
    patcher_status = patch(
        "modules.groups.providers.base.OperationStatus", new=SimpleNamespace(SUCCESS=m_op_status)
    )
    patcher_result = patch(
        "modules.groups.providers.base.OperationResult",
        new=SimpleNamespace(transient_error=staticmethod(lambda msg: DummyOp(status="TRANSIENT", message=msg))),
    )
    return patcher_status, patcher_result


def test_map_secondary_to_primary_group_success():
    with patch("modules.groups.providers.get_primary_provider_name", return_value="google"), patch(
        "modules.groups.group_name_mapping.map_provider_group_id", return_value="a-my-group"
    ) as mp:
        res = orch.map_secondary_to_primary_group("aws", "my-group")
        assert res == "a-my-group"
        mp.assert_called_once_with(from_provider="aws", from_group_id="my-group", to_provider="google")


def test_map_secondary_to_primary_group_raises_on_failure():
    with patch("modules.groups.providers.get_primary_provider_name", return_value="google"), patch(
        "modules.groups.group_name_mapping.map_provider_group_id", side_effect=Exception("boom")
    ):
        with pytest.raises(ValueError):
            orch.map_secondary_to_primary_group("aws", "my-group")


def test_map_primary_to_secondary_group_success():
    with patch("modules.groups.providers.get_primary_provider_name", return_value="google"), patch(
        "modules.groups.group_name_mapping.map_provider_group_id", return_value="my-group"
    ) as mp:
        res = orch.map_primary_to_secondary_group("g-my-group", "aws")
        assert res == "my-group"
        mp.assert_called_once_with(from_provider="google", from_group_id="g-my-group", to_provider="aws")


def test_normalize_member_for_provider_valid_and_invalid():
    # Patch the schema model so we don't import Pydantic in tests
    class FakeNM:
        def __init__(self, **kwargs):
            self._kw = kwargs

    with patch("modules.groups.schemas.NormalizedMember", new=FakeNM):
        nm = orch.normalize_member_for_provider("user@example.com", "aws")
        assert isinstance(nm, FakeNM)
        assert nm._kw["email"] == "user@example.com"

    with pytest.raises(ValueError):
        orch.normalize_member_for_provider("not-an-email", "aws")


def test_validate_group_in_provider_with_opresult_and_plain_success():
    # provider returns OperationResult-like with status SUCCESS
    provider = MagicMock()
    provider.get_group_members.return_value = DummyOp(status="SUCCESS")

    p_status, p_result = _patch_operation_symbols(m_op_status="SUCCESS")
    with p_status, p_result:
        assert orch.validate_group_in_provider("grp", provider) is True

    # provider returns non-OperationResult (no status attr) -> True when no exception
    provider.get_group_members.return_value = {"members": []}
    assert orch.validate_group_in_provider("grp", provider) is True

    # provider.get_group_members raises -> False
    provider.get_group_members.side_effect = Exception("not found")
    assert orch.validate_group_in_provider("grp", provider) is False


def test__unwrap_opresult_data_variants():
    # dict with single key -> first value returned
    obj = SimpleNamespace(data={"members": [1, 2, 3]})
    assert orch._unwrap_opresult_data(obj) == [1, 2, 3]

    # non-dict data returned as-is
    obj2 = SimpleNamespace(data=None)
    assert orch._unwrap_opresult_data(obj2) is None

    obj3 = SimpleNamespace(data=42)
    assert orch._unwrap_opresult_data(obj3) == 42


def test_add_member_to_group_primary_failure_no_propagation():
    # primary.add_member raises -> primary_result becomes transient and orchestration
    # should call format_orchestration_response with empty propagation
    primary = MagicMock()
    primary.add_member.side_effect = Exception("primary fail")
    fake_active = {"google": primary}

    p_status, p_result = _patch_operation_symbols(m_op_status="SUCCESS")
    with patch("modules.groups.providers.get_primary_provider", return_value=primary), patch(
        "modules.groups.providers.get_active_providers", return_value=fake_active
    ), patch("modules.groups.providers.get_primary_provider_name", return_value="google"), patch(
        "modules.groups.orchestration.uuid4", return_value=SimpleNamespace(__str__=lambda self: "cid")
    ), patch("modules.groups.orchestration.logger"):
        with p_status, p_result, patch(
            "modules.groups.orchestration.orr.format_orchestration_response",
            return_value={"ok": True},
        ) as fmt:
            res = orch.add_member_to_group("grp", "user@example.com", "just")
            fmt.assert_called_once()
            assert res == {"ok": True}


def test_add_member_to_group_primary_success_secondary_partial_failure():
    # primary.success, one secondary fails -> should enqueue reconciliation and return formatted response
    primary = MagicMock()
    primary.add_member.return_value = DummyOp(status="SUCCESS", data={"result": {"id": "p1"}})

    sec = MagicMock()
    # secondary returns non-success
    sec.add_member.return_value = DummyOp(status="FAIL", message="upstream error")

    active = {"google": primary, "aws": sec}

    p_status, p_result = _patch_operation_symbols(m_op_status="SUCCESS")
    with patch("modules.groups.providers.get_primary_provider", return_value=primary), patch(
        "modules.groups.providers.get_active_providers", return_value=active
    ), patch("modules.groups.providers.get_primary_provider_name", return_value="google"), patch(
        "modules.groups.orchestration.map_primary_to_secondary_group", return_value="mapped-sec-grp"
    ), patch("modules.groups.orchestration.logger"):
        with p_status, p_result, patch(
            "modules.groups.orchestration.ri.enqueue_failed_propagation"
        ) as enqueue, patch(
            "modules.groups.orchestration.orr.format_orchestration_response",
            return_value={"ok": True},
        ) as fmt:
            res = orch.add_member_to_group("grp", "user@example.com", "just")
            # ensure enqueue was called for the failing secondary
            enqueue.assert_called_once()
            fmt.assert_called_once()
            assert res == {"ok": True}


def test_remove_member_from_group_propagation_and_partial():
    # primary.remove_member success, secondary remove_member raises -> should record transient and return formatted
    primary = MagicMock()
    primary.remove_member.return_value = DummyOp(status="SUCCESS", data={"result": {"id": "p1"}})

    sec = MagicMock()
    # secondary raises to simulate unexpected error
    sec.remove_member.side_effect = Exception("boom")

    active = {"google": primary, "aws": sec}

    p_status, p_result = _patch_operation_symbols(m_op_status="SUCCESS")
    with patch("modules.groups.providers.get_primary_provider", return_value=primary), patch(
        "modules.groups.providers.get_active_providers", return_value=active
    ), patch("modules.groups.providers.get_primary_provider_name", return_value="google"), patch(
        "modules.groups.orchestration.map_primary_to_secondary_group", return_value="mapped-sec-grp"
    ), patch("modules.groups.orchestration.logger"):
        with p_status, p_result, patch(
            "modules.groups.orchestration.ri.enqueue_failed_propagation"
        ) as enqueue, patch(
            "modules.groups.orchestration.orr.format_orchestration_response",
            return_value={"ok": True},
        ) as fmt:
            res = orch.remove_member_from_group("grp", "user@example.com", "just")
            # enqueue may or may not be called depending on handling, ensure formatted response returned
            fmt.assert_called_once()
            assert res == {"ok": True}