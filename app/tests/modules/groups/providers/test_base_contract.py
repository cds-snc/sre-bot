import importlib.util
import pathlib
import sys
import types

# Load the base module directly from file to avoid importing the top-level
# `modules` package which performs heavy imports during test collection.
base_path = (
    pathlib.Path(__file__).resolve().parents[4]
    / "modules"
    / "groups"
    / "providers"
    / "base.py"
)
spec = importlib.util.spec_from_file_location(
    "providers_base_for_tests", str(base_path)
)
base_mod = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None

# To avoid importing the real `modules` package (which triggers provider
# loading), inject lightweight stubs for the package and the
# `modules.groups.schemas` submodule so the `from ... import` in base.py
# resolves without executing the package __init__ files.

original_modules = {
    k: sys.modules.get(k)
    for k in ("modules", "modules.groups", "modules.groups.schemas")
}
try:
    # create lightweight package stubs
    if "modules" not in sys.modules:
        m = types.ModuleType("modules")
        m.__path__ = []
        sys.modules["modules"] = m
    if "modules.groups" not in sys.modules:
        mg = types.ModuleType("modules.groups")
        mg.__path__ = []
        sys.modules["modules.groups"] = mg

    # provide a minimal `modules.groups.schemas` module with the names we need
    mgs = types.ModuleType("modules.groups.schemas")

    # simple placeholders for type names used by base.py
    class NormalizedMember:  # type: ignore
        pass

    class NormalizedGroup:  # type: ignore
        pass

    mgs.NormalizedMember = NormalizedMember
    mgs.NormalizedGroup = NormalizedGroup
    sys.modules["modules.groups.schemas"] = mgs

    # Make the module discoverable in sys.modules so dataclass and other
    # introspection utilities work correctly during exec.
    sys.modules[spec.name] = base_mod
    try:
        spec.loader.exec_module(base_mod)  # type: ignore
    finally:
        # ensure the temporary module registration is removed after loading
        sys.modules.pop(spec.name, None)
finally:
    # restore any originals (or remove our stubs)
    for k, v in original_modules.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v

GroupProvider = base_mod.GroupProvider
ProviderCapabilities = base_mod.ProviderCapabilities
OperationResult = base_mod.OperationResult
OperationStatus = base_mod.OperationStatus


def test_provider_implementation_returns_role_info_when_capability_enabled():
    # Implement a minimal provider that advertises provides_role_info
    class TestProv(GroupProvider):
        def __init__(self):
            self._capabilities = ProviderCapabilities(provides_role_info=True)
            # Skip circuit breaker init for test provider
            self._circuit_breaker = None

        @property
        def capabilities(self):
            return self._capabilities

        # Implement the new _*_impl methods (circuit breaker interface)
        def _add_member_impl(
            self, group_key: str, member_data, justification: str
        ) -> OperationResult:
            return OperationResult.success(data={"result": {}})

        def _remove_member_impl(
            self, group_key: str, member_data, justification: str
        ) -> OperationResult:
            return OperationResult.success(data={"result": {}})

        def _get_group_members_impl(self, group_key: str, **kwargs) -> OperationResult:
            return OperationResult.success(data={"members": []})

        def _list_groups_impl(self, **kwargs) -> OperationResult:
            # return a group that includes a role field to satisfy role-aware contract
            return OperationResult.success(
                data={"groups": [{"id": "eng", "role": "MANAGER"}]}
            )

        def _list_groups_with_members_impl(self, **kwargs) -> OperationResult:
            return OperationResult.success(data={"groups": []})

        def validate_permissions(
            self, user_key: str, group_key: str, action: str
        ) -> OperationResult:
            return OperationResult.success(data={"allowed": True})

        def list_groups_for_user(self, user_key: str) -> OperationResult:
            return OperationResult.success(
                data={"groups": [{"id": "eng", "role": "MANAGER"}]}
            )

    prov = TestProv()
    assert prov.capabilities.provides_role_info is True

    res = prov.list_groups_for_user("alice")
    assert res.status == OperationStatus.SUCCESS
    assert isinstance(res.data, dict)
    groups = res.data.get("groups")
    assert isinstance(groups, list)
    assert groups and "role" in groups[0]
