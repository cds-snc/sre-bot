# Analysis of test coverage gaps for modules/groups/mappings.py

## High-level gap summary
- The current test module exercises many core `map_provider_group_id` branches (same-provider, map → primary with/without primary.prefix, primary → non-primary canonical extraction, invalid empty inputs) and wrapper error handling for mapping helper wrappers.
- Missing coverage is concentrated around:
  - parsing and separator behaviors in `parse_primary_group_name` (colon, slash, longest-prefix selection).
  - local-name/email extraction behavior (`_local_name_from_primary`, exercised only indirectly).
  - provider registry activation/absent-provider behaviors (`_ensure_providers_activated`).
  - unknown-source / missing provider when mapping to primary (raising ValueError).
  - primary/ canonical composition helpers (`primary_group_to_canonical`, `canonical_to_primary_group`).
  - provider-registry helper (`_extract_prefixes_from_registry`) behavior with mapping vs non-mapping entries and empty/falsey prefix values.
  - mapping lists of groups → provider maps and association logic:
    - `map_normalized_groups_list_to_providers`
    - `map_normalized_groups_list_to_providers_with_association` (including mutability / immutable objects path and longest-prefix resolution).
  - `normalize_member_for_provider` (valid/invalid email, provider argument ignored currently but should be exercised).
  - Error branches where providers are not activated (RuntimeError from `_ensure_providers_activated`).
  - Edge cases like providers having empty-string prefix attributes (the code only adds prefixes when truthy).

Below I enumerate per function what is covered and what is missing, then give concrete suggested tests.

## Per-function analysis (coverage & missing branches)

1) `_local_name_from_primary(primary_name: str) -> str`
- Purpose: return the local part if input contains '@', empty string for falsy input.
- Covered? Indirectly via other functions but no direct tests.
- Missing branches:
  - Input with '@' to verify local part extraction.
  - Empty/None input returns "" (should be tested).

Suggested tests:
- `test_local_name_from_primary_handles_email_local_part`
- `test_local_name_from_primary_empty_returns_empty`

2) `_ensure_providers_activated(provider_registry: Optional[Mapping]) -> Dict`
- Purpose: return provider registry or call `get_active_providers()`; raises RuntimeError if no providers.
- Covered? Not tested.
- Missing branches:
  - When provider_registry arg is provided and non-empty → return dict form.
  - When no provider_registry and `get_active_providers()` returns empty → should raise RuntimeError.
  - When `provider_registry` is empty mapping → raises RuntimeError.

Suggested tests:
- `test_ensure_providers_activated_uses_passed_registry`
- `test_ensure_providers_activated_raises_on_empty_active`

3) `parse_primary_group_name(primary_group_name, provider_registry=None) -> {'prefix', 'canonical'}`
- Purpose: determine provider prefix and canonical name by checking provider prefixes (prefers inst.prefix or provider name). Matches separators in order `':'`, `'/'`, `'-'`. Longest-prefix-first matching.
- Covered? Partially exercised indirectly by `map_provider_group_id` when `from_provider == primary`. Existing tests don't cover:
  - ':' and '/' separator matching.
  - Longest-prefix resolution (e.g., providers with prefixes `a` and `ab`—should match `ab` for `ab-...`).
  - Cases where provider instance `prefix` is empty string or falsy (should be skipped).
  - When provider_registry is omitted and `get_active_providers()` empty → runtime error via `_ensure_providers_activated`.

Suggested tests:
- `test_parse_primary_group_name_matches_colon_separator`
- `test_parse_primary_group_name_matches_slash_separator`
- `test_parse_primary_group_name_prefers_longest_prefix`
- `test_parse_primary_group_name_handles_email_local_part`
- `test_parse_primary_group_name_raises_on_empty_input`

4) `map_provider_group_id(from_provider, from_group_id, to_provider, provider_registry=None) -> str`
- Purpose: core provider-to-provider mapping with rules described in docstring.
- Covered extensively:
  - same-provider short-circuit
  - mapping to primary (prefix composition) — with primary having a prefix attr and without (both tested)
  - mapping from primary to non-primary returns canonical (tested)
  - invalid empty inputs raise ValueError (tested)
- Missing branches:
  - When `to_provider == primary` but `from_provider` not found in provider registry -> raises `ValueError("Unknown source provider: ...")` — NOT tested.
  - When providers are not activated (no provider_registry, `get_active_providers` returns empty) → runtime error from `_ensure_providers_activated` — NOT tested.
  - When `from_provider == primary` but `parse_primary_group_name` returns prefix (i.e., input already includes a prefix different from expectation) — test to ensure canonical extraction works for different separators.
  - When provider instances have falsy `prefix` attribute (e.g., `prefix = ""`) — the code uses `getattr(inst, "prefix", None) or provider_name` but in `parse_primary_group_name` building the prefix_map it sets `p = getattr(inst, "prefix", None) or provider_name` and only includes if `p:`, so empty prefix falls back to provider_name because `or provider_name` will provide non-empty—actually, in `_extract_prefixes_from_registry` and in `map_normalized_groups_list_to_providers_with_association` other behaviors exist where empty prefix may be skipped; still, add tests that exercise provider instances with an empty/None prefix to confirm behavior.

Suggested tests:
- `test_map_provider_group_id_raises_when_source_provider_unknown` (mock providers without the source provider)
- `test_map_provider_group_id_raises_when_providers_not_activated` (get_active_providers returns {})
- `test_map_provider_group_id_primary_input_with_colon_separator` (verify canonical extraction)

5) `primary_group_to_canonical(primary_group_name, prefixes=None) -> str`
- Purpose: strip known prefix (from `prefixes`) if present, else return full name (after local-part extraction).
- Covered? Not directly tested.
- Missing branches:
  - `prefixes` is None → function should return name (after email local part stripping).
  - `prefixes` contains multiple values, including longer prefixes -> longest-first behavior.
  - Input with '@' uses local part.
  - Empty/None input returns "".

Suggested tests:
- `test_primary_group_to_canonical_strips_longest_prefix`
- `test_primary_group_to_canonical_no_prefixes_returns_name`
- `test_primary_group_to_canonical_handles_email`

6) `canonical_to_primary_group(canonical_name, prefix=None) -> str`
- Purpose: compose primary-style name by prefixing with `prefix-` if prefix given.
- Covered? Not tested.
- Missing:
  - Test with prefix provided.
  - Test with empty prefix (None) returns canonical unchanged.
  - Empty canonical_name returns "".

Suggested tests:
- `test_canonical_to_primary_group_with_prefix`
- `test_canonical_to_primary_group_no_prefix_and_empty`

7) `_extract_prefixes_from_registry(provider_registry) -> (provider_to_prefix, prefixes_iterable)`
- Purpose: build provider->prefix map where cfg may be mapping or non-mapping.
- Covered? Not tested.
- Missing branches:
  - cfg is Mapping with 'prefix'
  - cfg is Mapping without 'prefix' -> should use provider name
  - cfg is not Mapping -> uses provider name
  - Return types correctness and ordering not required, but verify values.

Suggested tests:
- `test_extract_prefixes_from_registry_with_mixed_cfg_types`

8) `map_secondary_to_primary_group(secondary_provider, secondary_group_id) -> str` and `map_primary_to_secondary_group(primary_group_id, secondary_provider) -> str`
- Purpose: wrapper helpers that call `map_provider_group_id` and log + wrap exceptions as ValueError.
- Covered? Partly:
  - `map_secondary_to_primary_group` success and failure tested (two tests).
  - `map_primary_to_secondary_group` success tested; failure path not tested (when map_provider_group_id raises).
- Missing:
  - `map_primary_to_secondary_group` failure path raising ValueError on map_provider_group_id Exception.
  - Cases where `get_primary_provider_name` returns something unexpected? (less important)
- Suggested tests:
  - `test_map_primary_to_secondary_group_raises_on_failure`

9) `map_normalized_groups_list_to_providers(groups: List[NormalizedGroup]) -> GroupsMap`
- Purpose: group list by `.provider` or `['provider']` and default unknown.
- Covered? Not tested.
- Missing:
  - Dict-like elements, attribute-like objects, missing provider -> grouped under `"unknown"`.
  - Mixed types in the same call.
- Suggested tests:
  - `test_map_normalized_groups_list_to_providers_handles_dict_and_namespace_and_unknown`

10) `map_normalized_groups_list_to_providers_with_association(groups, provider_registry=None) -> GroupsMap`
- Purpose: tries to parse primary-style names and associate them to a provider when prefix resolved; mutates the group's provider where possible; falls back to "unknown".
- Covered? Not tested at all.
- Missing branches:
  - When `primary_name` contains a known prefix -> resolved_provider set and group provider updated.
  - When `primary_name` parsed but prefix not in prefix_to_provider -> no change.
  - When object is not writable -> AttributeError/TypeError handled (logs debug and proceeds).
  - Longest-prefix selection when multiple providers' prefixes can match.
  - When provider_registry is omitted and `get_active_providers()` is used -> behavior as above.
- Suggested tests:
  - `test_map_normalized_groups_list_to_providers_with_association_updates_provider_for_known_prefix` (dict and object versions)
  - `test_map_normalized_groups_list_to_providers_with_association_immutable_object_does_not_raise`
  - `test_map_normalized_groups_list_to_providers_with_association_longest_prefix_win`

11) `normalize_member_for_provider(member_email, provider_type) -> NormalizedMember`
- Purpose: validate email contains '@', return NormalizedMember with email and other None fields.
- Covered? Not tested.
- Missing:
  - Valid email -> returns NormalizedMember with email set
  - Invalid email (no '@' or empty) -> raises ValueError
- Suggested tests:
  - `test_normalize_member_for_provider_valid_email_returns_normalized`
  - `test_normalize_member_for_provider_invalid_email_raises`

## Concrete test list (prioritized)
I list suggested tests with concise setup/invoke/assert details you can add to `tests/modules/groups/test_mappings.py`. Start with high-priority tests that cover error and core parsing branches.

High priority (cover critical logic/error paths)
1. test_map_provider_group_id_raises_when_source_provider_unknown
   - Setup: mock get_active_providers to return `{"google": SimpleNamespace(primary=True)}` (no "aws")
   - Call: gm.map_provider_group_id(from_provider="aws", from_group_id="my-group", to_provider="google")
   - Expect: ValueError with message containing "Unknown source provider: aws"

2. test_ensure_providers_activated_raises_on_empty_active
   - Setup: patch `modules.groups.mappings.get_active_providers` to return {}
   - Call: call gm._ensure_providers_activated() (import via module) or call a public function that uses it (e.g., gm.parse_primary_group_name with no providers)
   - Expect: RuntimeError

3. test_parse_primary_group_name_prefers_longest_prefix_and_various_separators
   - Setup: mock get_active_providers to return providers with prefixes `{"a": ns(prefix="a"), "ab": ns(prefix="ab")}`
   - Call: gm.parse_primary_group_name("ab:my") and gm.parse_primary_group_name("ab/my") and gm.parse_primary_group_name("ab-my")
   - Expect: {'prefix': 'ab', 'canonical': 'my'} for each

4. test_primary_group_to_canonical_strips_longest_prefix_and_handles_email
   - Call: gm.primary_group_to_canonical("ab-my", prefixes=["a","ab"]) -> "my"
   - Call: gm.primary_group_to_canonical("user@example.com", prefixes=None) -> "user"

5. test_map_normalized_groups_list_to_providers_handles_dict_and_namespace_and_unknown
   - Input: [{"id": "g", "provider": "aws"}, SimpleNamespace(id="h", provider="google"), {"id":"no_provider"}]
   - Expect map has keys "aws", "google", "unknown" with respective lists.

Medium priority (nice-to-have; improves parsing coverage)
6. test_parse_primary_group_name_matches_colon_and_slash_and_dash
   - Setup: providers with prefix "p"
   - Inputs: "p:foo", "p/foo", "p-foo"
   - Expects canonical "foo" each time.

7. test_local_name_from_primary_email_and_empty
   - Inputs: "bob@domain", ""/None
   - Expects "bob" and "" respectively.

8. test_canonical_to_primary_group_with_and_without_prefix
   - Call: gm.canonical_to_primary_group("my", "p") -> "p-my"
   - Call: gm.canonical_to_primary_group("my", None) -> "my"
   - Call: gm.canonical_to_primary_group("", "p") -> ""

9. test_extract_prefixes_from_registry_with_mixed_cfg_types
   - Input registry: {"a": {"prefix":"x"}, "b": "notamap", "c": {}}
   - Expect: provider_to_prefix {"a":"x","b":"b","c":"c"}, prefixes contains "x","b","c"

10. test_map_provider_group_id_raises_when_providers_not_activated
    - Patch get_active_providers to {} and call map_provider_group_id (with any args)
    - Expect: RuntimeError with message about providers not activated

Lower priority (helpers and wrappers)
11. test_map_primary_to_secondary_group_raises_on_failure
    - Patch map_provider_group_id to raise Exception("boom")
    - Call gm.map_primary_to_secondary_group("g-my", "aws")
    - Expect ValueError

12. test_map_normalized_groups_list_to_providers_with_association_updates_provider_for_known_prefix
    - Setup provider registry: {"aws": SimpleNamespace(prefix="a"), "google": SimpleNamespace(prefix="g")}
    - Input groups: [{"id": "a-svc", "provider": None}, SimpleNamespace(id="g-team", provider=None)]
    - Call with provider_registry param and expect returned map keys "aws" and "google" with the groups moved and provider mutated when possible.

13. test_map_normalized_groups_list_to_providers_with_association_immutable_object_does_not_raise
    - Use a custom object that raises on setattr or is a namedtuple/frozen dataclass. Ensure function handles it and group is still present under original provider or unknown.

14. test_normalize_member_for_provider_valid_and_invalid
    - Valid: gm.normalize_member_for_provider("a@b.com","aws") -> NormalizedMember with email set to "a@b.com"
    - Invalid: gm.normalize_member_for_provider("no-at","aws") -> raises ValueError

15. test_parse_primary_group_name_when_provider_prefix_is_empty_string
    - Mock provider instance with prefix="" and another provider with prefix="p"; ensure behavior uses fallback provider_name or skips as code expects.

## Small details & suggestions for test implementations
- Use the same mocking pattern already used in tests: patch `modules.groups.mappings.get_active_providers` and `get_primary_provider_name` where needed.
- For tests needing to pass a `provider_registry` explicitly, pass a plain dict (e.g., `{"aws": {"prefix": "a"}, "google": {"prefix": "g"}}`) to the functions that accept it OR pass a mapping of provider instances when functions expect instances (e.g., `map_provider_group_id` expects provider instances when you call `_ensure_providers_activated` without provider_registry — but `map_provider_group_id` can accept `provider_registry` param for deterministic results).
- For `map_normalized_groups_list_to_providers_with_association`, pass a `provider_registry` mapping whose values are objects with `.prefix` attributes (e.g., SimpleNamespace(prefix="a")). The function expects provider instances when `provider_registry` is provided to it (the helper `_ensure_providers_activated` returns dict(provs) — when we pass a mapping it expects mapping[str, object]).
- For asserting exceptions, use pytest `with pytest.raises(ValueError)`.

## Minimal example test signatures (no code blocks with file changes)
- test_map_provider_group_id_raises_when_source_provider_unknown
- test_ensure_providers_activated_raises_on_empty_active
- test_parse_primary_group_name_prefers_longest_prefix_and_various_separators
- test_primary_group_to_canonical_strips_longest_prefix_and_handles_email
- test_map_normalized_groups_list_to_providers_handles_dict_and_namespace_and_unknown
- test_parse_primary_group_name_matches_colon_and_slash_and_dash
- test_local_name_from_primary_email_and_empty
- test_canonical_to_primary_group_with_and_without_prefix
- test_extract_prefixes_from_registry_with_mixed_cfg_types
- test_map_provider_group_id_raises_when_providers_not_activated
- test_map_primary_to_secondary_group_raises_on_failure
- test_map_normalized_groups_list_to_providers_with_association_updates_provider_for_known_prefix
- test_map_normalized_groups_list_to_providers_with_association_immutable_object_does_not_raise
- test_normalize_member_for_provider_valid_and_invalid
- test_parse_primary_group_name_when_provider_prefix_is_empty_string

## Edge cases to consider in tests
- Inputs that are None or empty strings (functions often raise ValueError or return "").
- Provider instances with falsy/empty `prefix` attributes vs absent `prefix` attribute.
- Multiple providers with overlapping prefixes where deterministic longest-prefix matching matters.
- Dict-like vs attribute-like group objects in grouping functions (and objects that reject setattr).
- Passing `provider_registry` explicitly vs relying on `get_active_providers()` to avoid flakiness in tests.

## Next steps I can take for you
- I can implement these tests directly in `tests/modules/groups/test_mappings.py` and run the test suite (`make test SUBTEST=modules/groups/`), fixing any test-authoring issues (mocks, import paths). Estimated time: ~20–40 minutes to add the 8–12 highest-priority tests and run them.
- Or I can implement a smaller subset first (the high-priority 5 tests) to quickly increase coverage and validate failures.

Which option do you want? If you want me to add tests, I’ll:
1) implement the tests,
2) run pytest for `/modules/groups/`,
3) iterate on any failures up to 3 times, and
4) report results and a brief coverage note.