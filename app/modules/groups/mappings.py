"""Provider-aware mapping helpers for primary/secondary group id conversions.

These helpers consult the active provider instances (via the provider
registry) for deterministic prefix resolution. They expect the providers
to have been activated during application startup.

Primary provider groups follow a naming pattern: optionally a prefix for a third-party
integration followed by a dash and the canonical group name.

Examples:
- "aws-my-service-admins" -> prefix="aws", canonical="my-service-admins"
- "my-service-admins" -> prefix=None, canonical="my-service-admins"

"""

from __future__ import annotations

from typing import Optional, Dict, Iterable, Mapping, Tuple, List

from core.logging import get_module_logger
from modules.groups.providers import (
    get_active_providers,
    get_primary_provider_name,
)
from modules.groups.schemas import NormalizedMember, NormalizedGroup, GroupsMap

logger = get_module_logger()


def _local_name_from_primary(primary_name: str) -> str:
    """Extract the local name segment from a primary group identifier.

    If the primary group is an email (contains @), use the local part.
    """
    if not primary_name:
        return ""
    if "@" in primary_name:
        return primary_name.split("@", 1)[0]
    return primary_name


def _ensure_providers_activated(
    provider_registry: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    """Return a provider registry. If none provided, fall back to active providers.

    Raises RuntimeError if no providers are available.
    """
    provs = (
        provider_registry if provider_registry is not None else get_active_providers()
    )
    if not provs:
        raise RuntimeError(
            "Providers not activated. Call activate_providers() during app startup or pass a provider_registry."
        )
    return dict(provs)


def parse_primary_group_name(
    primary_group_name: str, *, provider_registry: Optional[Mapping[str, object]] = None
) -> Dict[str, Optional[str]]:
    """Return {'prefix': Optional[str], 'canonical': str}.

    If `provider_registry` is provided, it is used to build a deterministic
    mapping of provider prefixes. The function prefers the `prefix` attribute
    on provider instances; if absent the provider's registered name is used as
    the effective prefix.
    """
    name = _local_name_from_primary(primary_group_name).strip()
    if not name:
        raise ValueError("primary_group_name is required")

    provs = _ensure_providers_activated(provider_registry)

    # Build deterministic prefix -> [provider_name] mapping
    prefix_map: Dict[str, list] = {}
    for provider_name in sorted(provs.keys()):
        inst = provs[provider_name]
        p = getattr(inst, "prefix", None) or provider_name
        if p:
            prefix_map.setdefault(p, []).append(provider_name)

    # Try to match longest prefix first (stable deterministic ordering)
    for prefix in sorted(prefix_map.keys(), key=lambda s: -len(s)):
        # Common separator conventions: ':', '/', '-'
        for sep in (":", "/", "-"):
            token = prefix + sep
            if name.startswith(token):
                canonical = name[len(token) :]
                return {"prefix": prefix, "canonical": canonical}
    # No prefix matched
    return {"prefix": None, "canonical": name}


def map_provider_group_id(
    from_provider: str,
    from_group_id: str,
    to_provider: str,
    *,
    provider_registry: Optional[Mapping[str, object]] = None,
) -> str:
    """Map a group id between providers from `from_provider` to `to_provider`.

    Rules:
    - If same provider, return input unchanged.
    - If mapping TO primary provider: compose using source provider's prefix.
    - Otherwise mapping to non-primary provider: use canonical name.

    Callers may pass a
    `provider_registry` mapping for deterministic prefix resolution. If not
    provided the function falls back to the active providers.
    """
    if not from_provider or not to_provider or not from_group_id:
        raise ValueError("from_provider, to_provider and from_group_id are required")

    provs = _ensure_providers_activated(provider_registry)
    primary = get_primary_provider_name()

    # Short-circuit same-provider mapping
    if from_provider == to_provider:
        return from_group_id

    # Derive canonical name if input might be primary-style
    canonical = from_group_id
    if from_provider == primary:
        parsed = parse_primary_group_name(from_group_id, provider_registry=provs)
        canonical = parsed.get("canonical") or canonical

    # If target is primary, compose primary group name using source provider's prefix
    if to_provider == primary:
        src_inst = provs.get(from_provider)
        if not src_inst:
            raise ValueError(f"Unknown source provider: {from_provider}")
        prefix = getattr(src_inst, "prefix", from_provider)
        # Use '-' as canonical separator
        return f"{prefix}-{canonical}"

    # Mapping to non-primary provider: return canonical name by convention
    return canonical


def primary_group_to_canonical(
    primary_group_name: str, prefixes: Optional[Iterable[str]] = None
) -> str:
    """Return the canonical group name for a given primary provider group identifier.

    If `prefixes` is provided, it will be used to detect and strip a known
    provider prefix from the primary-style name. If not provided the input is
    treated as canonical (except for email local-part extraction handled by
    `_local_name_from_primary`).
    """
    if not primary_group_name:
        return ""

    name = _local_name_from_primary(primary_group_name).strip()
    if not name:
        return ""

    if not prefixes:
        return name

    # Try to match the longest prefix first to avoid ambiguous shorter matches
    sorted_prefixes = sorted({p for p in prefixes if p}, key=len, reverse=True)
    for p in sorted_prefixes:
        if name.startswith(f"{p}-"):
            return name[len(p) + 1 :]
    return name


def canonical_to_primary_group(
    canonical_name: str, prefix: Optional[str] = None
) -> str:
    """Compose a primary provider group name from a canonical name and optional prefix."""
    if not canonical_name:
        return ""
    if prefix:
        return f"{prefix}-{canonical_name}"
    return canonical_name


def _extract_prefixes_from_registry(
    provider_registry: Mapping[str, Mapping[str, str]],
) -> Tuple[Dict[str, str], Iterable[str]]:
    """Build helper maps from provider registry.

    Returns a tuple (provider_to_prefix, prefixes_iterable).
    The effective prefix for a provider is provider_registry[provider].get('prefix')
    if present, otherwise the provider's registered name.
    """
    provider_to_prefix: Dict[str, str] = {}
    prefixes = []
    for prov, cfg in (provider_registry or {}).items():
        if isinstance(cfg, Mapping):
            p = cfg.get("prefix") or prov
        else:
            p = prov
        provider_to_prefix[prov] = p
        prefixes.append(p)
    return provider_to_prefix, prefixes


def map_secondary_to_primary_group(
    secondary_provider: str, secondary_group_id: str
) -> str:
    """Map secondary provider's group ID to primary provider's equivalent.

    Uses `mappings.py` helpers to translate between provider-specific
    group ID formats.

    Args:
        secondary_provider: Name of secondary provider (e.g., 'aws', 'google')
        secondary_group_id: Group ID in secondary provider format

    Returns:
        Group ID in primary provider format

    Raises:
        ValueError: If mapping cannot be performed
    """
    primary_provider_name = get_primary_provider_name()

    try:
        primary_group_id = map_provider_group_id(
            from_provider=secondary_provider,
            from_group_id=secondary_group_id,
            to_provider=primary_provider_name,
        )
        logger.info(
            "group_mapping_secondary_to_primary",
            from_provider=secondary_provider,
            from_id=secondary_group_id,
            to_id=primary_group_id,
        )
        return primary_group_id
    except Exception as e:
        logger.error(
            "group_mapping_failed",
            from_provider=secondary_provider,
            from_id=secondary_group_id,
            error=str(e),
        )
        raise ValueError(
            f"Cannot map {secondary_provider} group '{secondary_group_id}' to {primary_provider_name}: {e}"
        ) from e


def map_primary_to_secondary_group(
    primary_group_id: str, secondary_provider: str
) -> str:
    """Map primary provider's group ID to secondary provider's equivalent.

    Reverse mapping for propagation: used when executing operations on secondary providers.

    Args:
        primary_group_id: Group ID in primary provider format
        secondary_provider: Name of secondary provider to map to

    Returns:
        Group ID in secondary provider format

    Raises:
        ValueError: If mapping cannot be performed
    """
    primary_provider_name = get_primary_provider_name()

    try:
        secondary_group_id = map_provider_group_id(
            from_provider=primary_provider_name,
            from_group_id=primary_group_id,
            to_provider=secondary_provider,
        )
        logger.info(
            "group_mapping_primary_to_secondary",
            from_id=primary_group_id,
            to_provider=secondary_provider,
            to_id=secondary_group_id,
        )
        return secondary_group_id
    except Exception as e:
        logger.error(
            "group_mapping_failed",
            from_id=primary_group_id,
            to_provider=secondary_provider,
            error=str(e),
        )
        raise ValueError(
            f"Cannot map {primary_provider_name} group '{primary_group_id}' to {secondary_provider}: {e}"
        ) from e


def normalize_member_for_provider(
    member_email: str, provider_type: str
) -> NormalizedMember:
    """Convert email address to provider-specific NormalizedMember.

    Each provider may have different member identifier requirements.
    This function normalizes the input to what the provider expects.

    Args:
        member_email: Email address of member
        provider_type: Name of provider

    Returns:
        NormalizedMember instance ready for provider API call

    Raises:
        ValueError: If email is invalid or provider unknown
    """
    if not member_email or "@" not in member_email:
        raise ValueError(f"Invalid email: {member_email}")

    # All providers currently use email-only normalization
    # Future: extend this to provider-specific logic as needed
    # Use provider_type in a debug log to avoid unused-argument lint warnings
    logger.debug("normalize_member_for_provider", provider=provider_type)
    return NormalizedMember(
        email=member_email,
        id=None,
        role=None,
        provider_member_id=None,
        raw=None,
    )


def map_normalized_groups_list_to_providers(groups: List[NormalizedGroup]) -> GroupsMap:
    """Deprecated: use map_normalized_groups_to_providers instead."""
    return map_normalized_groups_to_providers(groups, associate=False)


def map_normalized_groups_list_to_providers_with_association(
    groups: List[NormalizedGroup],
    provider_registry: Optional[Mapping[str, object]] = None,
) -> GroupsMap:
    """Deprecated: use map_normalized_groups_to_providers instead."""
    return map_normalized_groups_to_providers(
        groups, associate=True, provider_registry=provider_registry
    )


def map_normalized_groups_to_providers(
    groups: List[NormalizedGroup],
    *,
    associate: bool = False,
    provider_registry: Optional[Mapping[str, object]] = None,
) -> GroupsMap:
    """Map a list of NormalizedGroup to a dict by provider.
    When `associate` is True the function will attempt to detect primary-style
    group names (prefix-canonical) and associate them to a resolved provider
    using `provider_registry` (or active providers if not provided). When a
    resolved provider is found the group's `provider` attribute/key will be
    updated (best-effort) and the group will be grouped under that provider.

    Args:
        groups: List of NormalizedGroup instances (can be dict-like or objects).
        associate: If True, attempt prefix-based provider association.
        provider_registry: Optional mapping of provider_name -> provider instance
            used for deterministic prefix resolution when `associate` is True.

    Returns:
        Dict mapping provider name → list of NormalizedGroup for that provider.
    """
    provider_map: Dict[str, List[NormalizedGroup]] = {}

    # Prepare association helpers only when needed
    provs = None
    prefix_to_provider: Optional[Dict[str, str]] = None
    if associate:
        provs = _ensure_providers_activated(provider_registry)
        # Build prefix -> provider_name map deterministically
        prefix_to_provider = {
            (getattr(provs[p], "prefix", p) or p): p for p in sorted(provs.keys())
        }

    for group in groups:
        # Candidate primary-style identifier (id or name)
        primary_name = None
        if isinstance(group, dict):
            primary_name = group.get("id") or group.get("name")
        else:
            primary_name = getattr(group, "id", None) or getattr(group, "name", None)

        # Attempt to resolve a provider from a primary-style name when asked
        if associate and primary_name:
            try:
                parsed = parse_primary_group_name(primary_name, provider_registry=provs)
            except ValueError:
                parsed = None

            if parsed:
                prefix = parsed.get("prefix")
                if prefix and prefix_to_provider:
                    resolved_provider = prefix_to_provider.get(prefix)
                else:
                    resolved_provider = None
            else:
                resolved_provider = None

            # apply resolved provider when available (best-effort)
            if resolved_provider:
                if isinstance(group, dict):
                    group["provider"] = resolved_provider
                else:
                    try:
                        setattr(group, "provider", resolved_provider)
                    except (AttributeError, TypeError):
                        logger.debug(
                            "provider_mutation_failed", group=str(primary_name)
                        )

        # Read provider from group (dict or attribute)
        provider = (
            group.get("provider")
            if isinstance(group, dict)
            else getattr(group, "provider", None)
        )
        provider = provider or "unknown"
        provider_map.setdefault(provider, []).append(group)

    return provider_map
