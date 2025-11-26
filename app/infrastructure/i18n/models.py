"""Translation models for i18n system.

Defines core data structures for managing translations and locales.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Locale(str, Enum):
    """Supported locale identifiers.

    Uses IETF BCP 47 language tag format (e.g., en-US, fr-FR).
    """

    EN_US = "en-US"
    FR_FR = "fr-FR"

    @classmethod
    def from_string(cls, locale_str: str) -> "Locale":
        """Convert string to Locale enum.

        Args:
            locale_str: Locale string (e.g., "en-US", "fr-FR").

        Returns:
            Matching Locale enum value.

        Raises:
            ValueError: If locale string is not supported.
        """
        try:
            return cls(locale_str)
        except ValueError as e:
            raise ValueError(f"Unsupported locale: {locale_str}") from e

    @property
    def language(self) -> str:
        """Get language part of locale (e.g., "en" from "en-US").

        Returns:
            Language code.
        """
        return self.value.split("-")[0]

    @property
    def region(self) -> str:
        """Get region part of locale (e.g., "US" from "en-US").

        Returns:
            Region code.
        """
        parts = self.value.split("-")
        return parts[1] if len(parts) > 1 else ""


@dataclass(frozen=True)
class TranslationKey:
    """Represents a translation key for accessing translated messages.

    Keys are hierarchical (e.g., "incident.created", "role.invalid_name").
    Frozen to ensure immutability and hashability for caching.

    Attributes:
        namespace: Top-level namespace (e.g., "incident", "role", "secret").
        message_key: Specific message identifier (e.g., "created", "invalid_name").
    """

    namespace: str
    message_key: str

    def __str__(self) -> str:
        """Return full dot-separated key path.

        Returns:
            Full key (e.g., "incident.created").
        """
        return f"{self.namespace}.{self.message_key}"

    @classmethod
    def from_string(cls, key_string: str) -> "TranslationKey":
        """Create TranslationKey from dot-separated string.

        Args:
            key_string: Dot-separated key (e.g., "incident.created").

        Returns:
            TranslationKey instance.

        Raises:
            ValueError: If key_string does not contain exactly one dot.
        """
        parts = key_string.split(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Translation key must be in format 'namespace.key': {key_string}"
            )
        return cls(namespace=parts[0], message_key=parts[1])


@dataclass
class TranslationCatalog:
    """Container for translations in a specific locale.

    Stores all translation messages for a single locale, organized by namespace.

    Attributes:
        locale: The Locale this catalog is for.
        messages: Nested dict structure {namespace: {key: message_string}}.
        loaded_at: Timestamp (ISO 8601) when translations were loaded.
    """

    locale: Locale
    messages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    loaded_at: Optional[str] = None

    def get_message(self, key: TranslationKey) -> Optional[str]:
        """Retrieve a translation message by key.

        Args:
            key: TranslationKey with namespace and message_key.

        Returns:
            Translated message string, or None if not found.
        """
        namespace_dict = self.messages.get(key.namespace, {})
        return namespace_dict.get(key.message_key)

    def set_message(self, key: TranslationKey, message: str) -> None:
        """Set a translation message.

        Args:
            key: TranslationKey with namespace and message_key.
            message: Translated message string.
        """
        if key.namespace not in self.messages:
            self.messages[key.namespace] = {}
        self.messages[key.namespace][key.message_key] = message

    def has_message(self, key: TranslationKey) -> bool:
        """Check if translation exists for given key.

        Args:
            key: TranslationKey to check.

        Returns:
            True if message exists, False otherwise.
        """
        return key.message_key in self.get_namespace(key.namespace)

    def get_namespace(self, namespace: str) -> Dict[str, Any]:
        """Get all messages for a specific namespace.

        Args:
            namespace: Namespace identifier (e.g., "incident").

        Returns:
            Dictionary of all messages in namespace.
        """
        return self.messages.get(namespace, {})

    def merge(self, other: "TranslationCatalog") -> None:
        """Merge another catalog into this one.

        Later entries override earlier ones.

        Args:
            other: TranslationCatalog to merge.
        """
        for namespace, messages in other.messages.items():
            if namespace not in self.messages:
                self.messages[namespace] = {}
            self.messages[namespace].update(messages)


@dataclass
class LocaleResolutionContext:
    """Context for resolving the appropriate locale for an operation.

    Attributes:
        requested_locale: User-requested locale (if any).
        user_locale: User's preferred locale (if any).
        default_locale: Fallback locale (usually en-US).
        supported_locales: List of locales supported by the system.
    """

    requested_locale: Optional[Locale] = None
    user_locale: Optional[Locale] = None
    default_locale: Locale = Locale.EN_US
    supported_locales: Optional[list] = field(
        default_factory=lambda: [Locale.EN_US, Locale.FR_FR]
    )

    def resolve(self) -> Locale:
        """Resolve the best matching locale from available options.

        Resolution order:
        1. Requested locale (if supported)
        2. User locale (if supported)
        3. Default locale

        Returns:
            Resolved Locale.
        """
        if self.requested_locale and self.requested_locale in (
            self.supported_locales or []
        ):
            return self.requested_locale
        if self.user_locale and self.user_locale in (self.supported_locales or []):
            return self.user_locale
        return self.default_locale
