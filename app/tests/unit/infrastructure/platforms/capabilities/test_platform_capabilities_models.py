"""Unit tests for platform capability models."""

import pytest

from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    PlatformFeatureType,
    PLATFORM_SLACK,
    PLATFORM_TEAMS,
    PLATFORM_DISCORD,
    PLATFORM_API,
    create_capability_declaration,
)


@pytest.mark.unit
class TestPlatformCapability:
    """Test PlatformCapability enum."""

    def test_all_capability_values_exist(self):
        """Test that all expected capabilities are defined."""
        expected = {
            "COMMANDS",
            "HIERARCHICAL_TEXT_COMMANDS",
            "STRUCTURED_COMMANDS",
            "VIEWS_MODALS",
            "INTERACTIVE_CARDS",
            "MESSAGING",
            "MESSAGE_ACTIONS",
            "FILE_SHARING",
            "WORKFLOWS",
            "PRESENCE",
            "REACTIONS",
            "THREADS",
        }
        actual = {cap.name for cap in PlatformCapability}
        assert actual == expected

    def test_capability_string_values(self):
        """Test that enum string values match expected format."""
        assert PlatformCapability.COMMANDS.value == "commands"
        assert PlatformCapability.VIEWS_MODALS.value == "views_modals"
        assert PlatformCapability.INTERACTIVE_CARDS.value == "interactive_cards"
        assert PlatformCapability.MESSAGING.value == "messaging"

    def test_capability_is_string_enum(self):
        """Test that capabilities are string enum values."""
        assert isinstance(PlatformCapability.COMMANDS.value, str)
        assert PlatformCapability.COMMANDS == "commands"


@pytest.mark.unit
class TestPlatformFeatureType:
    """Test PlatformFeatureType enum."""

    def test_all_feature_types_exist(self):
        """Test that all expected feature types are defined."""
        expected = {
            "COMMAND_HANDLER",
            "VIEW_HANDLER",
            "BUTTON_HANDLER",
            "MESSAGE_ACTION_HANDLER",
            "EVENT_LISTENER",
        }
        actual = {ft.name for ft in PlatformFeatureType}
        assert actual == expected

    def test_feature_type_string_values(self):
        """Test that feature type string values match expected format."""
        assert PlatformFeatureType.COMMAND_HANDLER.value == "command_handler"
        assert PlatformFeatureType.VIEW_HANDLER.value == "view_handler"


@pytest.mark.unit
class TestPlatformConstants:
    """Test platform identifier constants."""

    def test_platform_constants_exist(self):
        """Test that all platform constants are defined."""
        assert PLATFORM_SLACK == "slack"
        assert PLATFORM_TEAMS == "teams"
        assert PLATFORM_DISCORD == "discord"
        assert PLATFORM_API == "api"


@pytest.mark.unit
class TestCapabilityDeclaration:
    """Test CapabilityDeclaration dataclass."""

    def test_create_capability_declaration(self):
        """Test creating a CapabilityDeclaration."""
        capabilities = frozenset(
            [
                PlatformCapability.COMMANDS,
                PlatformCapability.MESSAGING,
            ]
        )
        decl = CapabilityDeclaration(
            platform_id=PLATFORM_SLACK,
            capabilities=capabilities,
        )

        assert decl.platform_id == PLATFORM_SLACK
        assert decl.capabilities == capabilities
        assert decl.metadata == {}

    def test_capability_declaration_with_metadata(self):
        """Test CapabilityDeclaration with metadata."""
        metadata = {"version": "1.0.0", "author": "SRE Team"}
        decl = CapabilityDeclaration(
            platform_id=PLATFORM_TEAMS,
            capabilities=frozenset([PlatformCapability.COMMANDS]),
            metadata=metadata,
        )

        assert decl.metadata == metadata
        assert decl.metadata["version"] == "1.0.0"

    def test_capability_declaration_is_frozen(self):
        """Test that CapabilityDeclaration is immutable."""
        decl = CapabilityDeclaration(
            platform_id=PLATFORM_SLACK,
            capabilities=frozenset([PlatformCapability.COMMANDS]),
        )

        with pytest.raises(AttributeError):
            decl.platform_id = "new_platform"  # type: ignore

    def test_supports_single_capability(self):
        """Test supports() method with single capability."""
        decl = CapabilityDeclaration(
            platform_id=PLATFORM_SLACK,
            capabilities=frozenset(
                [
                    PlatformCapability.COMMANDS,
                    PlatformCapability.MESSAGING,
                ]
            ),
        )

        assert decl.supports(PlatformCapability.COMMANDS) is True
        assert decl.supports(PlatformCapability.MESSAGING) is True
        assert decl.supports(PlatformCapability.VIEWS_MODALS) is False

    def test_supports_all_capabilities(self):
        """Test supports_all() method."""
        decl = CapabilityDeclaration(
            platform_id=PLATFORM_SLACK,
            capabilities=frozenset(
                [
                    PlatformCapability.COMMANDS,
                    PlatformCapability.MESSAGING,
                    PlatformCapability.INTERACTIVE_CARDS,
                ]
            ),
        )

        assert (
            decl.supports_all(
                PlatformCapability.COMMANDS,
                PlatformCapability.MESSAGING,
            )
            is True
        )

        assert (
            decl.supports_all(
                PlatformCapability.COMMANDS,
                PlatformCapability.VIEWS_MODALS,  # Not supported
            )
            is False
        )

    def test_supports_any_capability(self):
        """Test supports_any() method."""
        decl = CapabilityDeclaration(
            platform_id=PLATFORM_SLACK,
            capabilities=frozenset([PlatformCapability.COMMANDS]),
        )

        assert (
            decl.supports_any(
                PlatformCapability.COMMANDS,
                PlatformCapability.MESSAGING,
            )
            is True
        )

        assert (
            decl.supports_any(
                PlatformCapability.VIEWS_MODALS,
                PlatformCapability.WORKFLOWS,
            )
            is False
        )

    def test_empty_capabilities(self):
        """Test declaration with no capabilities."""
        decl = CapabilityDeclaration(
            platform_id=PLATFORM_API,
            capabilities=frozenset(),
        )

        assert len(decl.capabilities) == 0
        assert decl.supports(PlatformCapability.COMMANDS) is False
        assert decl.supports_all() is True  # Vacuous truth
        assert decl.supports_any() is False


@pytest.mark.unit
class TestCreateCapabilityDeclaration:
    """Test create_capability_declaration factory function."""

    def test_create_with_single_capability(self):
        """Test factory with single capability."""
        decl = create_capability_declaration(
            PLATFORM_SLACK,
            PlatformCapability.COMMANDS,
        )

        assert decl.platform_id == PLATFORM_SLACK
        assert decl.capabilities == frozenset([PlatformCapability.COMMANDS])
        assert decl.metadata == {}

    def test_create_with_multiple_capabilities(self):
        """Test factory with multiple capabilities."""
        decl = create_capability_declaration(
            PLATFORM_TEAMS,
            PlatformCapability.COMMANDS,
            PlatformCapability.MESSAGING,
            PlatformCapability.INTERACTIVE_CARDS,
        )

        assert len(decl.capabilities) == 3
        assert PlatformCapability.COMMANDS in decl.capabilities
        assert PlatformCapability.MESSAGING in decl.capabilities
        assert PlatformCapability.INTERACTIVE_CARDS in decl.capabilities

    def test_create_with_metadata(self):
        """Test factory with metadata."""
        metadata = {"version": "2.0.0", "sdk": "bolt"}
        decl = create_capability_declaration(
            PLATFORM_SLACK,
            PlatformCapability.COMMANDS,
            metadata=metadata,
        )

        assert decl.metadata == metadata

    def test_create_with_no_capabilities(self):
        """Test factory with no capabilities."""
        decl = create_capability_declaration(PLATFORM_API)

        assert decl.platform_id == PLATFORM_API
        assert len(decl.capabilities) == 0

    def test_factory_returns_frozen_set(self):
        """Test that factory returns immutable frozenset for capabilities."""
        decl = create_capability_declaration(
            PLATFORM_DISCORD,
            PlatformCapability.COMMANDS,
            PlatformCapability.MESSAGING,
        )

        assert isinstance(decl.capabilities, frozenset)

    def test_duplicate_capabilities_are_deduplicated(self):
        """Test that duplicate capabilities are handled by frozenset."""
        decl = create_capability_declaration(
            PLATFORM_SLACK,
            PlatformCapability.COMMANDS,
            PlatformCapability.COMMANDS,  # Duplicate
            PlatformCapability.MESSAGING,
        )

        # frozenset automatically deduplicates
        assert len(decl.capabilities) == 2
        assert PlatformCapability.COMMANDS in decl.capabilities
        assert PlatformCapability.MESSAGING in decl.capabilities
