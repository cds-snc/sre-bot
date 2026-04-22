"""Access Sync policy models and planning engine.

This module is the single source of truth for all access-sync business rules.
New developers should read this file before any other in the package.

Two layers of policy are defined here:

1. Configuration models (``EntitlementRule``, ``PlatformPolicy``) -- constructed
   at startup from the external config source and held immutably for the
   lifetime of the process.  ``PlatformPolicy`` is deliberately minimal: it
   carries only what cannot be derived at runtime (authn token, removal mode,
   and mode overrides for specific tokens).  Slug construction -- authn group
   slug, platform group prefix -- lives in ``AccessSyncRuntimeConfig``.

2. Runtime-resolved policy (``EffectivePlatformPolicy``) -- built once per sync
   run by ``resolve_effective_policy`` after the IDP group discovery step.
   Contains only ``sync_managed`` rules; ephemeral and deactivated tokens are
   excluded at resolution time.  Both the desired-state builder and the planner
   receive this same object so every phase of a run operates on the same rule
   set.

3. Planning (``PolicyEngine``) -- pure, side-effect-free translation of desired
   state + current state into a minimal ordered list of ``PlannedAction``
   values the coordinator dispatches to the adapter.

Adapters must not duplicate any logic from this module.
"""

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Set, TYPE_CHECKING

from packages.access.common.config import EntitlementRule

if TYPE_CHECKING:
    from packages.access.common.config import AccessRuntimeConfig


@dataclass(frozen=True)
class EffectivePlatformPolicy:
    """Policy resolved once at the start of a sync run.

    Produced by ``resolve_effective_policy``.  Contains only ``sync_managed``
    rules; ephemeral and deactivated tokens are excluded at resolution time.

    Pass this to desired-state builders, the prefetch step, and the
    ``PolicyEngine`` so every phase of a run operates on the same rule set.

    ``EffectivePlatformPolicy`` is immutable and run-scoped.  Create one per
    ``sync_user`` or ``sync_platform`` call; never reuse across runs.
    """

    platform: str
    authn_group_slug: str
    authn_removal_mode: str
    entitlement_rules: List[EntitlementRule]

    def sync_managed_rules(self) -> List[EntitlementRule]:
        """All rules (every rule in effective policy is already sync_managed)."""
        return list(self.entitlement_rules)


@dataclass(frozen=True)
class PlanningContext:
    """Policy context passed to adapters for reconciliation planning.

    Contains only the information adapters need to compute a delta plan.
    IDP-specific fields (authn_group_slug) are intentionally excluded; those
    are only needed during desired-state construction in ``desired_state.py``.

    Produced by ``PlanningContext.from_effective`` after the IDP step.
    """

    platform: str
    authn_removal_mode: str
    entitlement_rules: List[EntitlementRule]

    def sync_managed_rules(self) -> List[EntitlementRule]:
        """All rules (every rule in planning context is already sync_managed)."""
        return list(self.entitlement_rules)

    @classmethod
    def from_effective(cls, effective: "EffectivePlatformPolicy") -> "PlanningContext":
        """Derive a PlanningContext from an EffectivePlatformPolicy."""
        return cls(
            platform=effective.platform,
            authn_removal_mode=effective.authn_removal_mode,
            entitlement_rules=effective.entitlement_rules,
        )


def resolve_effective_policy(
    config: "AccessRuntimeConfig",
    platform: str,
    discovered_slugs: Set[str],
) -> EffectivePlatformPolicy:
    """Build the run-scoped effective policy from IDP-discovered group slugs.

    Only groups matching the platform prefix are included.  The authn token
    group and any token declared in ``PlatformPolicy.mode_overrides`` with a
    non-``sync_managed`` mode are excluded.  The result contains only
    ``sync_managed`` rules and is ready for the sync pipeline.

    Args:
        config: Runtime config carrying ``dir_prefix``, ``dir_separator``, and
            the per-platform ``PlatformPolicy`` map.
        platform: Platform key (e.g. ``"aws"``).
        discovered_slugs: All group slugs returned by the IDP discovery step.

    Returns:
        ``EffectivePlatformPolicy`` with entitlement rules ready for sync.
    """
    policy = config.platforms[platform]
    prefix = config.group_prefix(platform)
    authn_slug = config.authn_group_slug(platform)

    rules: List[EntitlementRule] = []
    for slug in sorted(discovered_slugs):
        normalized = slug.strip().lower()
        if normalized == authn_slug.lower():
            continue
        if not normalized.startswith(prefix.lower()):
            continue
        token = normalized[len(prefix) :]
        if not token:
            continue
        mode = policy.mode_overrides.get(token, "sync_managed")
        if mode != "sync_managed":
            continue  # Silently excluded
        rules.append(
            EntitlementRule(
                group_slug=normalized,
                entitlement_id=token,
                entitlement_type="group",
                mode="sync_managed",
            )
        )

    return EffectivePlatformPolicy(
        platform=platform,
        authn_group_slug=authn_slug,
        authn_removal_mode=policy.authn_removal_mode,
        entitlement_rules=rules,
    )


@dataclass(frozen=True)
class AdapterCapabilities:
    """Execution capabilities declared by a platform adapter.

    The coordinator queries ``adapter.capabilities()`` once per run and passes
    the result to ``PolicyEngine.plan_actions``.  The engine cross-references
    capabilities against the desired actions to skip unsupported operations and
    set ``requires_manual_action`` on the outcome instead.

    ``supports_bulk_user_delta`` enables an optimisation in ``sync_platform``:
    when True and no entitlement rules are configured, users already on the
    platform and in the IDP authn group are skipped entirely (zero-diff path).
    """

    supports_disable: bool
    supports_delete: bool
    supported_entitlement_types: Set[str]
    supports_bulk_user_delta: bool = False


@dataclass(frozen=True)
class PlannedAction:
    """A single normalized action produced by ``PolicyEngine.plan_actions``.

    The coordinator iterates the planned list and dispatches each action to the
    adapter.  ``entitlement_type`` and ``entitlement_id`` are populated for
    ``apply_entitlement`` and ``remove_entitlement`` actions; they are ``None``
    for lifecycle actions (``provision_user``, ``disable_user``, ``remove_user``).
    """

    action: Literal[
        "provision_user",
        "disable_user",
        "remove_user",
        "apply_entitlement",
        "remove_entitlement",
    ]
    entitlement_type: Optional[str] = None
    entitlement_id: Optional[str] = None


class PolicyEngine:
    """Translates policy + current state into a minimal ordered list of actions.

    This is the only place in the codebase where policy semantics are
    interpreted.  It is pure (no I/O, no side effects) and deterministic: the
    same inputs always produce the same output.

    Adapters receive ``PlannedAction`` values and execute them.  They must not
    re-implement lifecycle or entitlement classification logic here.
    """

    def plan_actions(
        self,
        policy: PlanningContext,
        capabilities: AdapterCapabilities,
        user_should_exist: bool,
        required_entitlements: List[EntitlementRule],
        current_entitlement_ids: Optional[Set[str]] = None,
        platform_user_exists: bool = False,
    ) -> List[PlannedAction]:
        """Produce the minimal ordered action list to converge one user.

        Args:
            policy: Planning context (platform, removal mode, rules).
            capabilities: Adapter capability declaration.
            user_should_exist: Whether IDP membership in the authn group is True.
            required_entitlements: Sync-managed rules the user qualifies for.
            current_entitlement_ids: Entitlement IDs the user currently holds
                on the platform.  Pass ``None`` when unknown; no removals are
                planned.
            platform_user_exists: Whether the user already exists on the platform.
                Only emits ``provision_user`` when this is ``False``.

        Returns:
            Ordered list of PlannedActions.  Entitlement removals precede
            user-lifecycle actions so records are clean before deactivation.
        """
        planned: List[PlannedAction] = []
        current_ids: Set[str] = current_entitlement_ids or set()

        sync_managed_by_id: Dict[str, EntitlementRule] = {
            r.entitlement_id: r for r in policy.sync_managed_rules()
        }

        if user_should_exist:
            if not platform_user_exists:
                planned.append(PlannedAction(action="provision_user"))

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

        if platform_user_exists:
            if policy.authn_removal_mode == "disable":
                planned.append(PlannedAction(action="disable_user"))
            elif policy.authn_removal_mode == "delete":
                planned.append(PlannedAction(action="remove_user"))

        return planned
