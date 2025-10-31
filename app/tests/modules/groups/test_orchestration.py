# python
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import pytest

import modules.groups.orchestration as orch


class DummyOp:
    def __init__(self, status="SUCCESS", data=None, message=""):
        self.status = status
        self.data = data
        self.message = message


def _transient_result_fn(msg):
    return DummyOp(status="TRANSIENT", message=msg)


def test_normalize_member_for_provider_valid_and_invalid():
    nm = orch.service_layer.normalize_member_for_provider("user@example.com", "aws")
    # returned object should expose email attribute and match input
    assert hasattr(nm, "email") and nm.email == "user@example.com"

    with pytest.raises(ValueError):
        orch.service_layer.normalize_member_for_provider("not-an-email", "aws")


@patch(
    "modules.groups.service.OperationResult",
    new=SimpleNamespace(
        transient_error=staticmethod(
            lambda msg: DummyOp(status="TRANSIENT", message=msg)
        )
    ),
)
@patch(
    "modules.groups.service.OperationStatus",
    new=SimpleNamespace(SUCCESS="SUCCESS"),
)
def test_validate_group_in_provider_with_opresult_and_plain_success():
    provider = MagicMock()
    provider.get_group_members.return_value = DummyOp(status="SUCCESS")

    # When OperationResult-like with status SUCCESS -> True
    assert orch.validate_group_in_provider("grp", provider) is True

    # Non-OperationResult return -> True when no exception
    provider.get_group_members.return_value = {"members": []}
    assert orch.validate_group_in_provider("grp", provider) is True

    # Exception -> False
    provider.get_group_members.side_effect = Exception("not found")
    assert orch.validate_group_in_provider("grp", provider) is False


def test__unwrap_opresult_data_variants():
    obj = SimpleNamespace(data={"members": [1, 2, 3]})
    assert orch._unwrap_opresult_data(obj) == [1, 2, 3]

    obj2 = SimpleNamespace(data=None)
    assert orch._unwrap_opresult_data(obj2) is None

    obj3 = SimpleNamespace(data=42)
    assert orch._unwrap_opresult_data(obj3) == 42


@patch("modules.groups.orchestration.ri.enqueue_failed_propagation")
@patch("modules.groups.orchestration.logger")
@patch(
    "modules.groups.service.map_primary_to_secondary_group",
    return_value="mapped-sec-grp",
)
@patch("modules.groups.orchestration.get_primary_provider_name", return_value="google")
@patch("modules.groups.orchestration.get_active_providers")
@patch("modules.groups.orchestration.get_primary_provider")
@patch(
    "modules.groups.service.OperationResult",
    new=SimpleNamespace(
        transient_error=staticmethod(
            lambda msg: DummyOp(status="TRANSIENT", message=msg)
        )
    ),
)
@patch(
    "modules.groups.service.OperationStatus",
    new=SimpleNamespace(SUCCESS="SUCCESS"),
)
@patch(
    "modules.groups.service.OperationResult",
    new=SimpleNamespace(
        transient_error=staticmethod(
            lambda msg: DummyOp(status="TRANSIENT", message=msg)
        )
    ),
)
@patch(
    "modules.groups.service.OperationStatus",
    new=SimpleNamespace(SUCCESS="SUCCESS"),
)
def test_add_member_to_group_primary_failure_no_propagation(
    mock_get_primary,
    mock_get_active,
    mock_get_primary_name,
    mock_map,
    mock_logger,
    mock_enqueue,
):
    primary = MagicMock()
    primary.add_member.side_effect = Exception("primary fail")
    fake_active = {"google": primary}

    mock_get_primary.return_value = primary
    mock_get_active.return_value = fake_active
    # uuid4 is imported at module level, patch where used
    with patch(
        "modules.groups.orchestration.uuid4",
        return_value=SimpleNamespace(__str__=lambda self: "cid"),
    ):
        res = orch.add_member_to_group("grp", "user@example.com", "just")

    # Orchestration now returns raw OperationResult objects; assert shape
    assert isinstance(res, dict)
    assert "primary" in res and "propagation" in res
    assert res["propagation"] == {}


@patch("modules.groups.orchestration.ri.enqueue_failed_propagation")
@patch("modules.groups.orchestration.logger")
@patch(
    "modules.groups.service.map_primary_to_secondary_group",
    return_value="mapped-sec-grp",
)
@patch("modules.groups.orchestration.get_primary_provider_name", return_value="google")
@patch("modules.groups.orchestration.get_active_providers")
@patch("modules.groups.orchestration.get_primary_provider")
@patch(
    "modules.groups.service.OperationResult",
    new=SimpleNamespace(
        transient_error=staticmethod(
            lambda msg: DummyOp(status="TRANSIENT", message=msg)
        )
    ),
)
@patch(
    "modules.groups.service.OperationStatus",
    new=SimpleNamespace(SUCCESS="SUCCESS"),
)
@patch(
    "modules.groups.service.OperationResult",
    new=SimpleNamespace(
        transient_error=staticmethod(
            lambda msg: DummyOp(status="TRANSIENT", message=msg)
        )
    ),
)
@patch(
    "modules.groups.service.OperationStatus",
    new=SimpleNamespace(SUCCESS="SUCCESS"),
)
def test_add_member_to_group_primary_success_secondary_partial_failure(
    mock_get_primary,
    mock_get_active,
    mock_get_primary_name,
    mock_map,
    mock_logger,
    mock_enqueue,
):
    primary = MagicMock()
    primary.add_member.return_value = DummyOp(
        status="SUCCESS", data={"result": {"id": "p1"}}
    )

    sec = MagicMock()
    sec.add_member.return_value = DummyOp(status="FAIL", message="upstream error")

    active = {"google": primary, "aws": sec}

    mock_get_primary.return_value = primary
    mock_get_active.return_value = active

    res = orch.add_member_to_group("grp", "user@example.com", "just")

    # Orchestration returns raw results; ensure propagation info present
    assert mock_enqueue.call_count in (0, 1)
    assert isinstance(res, dict)
    assert "propagation" in res


@patch("modules.groups.orchestration.ri.enqueue_failed_propagation")
@patch("modules.groups.orchestration.logger")
@patch(
    "modules.groups.service.map_primary_to_secondary_group",
    return_value="mapped-sec-grp",
)
@patch("modules.groups.orchestration.get_primary_provider_name", return_value="google")
@patch("modules.groups.orchestration.get_active_providers")
@patch("modules.groups.orchestration.get_primary_provider")
@patch(
    "modules.groups.orchestration.OperationResult",
    new=SimpleNamespace(
        transient_error=staticmethod(
            lambda msg: DummyOp(status="TRANSIENT", message=msg)
        )
    ),
)
@patch(
    "modules.groups.orchestration.OperationStatus",
    new=SimpleNamespace(SUCCESS="SUCCESS"),
)
@patch(
    "modules.groups.service.OperationResult",
    new=SimpleNamespace(
        transient_error=staticmethod(
            lambda msg: DummyOp(status="TRANSIENT", message=msg)
        )
    ),
)
@patch(
    "modules.groups.service.OperationStatus",
    new=SimpleNamespace(SUCCESS="SUCCESS"),
)
def test_remove_member_from_group_propagation_and_partial(
    mock_get_primary,
    mock_get_active,
    mock_get_primary_name,
    mock_map,
    mock_logger,
    mock_enqueue,
):
    primary = MagicMock()
    primary.remove_member.return_value = DummyOp(
        status="SUCCESS", data={"result": {"id": "p1"}}
    )

    sec = MagicMock()
    sec.remove_member.side_effect = Exception("boom")

    active = {"google": primary, "aws": sec}

    mock_get_primary.return_value = primary
    mock_get_active.return_value = active

    res = orch.remove_member_from_group("grp", "user@example.com", "just")

    # Orchestration returns raw result objects with propagation details
    assert isinstance(res, dict)
    assert "primary" in res and "propagation" in res
