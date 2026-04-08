"""Access Sync policy models and planning engine.

This module is the single source of truth for all access-sync business rules.
New developers should read this file before any other in the package.

Three layers of policy are defined here:

1. Configuration models (``EntitlementRule``, ``PlatformPolicy``) — loaded once
   at startup from the external config source and held immutably for the
   lifetime of the process.

2. Runtime-resolved policy (``EffectivePlatformPolicy``) — computed once per
   sync run after the IDP group discovery step.  Both the desired-state builder
   and the PolicyEngine receive this same resolved object so every phase of a
   run operates on an identical entitlement rule set.

3. Planning (``PolicyEngine``) — pure, side-effect-free translation of desired
   state + current state into a minimal ordered list of ``PlannedAction``
   values that the coordinator dispatches to the adapter.

Adapters must not duplicate any logic from this module.
"""

from dataclasses import dataclass, field, replace
from fnmatch import fnmatch
from typing import Dict, List, Literal, Optional, Set, Union


EntitlementMode = Literal["sync_managed", "ephemeral", "deactivated"]
EntitlementStrategyKind = Literal[
    "none",
    "explicit_rules_only",
    "default_prefix",
    "pattern_map",
]


@dataclass(frozen=True)
class EntitlementRule:
    """Mapping from a single IDP security group slug to a platform entitlement.

    Each rule says: "if a user is an effective member of ``group_slug`` in the
    IDP, they should hold ``entitlement_id`` of type ``entitlement_type`` on
    the target platform."

    ``mode`` controls how Access Sync treats the entitlement:

    * ``sync_managed``  — standard lifecycle: Access Sync applies and removes
      this entitlement automatically based on IDP membership.
    * ``ephemeral``     — Privileged Access owns the grant lifecycle. Access
      Sync skips this entitlement during reconciliation so time-bound grants
      are not prematurely revoked.
    * ``deactivated``   — all SRE Bot automation is suspended. Access Sync
      skips apply/remove, Privileged Access refuses new grants, Access Requests
      rejects intake, and the current platform state is frozen until the
      override is removed or expires.

    Mode evaluation is per-rule: one platform policy can mix all three values
    across different entitlement groups.
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
    """Platform-level strategy for auto-generating entitlement rules from IDP groups.

    Used when a platform has many entitlement groups that follow a predictable
    naming pattern and listing them all explicitly in config would be
    impractical.  The strategy is evaluated once per run during IDP group
    discovery (``desired_state.DirectoryMembershipBuilder.discover_group_slugs``).

    ``kind`` selects the matching algorithm:

    * ``none``                — no entitlements managed for this platform.
    * ``explicit_rules_only`` — use only ``PlatformPolicy.entitlement_rules``.
    * ``default_prefix``      — any IDP group whose slug starts with
      ``source_group_prefix`` generates a rule using
      ``entitlement_id_template``.  The ``{token}`` placeholder is replaced
      with the slug suffix after the prefix is stripped.
    * ``pattern_map``         — each group slug is matched against
      ``pattern_mappings`` using ``fnmatch``-style wildcards.

    ``exclude_group_slugs`` is applied before pattern evaluation and always
    takes precedence over both ``default_prefix`` and ``pattern_map``.
    """

    kind: EntitlementStrategyKind = "explicit_rules_only"
    source_group_prefix: str = ""
    exclude_group_slugs: List[str] = field(default_factory=list)
    default_entitlement_type: str = "group"
    entitlement_id_template: str = "{token}"
    mode: EntitlementMode = "sync_managed"
    pattern_mappings: List[PatternEntitlementMapping] = field(default_factory=list)

    def applies_to_group(self, group_slug: str) -> bool:
        """Return True when this strategy should generate a rule for ``group_slug``.

        Groups in ``exclude_group_slugs`` are always rejected regardless of
        prefix or pattern match.  Returns False for ``none`` and
        ``explicit_rules_only`` kinds — those kinds produce no generated rules.
        """
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
        """Build a generated ``EntitlementRule`` for ``group_slug``, or return None.

        Called only after ``applies_to_group`` returns True.  Returns None
        when the slug does not produce a valid entitlement ID (e.g. empty token
        after stripping the prefix).
        """
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
    """Declarative policy for a single target platform, loaded from runtime config.

    A ``PlatformPolicy`` is immutable and process-scoped.  The coordinator
    calls ``resolve_effective_policy`` at the start of each run to produce an
    ``EffectivePlatformPolicy`` that includes any IDP-discovered dynamic rules.
    The base ``PlatformPolicy`` is never mutated.

    ``authn_group_slug`` — e.g. ``sg-aws-authn``.  Effective membership
    (direct or via nested groups) in this IDP group is the authoritative source
    of truth for whether a user should retain access on the target platform.

    ``authn_mode``:

    * ``direct``  — operators manage access via direct membership in the authn group.
    * ``derived`` — operators nest entitlement groups into the authn group; access
      follows from entitlement group membership.

    In both modes, effective membership in the authn group determines whether the
    user should exist.  The mode is informational for operators and adapters; it
    does not change Access Sync's convergence logic.

    ``authn_removal_mode`` — what to do when a user leaves the authn group:

    * ``disable``           — deactivate the user account on the platform.
    * ``delete``            — remove the user from the platform entirely.
    * ``entitlement_only``  — remove only managed entitlements; the account is
      left intact and flagged for manual follow-up.
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
        """Return the full set of entitlement rules for this policy.

        Combines explicit ``entitlement_rules`` with rules auto-generated by
        ``default_entitlement_strategy`` for any slugs in
        ``discovered_group_slugs``.  Explicit rules always win: if a discovered
        slug already has an explicit rule, the strategy-generated candidate is
        discarded.  The authn group slug is also excluded from generation.

        Pass ``discovered_group_slugs=None`` (or omit it) when no strategy is
        configured or no IDP groups were found; only explicit rules are returned.
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

    def with_ephemeral_entitlement(
        self,
        entitlement_type: str,
        entitlement_id: str,
    ) -> "PlatformPolicy":
        """Return a new PlatformPolicy with one additional ephemeral rule appended.

        Uses dataclasses.replace() so all fields — including
        default_entitlement_strategy — are preserved automatically.
        """
        return replace(
            self,
            entitlement_rules=[
                *self.entitlement_rules,
                EntitlementRule(
                    group_slug="",
                    entitlement_type=entitlement_type,
                    entitlement_id=entitlement_id,
                    mode="ephemeral",
                ),
            ],
        )


@dataclass(frozen=True)
class EffectivePlatformPolicy:
    """Policy resolved once at the start of a sync run.

    Produced by ``resolve_effective_policy``.  Combines the base
    ``PlatformPolicy`` with any IDP-discovered dynamic rules so that every
    phase of a run — desired-state building, entitlement prefetch, and
    ``PolicyEngine`` planning — operates on the exact same rule set.

    This eliminates the class of bug where strategy-generated rules are
    included in membership building but absent from removal planning.

    ``EffectivePlatformPolicy`` is immutable and run-scoped.  Create one per
    ``sync_user`` or ``sync_platform`` call; never reuse across runs.
    """

    platform: str
    authn_group_slug: str
    authn_mode: str
    authn_removal_mode: str
    entitlement_rules: List[EntitlementRule]

    def sync_managed_rules(self) -> List[EntitlementRule]:
        """Return rules that Access Sync is responsible for managing."""
        return [r for r in self.entitlement_rules if r.mode == "sync_managed"]

    def ephemeral_entitlement_ids(self) -> Set[str]:
        """Return entitlement IDs owned by Privileged Access (skip during reconciliation)."""
        return {
            r.entitlement_id for r in self.entitlement_rules if r.mode == "ephemeral"
        }

    def deactivated_entitlement_ids(self) -> Set[str]:
        """Return entitlement IDs where all SRE Bot automation is suspended."""
        return {
            r.entitlement_id for r in self.entitlement_rules if r.mode == "deactivated"
        }

    def skip_entitlement_ids(self) -> Set[str]:
        """Return all entitlement IDs Access Sync must not touch."""
        return self.ephemeral_entitlement_ids() | self.deactivated_entitlement_ids()


def resolve_effective_policy(
    policy: "PlatformPolicy",
    discovered_group_slugs: Optional[Set[str]] = None,
) -> EffectivePlatformPolicy:
    """Compute the fully-resolved policy for one sync run.

    Call this once after IDP group discovery.  Pass the result to
    membership builders, PolicyEngine, and all planning steps so every
    phase operates on the same entitlement rule set.

    Args:
        policy: The base platform policy from runtime config.
        discovered_group_slugs: Group slugs discovered from the IDP for
            strategy-driven entitlement expansion.  Pass None or empty
            when no strategy is configured or no groups were found.

    Returns:
        EffectivePlatformPolicy with all rules (explicit + strategy-generated).
    """
    return EffectivePlatformPolicy(
        platform=policy.platform,
        authn_group_slug=policy.authn_group_slug,
        authn_mode=policy.authn_mode,
        authn_removal_mode=policy.authn_removal_mode,
        entitlement_rules=policy.effective_rules(discovered_group_slugs),
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
    for lifecycle actions (``ensure_user``, ``disable_user``, ``remove_user``).
    """

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
    """Translates policy + current state into a minimal ordered list of actions.

    This is the only place in the codebase where policy semantics are
    interpreted.  It is pure (no I/O, no side effects) and deterministic: the
    same inputs always produce the same output.

    Adapters receive ``PlannedAction`` values and execute them.  They must not
    re-implement lifecycle or entitlement classification logic here.
    """

    def plan_actions(
        self,
        policy: Union[PlatformPolicy, EffectivePlatformPolicy],
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
