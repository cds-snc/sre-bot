from modules.groups.schemas import NormalizedMember
from modules.groups.providers.base import ProviderCapabilities


def test_get_primary_provider_is_primary_type(safe_providers_import):
    mod = safe_providers_import

    # start with a clean registry
    mod.PROVIDER_REGISTRY.clear()

    from modules.groups.providers.base import (
        PrimaryGroupProvider,
        OperationResult,
        OperationStatus,
    )

    # minimal concrete primary provider implementation
    class DummyPrimary(PrimaryGroupProvider):
        def __init__(self):
            # advertise role info as required for primaries
            self._capabilities = ProviderCapabilities(provides_role_info=True)

        @property
        def capabilities(self):
            return self._capabilities

        def get_group_members(self, group_key: str, **kwargs) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def add_member(
            self, group_key: str, member_data, justification: str
        ) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def remove_member(
            self, group_key: str, member_data, justification: str
        ) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def list_groups_for_user(self, user_key: str) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def validate_permissions(
            self, user_key: str, group_key: str, action: str
        ) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def is_manager(self, user_key: str, group_key: str) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def create_user(self, user_data: "NormalizedMember") -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def delete_user(self, user_key: str) -> OperationResult:
            return OperationResult(status=OperationStatus.SUCCESS, message="ok")

        def list_groups(self, **kwargs) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

        def list_groups_with_members(self, **kwargs) -> OperationResult:
            return OperationResult(
                status=OperationStatus.SUCCESS, message="ok", data={}
            )

    # Configure settings so the registry will accept/recognize primary
    import core.config as core_config

    core_config.settings.groups.providers.clear()
    core_config.settings.groups.providers.update(
        {"dummy": {"primary": True, "prefix": "p", "enabled": True}}
    )

    # Register our DummyPrimary as the provider named "dummy"
    mod.register_provider("dummy")(DummyPrimary)
    # Activate so the provider is instantiated (new contract requires explicit activation)
    mod.activate_providers()

    # Now assert get_primary_provider() returns an instance of PrimaryGroupProvider
    prov = mod.get_primary_provider()
    assert isinstance(prov, PrimaryGroupProvider)
