"""Access Sync policy models and planning engine.

This is the single source of truth for all entitlement classification,
authn-mode semantics, and action planning.  Adapters must not duplicate
any of this logic.
"""

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Dict, List, Literal, Optional, Set


EntitlementMode = Literal["sync_managed", "ephemeral", "deactivated"]
EntitlementStrategyKind = Literal[
    "none",
    "explicit_rules_only",
    "default_prefix",
    "pattern_map",
]


@dataclass(frozen=True)
class EntitlementRule:
    """Mapping from an IDP security group slug to a platform entitlement.

    mode:
      'sync_managed' - entitlement is always applied/removed by Access Sync.
      'ephemeral'    - entitlement is managed by Privileged Access; Access Sync
                       skips it during reconciliation so active grants are not
                       revoked.
      'deactivated'  - all SRE Bot automation is suspended for this group.
                       Access Sync skips apply/remove.  Privileged Access refuses
                       new grants.  Access Requests rejects intake.  Current
                       platform entitlement state is frozen until the override is
                       removed or expires.

    Mode is evaluated per rule, so a single platform policy can mix all three
    values across different entitlement groups.
    """

    group_slug: str
    entitlement_type: str
    entitlement_id: str
    mode: EntitlementMode = "sync_managed"


@dataclass(frozen=True)
class PatternEntitlementMapping:
    """Map source-group wildcard patterns to one platform entitlement."""

    source_group_pattern: str
    entitlement_type: str
    entitlement_id: str
    mode: EntitlementMode = "sync_managed"


@dataclass(frozen=True)
class DefaultEntitlementStrategy:
    """Platform-level default discovery and mapping strategy.

    kind:
      'none'                - no entitlements for this platform.
      'explicit_rules_only' - only explicit EntitlementRule entries are used.
      'default_prefix'      - groups matching source_group_prefix map to a default
                              entitlement shape using entitlement_id_template.
      'pattern_map'         - groups are matched against pattern_mappings.
    """

    kind: EntitlementStrategyKind = "explicit_rules_only"
    source_group_prefix: str = ""
    exclude_group_slugs: List[str] = field(default_factory=list)
    default_entitlement_type: str = "group"
    entitlement_id_template: str = "{token}"
    mode: EntitlementMode = "sync_managed"
    pattern_mappings: List[PatternEntitlementMapping] = field(default_factory=list)

    def applies_to_group(self, group_slug: str) -> bool:
        """Return True when the strategy should consider *group_slug*."""
        normalized = group_slug.strip().lower()
        if normalized in {
            slug.strip().lower() for slug in self.exclude_group_slugs if slug
        }:
            return False

        if self.kind == "default_prefix":
            prefix = self.source_group_prefix.strip().lower()
            return bool(prefix) and normalized.startswith(prefix)

        if self.kind == "pattern_map":
            return any(
                fnmatch(normalized, mapping.source_group_pattern.strip().lower())
                for mapping in self.pattern_mappings
                if mapping.source_group_pattern
            )

        return False

    def build_rule_for_group(self, group_slug: str) -> Optional[EntitlementRule]:
        """Build a default rule candidate for *group_slug* when configured."""
        normalized = group_slug.strip().lower()
        if not normalized:
            return None

        if self.kind == "default_prefix":
            prefix = self.source_group_prefix.strip().lower()
            if not prefix or not normalized.startswith(prefix):
                return None
            token = normalized[len(prefix) :]
            if not token:
                return None
            entitlement_id = self.entitlement_id_template.replace("{token}", token)
            if not entitlement_id:
                return None
            return EntitlementRule(
                group_slug=normalized,
                entitlement_type=self.default_entitlement_type,
                entitlement_id=entitlement_id,
                mode=self.mode,
            )

        if self.kind == "pattern_map":
            for mapping in self.pattern_mappings:
                pattern = mapping.source_group_pattern.strip().lower()
                if not pattern:
                    continue
                if fnmatch(normalized, pattern):
                    return EntitlementRule(
                        group_slug=normalized,
                        entitlement_type=mapping.entitlement_type,
                        entitlement_id=mapping.entitlement_id,
                        mode=mapping.mode,
                    )

        return None


@dataclass(frozen=True)
class PlatformPolicy:
    """Policy for a single target platform.

    authn_mode:
      'direct'  - operators typically manage access via direct membership in
                  sg-<platform>-authn.
      'derived' - operators typically nest entitlement groups into
                  sg-<platform>-authn and manage access through those groups.

    In both modes, effective membership in sg-<platform>-authn (direct or
    indirect) is the authoritative source of truth for whether a user should
    retain platform access.

    authn_removal_mode:
      'disable'           - deactivate user account on the platform.
      'delete'            - remove user from the platform entirely.
      'entitlement_only'  - remove only managed entitlements; authn account is
                            left intact (manual follow-up required if the platform
                            cannot automate account removal).
    """

    platform: str
    authn_group_slug: str  # e.g. "sg-aws-authn"
    authn_mode: str  # direct | derived
    authn_removal_mode: str  # disable | delete | entitlement_only
    entitlement_rules: List[EntitlementRule]
    default_entitlement_strategy: Optional[DefaultEntitlementStrategy] = None

    def effective_rules(
        self,
        discovered_group_slugs: Optional[Set[str]] = None,
    ) -> List[EntitlementRule]:
        """Return explicit rules plus strategy-generated defaults.

        Explicit rules always win over strategy-generated candidates for the
        same source group slug.
        """
        explicit_by_slug: Dict[str, EntitlementRule] = {
            rule.group_slug.strip().lower(): rule
            for rule in self.entitlement_rules
            if rule.group_slug
        }

        if not discovered_group_slugs:
            return list(self.entitlement_rules)

        strategy = self.default_entitlement_strategy
        if strategy is None or strategy.kind in {"none", "explicit_rules_only"}:
            return list(self.entitlement_rules)

        generated: List[EntitlementRule] = []
        for slug in sorted(group_slug.lower() for group_slug in discovered_group_slugs):
            if slug == self.authn_group_slug.lower():
                continue
            if slug in explicit_by_slug:
                continue
            if not strategy.applies_to_group(slug):
                continue
            rule = strategy.build_rule_for_group(slug)
            if rule is not None:
                generated.append(rule)

        return list(self.entitlement_rules) + generated

    def sync_managed_rules(
        self,
        discovered_group_slugs: Optional[Set[str]] = None,
    ) -> List[EntitlementRule]:
        """Return only rules that Access Sync is responsible for."""
        return [
            rule
            for rule in self.effective_rules(discovered_group_slugs)
            if rule.mode == "sync_managed"
        ]

    def ephemeral_entitlement_ids(self) -> Set[str]:
        """Return entitlement IDs that must be skipped during reconciliation (Privileged Access owns them)."""
        return {
            r.entitlement_id for r in self.entitlement_rules if r.mode == "ephemeral"
        }

    def deactivated_entitlement_ids(self) -> Set[str]:
        """Return entitlement IDs where all SRE Bot automation is suspended."""
        return {
            r.entitlement_id for r in self.entitlement_rules if r.mode == "deactivated"
        }

    def skip_entitlement_ids(self) -> Set[str]:
        """Return all entitlement IDs Access Sync must not touch (ephemeral + deactivated)."""
        return self.ephemeral_entitlement_ids() | self.deactivated_entitlement_ids()


@dataclass
class PolicyRegistry:
    """Registry of per-platform policies.

    Mutable so that Privileged Access can register ephemeral entitlements at
    startup via the hookimpl plugin system.
    """

    policies: Dict[str, PlatformPolicy] = field(default_factory=dict)

    def register_ephemeral_entitlement(
        self,
        platform: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> None:
        """Register an entitlement as ephemeral (sync-exempt).

        Called by Privileged Access at startup so Access Sync skips those
        entitlements during reconciliation.
        """
        policy = self.policies.get(platform)
        if policy is None:
            return
        rule = EntitlementRule(
            group_slug="",
            entitlement_type=entitlement_type,
            entitlement_id=entitlement_id,
            mode="ephemeral",
        )
        # PlatformPolicy is frozen; rebuild with the new rule appended.
        updated = PlatformPolicy(
            platform=policy.platform,
            authn_group_slug=policy.authn_group_slug,
            authn_mode=policy.authn_mode,
            authn_removal_mode=policy.authn_removal_mode,
            entitlement_rules=list(policy.entitlement_rules) + [rule],
        )
        self.policies[platform] = updated


@dataclass(frozen=True)
class AdapterCapabilities:
    """Execution capabilities declared by a platform adapter.

    The PolicyEngine uses these to select compatible planned actions.
    """

    supports_disable: bool
    supports_delete: bool
    supported_entitlement_types: Set[str]
    supports_bulk_user_delta: bool = False


@dataclass(frozen=True)
class PlannedAction:
    """A single normalized action produced by the PolicyEngine."""

    action: Literal[
        "ensure_user",
        "disable_user",
        "remove_user",
        "apply_entitlement",
        "remove_entitlement",
    ]
    entitlement_type: Optional[str] = None
    entitlement_id: Optional[str] = None


class PolicyEngine:
    """Converts policy + current state into a normalized list of planned actions.

    This class is the single place where policy semantics are interpreted.
    Adapters receive planned actions and execute them — they never re-implement
    policy logic.
    """

    def plan_actions(
        self,
        policy: PlatformPolicy,
        capabilities: AdapterCapabilities,
        user_should_exist: bool,
        required_entitlements: List[EntitlementRule],
        current_entitlement_ids: Optional[Set[str]] = None,
    ) -> List[PlannedAction]:
        """Produce the minimal set of actions needed to converge to desired state.

        Args:
            policy: Platform policy containing authn/removal modes.
            capabilities: Adapter execution capabilities.
            user_should_exist: True when authn-group membership indicates the user
                should retain platform access.
            required_entitlements: sync_managed rules *for which the user is an
                effective IDP group member*.  Caller resolves membership before
                passing this list — do not pass all rules unconditionally.
            current_entitlement_ids: Set of entitlement IDs the user currently
                holds on the target platform (from adapter.get_current_entitlement_ids).
                Used to compute removals.  Pass ``None`` or empty when unknown;
                the engine will skip removal planning in that case.

        Returns:
            Ordered list of PlannedActions to execute.  Entitlement removals
            always precede user-lifecycle actions so the platform records are
            clean before any account deactivation.
        """
        planned: List[PlannedAction] = []
        current_ids: Set[str] = current_entitlement_ids or set()

        # Build a lookup: entitlement_id → EntitlementRule for all sync_managed rules.
        # Used to resolve type + id pairs for removal planning.
        sync_managed_by_id: Dict[str, EntitlementRule] = {
            r.entitlement_id: r for r in policy.sync_managed_rules()
        }

        if user_should_exist:
            planned.append(PlannedAction(action="ensure_user"))

            desired_ids: Set[str] = set()
            for rule in required_entitlements:
                if rule.entitlement_type in capabilities.supported_entitlement_types:
                    planned.append(
                        PlannedAction(
                            action="apply_entitlement",
                            entitlement_type=rule.entitlement_type,
                            entitlement_id=rule.entitlement_id,
                        )
                    )
                    desired_ids.add(rule.entitlement_id)

            # Remove sync-managed entitlements user holds but is no longer qualified for.
            for ent_id in sorted(current_ids):
                if ent_id in sync_managed_by_id and ent_id not in desired_ids:
                    rule = sync_managed_by_id[ent_id]
                    if (
                        rule.entitlement_type
                        in capabilities.supported_entitlement_types
                    ):
                        planned.append(
                            PlannedAction(
                                action="remove_entitlement",
                                entitlement_type=rule.entitlement_type,
                                entitlement_id=ent_id,
                            )
                        )
            return planned

        # User should NOT exist.
        # Step 1: strip all sync-managed entitlements the user currently holds
        # before any account-level deactivation.
        for ent_id in sorted(current_ids):
            if ent_id in sync_managed_by_id:
                rule = sync_managed_by_id[ent_id]
                if rule.entitlement_type in capabilities.supported_entitlement_types:
                    planned.append(
                        PlannedAction(
                            action="remove_entitlement",
                            entitlement_type=rule.entitlement_type,
                            entitlement_id=ent_id,
                        )
                    )

        # Step 2: user lifecycle action per policy.
        # Always plan the policy-mandated action.  Adapters that cannot automate
        # it return UNSUPPORTED_OPERATION; the service then marks
        # requires_manual_action so an operator can act.
        if policy.authn_removal_mode == "disable":
            planned.append(PlannedAction(action="disable_user"))
        elif policy.authn_removal_mode == "delete":
            planned.append(PlannedAction(action="remove_user"))
        # authn_removal_mode == "entitlement_only": entitlement removals above
        # are sufficient; no account-level action is needed.

        return planned
