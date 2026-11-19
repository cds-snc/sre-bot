"""Behavior tests for the package-layout manifest and its loader.

The real manifest (app/bin/package_layout.toml) is loaded and its kinds are
asserted against the rules of decisions/feature-packages.md. Malformed
manifests are written under ``tmp_path`` and must be refused with a message
naming the offending key, so a bad edit fails loudly instead of silently
widening the shape check. A drift test compares the names in the record's
layout table with the manifest's, so the two can only change together. The
generator's options and templates are read from the same manifest, so the
real one is also checked for the option each kind takes and for a template on
every entry the generator can write. The names the other bin guards read (the
public api module, the adapters directory, the core and common kinds) are
asserted on the real manifest, and a manifest that cannot supply them is
refused by the repository check, so no guard keeps its own copy.
"""

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from bin.package_layout import COMMON_KIND, CORE_KIND, LAYOUT_PATH, Layout, LayoutError, check_tool_needs, load_layout

DECISION = Path(__file__).resolve().parents[4] / "decisions" / "feature-packages.md"
TEMPLATES = LAYOUT_PATH.parent / "package_templates"

MINIMAL = """
roots = { features = "features", capabilities = "capabilities" }
public_api = "api.py"
reserved_subdomains = ["core"]
grows_into_package = ["service.py"]

[capability_readme]
classification_heading = "## Classification"
consumers_heading = "## Feature consumers"
classifications = ["generic"]

[kinds.feature]
required = ["__init__.py", "service.py"]
optional = ["adapters/"]
"""


OPTIONS = """
[options.service]
entry = "service.py"

[options.adapters]
entry = "adapters/"

[kinds.feature.templates]
"__init__.py" = "init.tmpl"
"service.py" = "service.tmpl"
"adapters/" = ""
"""

CAPABILITY = """
[kinds.capability]
extends = "feature"
exclude = ["service.py"]
required = ["api.py"]
optional = ["service.py"]

[kinds.capability.templates]
"api.py" = "api.tmpl"
"""

TOOL_NEEDS = """
[options.adapters]
entry = "adapters/"

[kinds.capability]
extends = "feature"
required = ["api.py"]

[kinds.core]
extends = "feature"
required = ["api.py"]

[kinds.common]
required = ["__init__.py"]
open = true
"""


def _load(tmp_path: Path, text: str) -> Layout:
    path = tmp_path / "layout.toml"
    path.write_text(text, encoding="utf-8")
    return load_layout(path)


def _table_names() -> set[str]:
    """Names in the layout code block of feature-packages.md, a directory keeping its trailing '/'."""
    text = DECISION.read_text(encoding="utf-8")
    block = text.split("```text\napp/features/<feature>/\n", 1)[1].split("```", 1)[0]
    return {match.group(1) for line in block.splitlines() if (match := re.search(r"── (\S+)", line))}


class TestRealManifest:
    """The checked-in manifest encodes the layout table's rules per kind."""

    def test_every_kind_requires_an_init(self) -> None:
        layout = load_layout(LAYOUT_PATH)

        assert {name for name, kind in layout.kinds.items() if "__init__.py" not in kind.required} == set()

    def test_a_capability_allows_api_and_hookspecs_and_a_feature_does_not(self) -> None:
        kinds = load_layout(LAYOUT_PATH).kinds

        assert {"api.py", "hookspecs.py"} <= kinds["capability"].allowed_files
        assert {"api.py", "hookspecs.py"} & kinds["feature"].allowed_files == set()
        assert kinds["subdomain"].allowed_files == kinds["feature"].allowed_files

    def test_core_has_api_and_no_plugin_module_or_entrypoints(self) -> None:
        core = load_layout(LAYOUT_PATH).kinds["core"]

        assert "api.py" in core.allowed_files
        assert "plugin.py" not in core.allowed_files
        assert "entrypoints" not in core.allowed_dirs

    def test_service_and_domain_may_be_modules_or_packages(self) -> None:
        feature = load_layout(LAYOUT_PATH).kinds["feature"]

        assert {"service.py", "domain.py"} <= feature.allowed_files
        assert {"service", "domain"} <= feature.allowed_dirs

    def test_common_is_open_except_for_io_names(self) -> None:
        common = load_layout(LAYOUT_PATH).kinds["common"]

        assert common.open
        assert common.forbidden_names == {"adapters", "store.py", "providers.py"}

    def test_an_umbrella_root_allows_only_its_init_and_readme(self) -> None:
        umbrella = load_layout(LAYOUT_PATH).kinds["umbrella"]

        assert umbrella.allowed_files == {"__init__.py", "README.md"}
        assert umbrella.allowed_dirs == frozenset()

    def test_a_capability_requires_only_its_init_readme_and_api(self) -> None:
        capability = load_layout(LAYOUT_PATH).kinds["capability"]

        assert capability.required == {"__init__.py", "README.md", "api.py"}
        assert {"service.py", "entrypoints/", "hookspecs.py", "interfaces.py", "adapters/"} <= capability.optional

    def test_core_may_gain_interfaces_and_adapters_but_never_entrypoints(self) -> None:
        core = load_layout(LAYOUT_PATH).kinds["core"]

        assert core.required == {"__init__.py", "README.md", "api.py", "service.py"}
        assert {"interfaces.py", "adapters/"} <= core.optional
        assert "entrypoints/" not in core.declared

    @pytest.mark.parametrize(
        ("kind", "options"),
        [
            ("capability", ["hookspecs", "service", "entrypoints", "interfaces", "adapters", "settings"]),
            ("feature", ["interfaces", "adapters", "settings"]),
            ("subdomain", ["interfaces", "adapters", "settings"]),
            ("core", ["interfaces", "adapters", "settings"]),
            ("common", ["settings"]),
            ("umbrella", []),
        ],
    )
    def test_each_kind_takes_the_options_whose_entry_it_lists_as_optional(self, kind: str, options: list[str]) -> None:
        assert [option.name for option in load_layout(LAYOUT_PATH).options_of(kind)] == options

    def test_interfaces_needs_a_service(self) -> None:
        assert load_layout(LAYOUT_PATH).options["interfaces"].needs == {"service.py"}

    def test_every_entry_the_generator_writes_has_an_existing_template(self) -> None:
        layout = load_layout(LAYOUT_PATH)

        for name, kind in layout.kinds.items():
            written = kind.required | {option.entry for option in layout.options_of(name)}
            assert set(kind.templates) >= written, name
            for template in kind.templates.values():
                assert not template or (TEMPLATES / template).is_file(), template

    def test_the_layout_table_and_the_manifest_name_the_same_entries(self) -> None:
        declared = load_layout(LAYOUT_PATH).declared_names

        assert _table_names() == declared, (
            "decisions/feature-packages.md's layout table and app/bin/package_layout.toml differ; "
            "amend the record and the manifest together"
        )

    def test_the_guards_read_the_public_api_adapters_and_umbrella_kernel_names(self) -> None:
        layout = check_tool_needs(load_layout(LAYOUT_PATH))

        assert layout.public_api == "api.py"
        assert layout.adapters_dir == "adapters"
        assert {CORE_KIND, COMMON_KIND} <= set(layout.kinds)
        assert layout.public_api in layout.kinds["capability"].required & layout.kinds[CORE_KIND].required


class TestMalformedManifest:
    """A malformed manifest is refused, naming the key at fault."""

    def test_a_minimal_manifest_loads(self, tmp_path: Path) -> None:
        layout = _load(tmp_path, MINIMAL)

        assert layout.kinds["feature"].allowed_dirs == {"adapters", "service"}
        assert layout.classifications == ("generic",)
        assert layout.options == {}
        assert layout.kinds["feature"].templates == {}

    def test_options_and_templates_are_read_and_inherited(self, tmp_path: Path) -> None:
        layout = _load(tmp_path, MINIMAL + OPTIONS + CAPABILITY)

        assert layout.options["adapters"].entry == "adapters/"
        assert [option.name for option in layout.options_of("feature")] == ["adapters"]
        assert [option.name for option in layout.options_of("capability")] == ["service", "adapters"]
        assert layout.kinds["capability"].templates == {
            "__init__.py": "init.tmpl",
            "service.py": "service.tmpl",
            "adapters/": "",
            "api.py": "api.tmpl",
        }

    def test_an_inherited_required_entry_can_be_excluded_and_made_optional(self, tmp_path: Path) -> None:
        capability = _load(tmp_path, MINIMAL + CAPABILITY).kinds["capability"]

        assert capability.required == {"__init__.py", "api.py"}
        assert capability.optional == {"service.py", "adapters/"}

    @pytest.mark.parametrize(
        ("edit", "message"),
        [
            (lambda text: 'unknown = "x"\n' + text, "unknown"),
            (lambda text: text + '\n[kinds.extra]\nrequired = ["__init__.py"]\nsurplus = true\n', "surplus"),
            (lambda text: text.replace('optional = ["adapters/"]', 'optional = ["service.py"]'), "service.py"),
            (lambda text: text.replace('optional = ["adapters/"]', 'optional = ["adapters/x.py"]'), "adapters/x.py"),
            (lambda text: text + '\n[kinds.core]\nextends = "nowhere"\n', "nowhere"),
            (lambda text: text.replace('classifications = ["generic"]', "classifications = []"), "classifications"),
            (lambda text: text.replace('roots = { features = "features", capabilities = "capabilities" }', ""), "roots"),
            (lambda text: text + '\n[kinds.core]\nextends = "feature"\nexclude = ["api.py"]\n', "api.py"),
            (lambda text: text + '\n[options.hooks]\nentry = "hookspecs.py"\n', "options.hooks.entry"),
            (lambda text: text + '\n[options.adapters]\nentry = "adapters/"\nneeds = ["store.py"]\n', "options.adapters.needs"),
            (lambda text: text + '\n[options.adapters]\nentry = "adapters/"\nflag = "a"\n', "flag"),
            (lambda text: text + '\n[kinds.feature.templates]\n"api.py" = "api.tmpl"\n', "kinds.feature.templates"),
            (lambda text: text.replace('public_api = "api.py"\n', ""), "public_api"),
            (lambda text: text.replace('public_api = "api.py"', 'public_api = "api/"'), "public_api"),
            (lambda text: text + CAPABILITY.replace('required = ["api.py"]', 'required = ["hookspecs.py"]'), "kinds.capability"),
            (lambda text: text + '\n[kinds.core]\nextends = "feature"\n', "kinds.core"),
        ],
        ids=[
            "unknown-top-level-key",
            "unknown-kind-key",
            "required-and-optional",
            "nested-path",
            "unknown-base-kind",
            "empty-classifications",
            "missing-roots",
            "exclude-of-an-absent-name",
            "option-entry-undeclared",
            "option-needs-unknown",
            "unknown-option-key",
            "template-for-an-undeclared-entry",
            "missing-public-api",
            "public-api-a-directory",
            "capability-without-the-public-api",
            "core-without-the-public-api",
        ],
    )
    def test_a_malformed_manifest_is_refused(self, tmp_path: Path, edit: Callable[[str], str], message: str) -> None:
        with pytest.raises(LayoutError, match=re.escape(message)):
            _load(tmp_path, edit(MINIMAL))

    def test_a_manifest_with_every_name_the_guards_read_passes_the_repository_check(self, tmp_path: Path) -> None:
        layout = check_tool_needs(_load(tmp_path, MINIMAL + TOOL_NEEDS))

        assert layout.adapters_dir == "adapters"

    @pytest.mark.parametrize(
        ("removed", "message"),
        [
            ('[options.adapters]\nentry = "adapters/"\n', "options.adapters"),
            ('[kinds.capability]\nextends = "feature"\nrequired = ["api.py"]\n', "kinds.capability"),
            ('[kinds.core]\nextends = "feature"\nrequired = ["api.py"]\n', "kinds.core"),
            ('[kinds.common]\nrequired = ["__init__.py"]\nopen = true\n', "kinds.common"),
        ],
        ids=["no-adapters-option", "no-capability-kind", "no-core-kind", "no-common-kind"],
    )
    def test_a_manifest_missing_a_name_the_guards_read_fails_the_repository_check(
        self, tmp_path: Path, removed: str, message: str
    ) -> None:
        layout = _load(tmp_path, MINIMAL + TOOL_NEEDS.replace(removed, ""))

        with pytest.raises(LayoutError, match=re.escape(message)):
            check_tool_needs(layout)
