import importlib
import sys
import types
from importlib import util
from pathlib import Path
from types import ModuleType

# Ensure the application package root is on sys.path so importing application
# modules (e.g. `core.config`) works during pytest collection. Pytest may
# import `conftest` before the project root is on sys.path depending on
# invocation; add it explicitly here before importing application modules.
project_root = "/workspace/app"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import core.config as core_config
import pytest
from tests.factories.google import (
    make_google_groups,
    make_google_members,
    make_google_users,
)
from tests.factories.aws import (
    make_aws_users,
    make_aws_groups,
    make_aws_groups_memberships,
    make_aws_groups_w_users,
)


@pytest.fixture
def safe_providers_import(monkeypatch):
    """Import `modules.groups.providers` safely for tests.

    This fixture temporarily stubs `importlib.import_module` so that
    submodule imports under `modules.groups.providers.*` are blocked
    during the initial import. It also forces `core.config.settings.groups`
    to be an empty mapping during import so module-level startup
    validation is skipped. After the import the real import function is
    restored.
    """
    original_import = importlib.import_module

    def _stub_import(name, package=None):
        if (
            name.startswith("modules.groups.providers.")
            and name != "modules.groups.providers"
        ):
            raise ImportError("submodule imports stubbed in tests")
        return original_import(name, package)

    monkeypatch.setattr(importlib, "import_module", _stub_import)

    # Ensure settings.groups.providers is an empty mapping during import
    monkeypatch.setattr(
        core_config.settings,
        "groups",
        types.SimpleNamespace(providers={}),
        raising=False,
    )

    # Force a fresh import. Instead of using the normal import machinery
    # which would execute `modules/__init__.py` (and by extension
    # `modules.groups.__init__.py`, which now auto-initializes the
    # groups module), load the providers package directly from its
    # file. Create lightweight entries for `modules` and
    # `modules.groups` in sys.modules so relative/absolute imports
    # inside the providers package resolve without triggering the
    # package initializers.
    sys.modules.pop("modules.groups.providers", None)

    project_root = Path(__file__).resolve().parents[1]
    providers_init = project_root / "modules" / "groups" / "providers" / "__init__.py"

    # Insert lightweight package modules to avoid executing real package __init__
    if "modules" not in sys.modules:
        pkg = ModuleType("modules")
        pkg.__path__ = [str(project_root / "modules")]
        sys.modules["modules"] = pkg

    if "modules.groups" not in sys.modules:
        grp_pkg = ModuleType("modules.groups")
        grp_pkg.__path__ = [str(project_root / "modules" / "groups")]
        sys.modules["modules.groups"] = grp_pkg

    spec = util.spec_from_file_location("modules.groups.providers", str(providers_init))
    mod = util.module_from_spec(spec)
    # register before executing so imports inside the module can reference it
    sys.modules["modules.groups.providers"] = mod
    spec.loader.exec_module(mod)

    # Defer provider registration: replace the real register_provider with
    # a decorator that stores the decorated objects so tests can import
    # provider submodules safely without causing instantiation/validation
    # at import time. Tests can call `mod.register_deferred_providers()` to
    # perform the real registration later (after setting up `settings`).
    orig_register = getattr(mod, "register_provider")
    mod._deferred_registry = {}

    def _deferred_register(name: str):
        def _decorator(obj):
            # Attempt immediate registration (tests expect explicit
            # calls to `register_provider` to register immediately).
            # Keep a record in the deferred registry for debugging if
            # needed.
            mod._deferred_registry[name] = obj
            try:
                orig_register(name)(obj)
            except Exception:
                # If registration fails, keep the deferred entry and
                # re-raise so tests see the original error.
                raise
            return obj

        return _decorator

    def _apply_deferred_registrations() -> None:
        """Instantiate and register any previously-decorated providers.

        This should be called by tests after they have configured
        `core.config.settings.groups.providers` as needed.
        """
        # replay deferred registrations using the original register
        for name, obj in list(mod._deferred_registry.items()):
            # call the original register_provider to perform real
            # instantiation/registration and remove from deferred map
            try:
                orig_register(name)(obj)
            finally:
                mod._deferred_registry.pop(name, None)

    # replace the package-level decorator with the deferred variant
    monkeypatch.setattr(mod, "register_provider", _deferred_register, raising=True)
    # expose helper for tests
    # create the attribute on the module if it doesn't exist
    monkeypatch.setattr(
        mod, "register_deferred_providers", _apply_deferred_registrations, raising=False
    )

    # restore importlib.import_module to avoid affecting other imports
    monkeypatch.setattr(importlib, "import_module", original_import)

    return mod


@pytest.fixture
def groups_providers(monkeypatch):
    """Provide a test-controlled `settings.groups.providers` mapping.

    Yields a small namespace with convenience helpers and a mutable
    `providers` dict that tests can mutate. The original
    `core.config.settings.groups` is restored after the test.
    """
    orig_has = hasattr(core_config.settings, "groups")
    orig_groups = getattr(core_config.settings, "groups", None)

    providers = {}

    # Ensure settings.groups exists and exposes the providers mapping
    monkeypatch.setattr(
        core_config.settings,
        "groups",
        types.SimpleNamespace(providers=providers),
        raising=False,
    )

    def set_providers(d: dict):
        # Replace the providers mapping with the provided dict
        monkeypatch.setattr(core_config.settings.groups, "providers", d, raising=False)

    def clear_providers():
        providers.clear()

    def remove_groups():
        # Remove the groups attribute to simulate missing config
        try:
            monkeypatch.delattr(core_config.settings, "groups", raising=False)
        except Exception:
            # best-effort removal
            try:
                delattr(core_config.settings, "groups")
            except Exception:
                pass

    helper = types.SimpleNamespace(
        providers=providers,
        set_providers=set_providers,
        clear_providers=clear_providers,
        remove_groups=remove_groups,
    )

    try:
        yield helper
    finally:
        # Restore original groups attribute
        if orig_has:
            monkeypatch.setattr(
                core_config.settings, "groups", orig_groups, raising=False
            )
        else:
            try:
                monkeypatch.delattr(core_config.settings, "groups", raising=False)
            except Exception:
                try:
                    delattr(core_config.settings, "groups")
                except Exception:
                    pass


@pytest.fixture
def set_provider_capability(groups_providers):
    """Return a helper to set the `provides_role_info` capability for a
    provider in `settings.groups.providers` using the `groups_providers`
    test helper.
    """

    def _setter(provider_name: str, provides_role: bool):
        gp = groups_providers
        gp.providers.setdefault(provider_name, {})
        gp.providers[provider_name].setdefault("capabilities", {})
        gp.providers[provider_name]["capabilities"][
            "provides_role_info"
        ] = provides_role

    return _setter


# Google API Python Client


# Google Discovery Directory Resource
# Legacy Fixtures
@pytest.fixture
def google_groups():
    def _google_groups(n=3, prefix="", domain="test.com"):
        return [
            {
                "id": f"{prefix}google_group_id{i+1}",
                "name": f"{prefix}group-name{i+1}",
                "email": f"{prefix}group-name{i+1}@{domain}",
                "description": f"{prefix}description{i+1}",
                "directMembersCount": i + 1,
            }
            for i in range(n)
        ]

    return _google_groups


@pytest.fixture
def google_users():
    def _google_users(n=3, prefix="", domain="test.com"):
        users = []
        for i in range(n):
            user = {
                "id": f"{prefix}user_id{i+1}",
                "primaryEmail": f"{prefix}user-email{i+1}@{domain}",
                "emails": [
                    {
                        "address": f"{prefix}user-email{i+1}@{domain}",
                        "primary": True,
                        "type": "work",
                    }
                ],
                "suspended": False,
                "name": {
                    "fullName": f"Given_name_{i+1} Family_name_{i+1}",
                    "familyName": f"Family_name_{i+1}",
                    "givenName": f"Given_name_{i+1}",
                    "displayName": f"Given_name_{i+1} Family_name_{i+1}",
                },
            }
            users.append(user)
        return users

    return _google_users


@pytest.fixture
def google_group_members(google_users):
    def _google_group_members(n=3, prefix="", domain="test.com"):
        users = google_users(n, prefix, domain)
        return [
            {
                "kind": "admin#directory#member",
                "email": user["primaryEmail"],
                "role": "MEMBER",
                "type": "USER",
                "status": "ACTIVE",
                "id": user["id"],
            }
            for user in users
        ]

    return _google_group_members


# Fixture with users
@pytest.fixture
def google_groups_w_users(google_groups, google_group_members, google_users):
    def _google_groups_w_users(
        n_groups=1, n_users=3, group_prefix="", user_prefix="", domain="test.com"
    ):
        groups = google_groups(n_groups, prefix=group_prefix, domain=domain)
        members = google_group_members(n_users, prefix=user_prefix, domain=domain)
        users = google_users(n_users, prefix=user_prefix, domain=domain)

        combined_members = []
        for member, user in zip(members, users):
            combined_member = {**member, **user}
            combined_members.append(combined_member)

        for group in groups:
            group["members"] = combined_members
        return groups

    return _google_groups_w_users


# Additional fixtures for comprehensive testing
@pytest.fixture
def google_groups_with_legacy_structure(
    google_group_factory, google_member_factory, google_user_factory
):
    """Factory to create groups with legacy-compatible member structure."""

    def _factory(n_groups=1, n_members_per_group=2, domain="test.com"):
        groups = google_group_factory(n_groups, domain=domain)
        result = []

        for i, group in enumerate(groups):
            # Create members for this group
            members = google_member_factory(
                n_members_per_group, prefix=f"g{i}-", domain=domain
            )
            users = google_user_factory(
                n_members_per_group, prefix=f"g{i}-", domain=domain
            )

            # Create legacy-compatible members with flattened user details
            legacy_members = []
            for member, user in zip(members, users):
                # Ensure email consistency
                member["email"] = user["primaryEmail"]

                # Create legacy member with flattened user details
                legacy_member = {**member}
                legacy_member["user_details"] = user

                # Flatten user details into top-level member dict (legacy compatibility)
                for k, v in user.items():
                    if k not in legacy_member:
                        legacy_member[k] = v

                legacy_members.append(legacy_member)

            group_with_members = {**group}
            group_with_members["members"] = legacy_members
            result.append(group_with_members)

        return result

    return _factory


# --- Google Directory API Pydantic factories ---


@pytest.fixture
def google_group_factory():
    """
    Factory fixture to generate a list of valid Google Group dicts for tests.
    Usage:
        groups = google_group_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_groups(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_user_factory():
    """
    Factory fixture to generate a list of valid Google User dicts or models for tests.
    Usage:
        users = google_user_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
        users = google_user_factory(n=2, as_model=True)
        # returns a list of User models
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_users(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_member_factory():
    """
    Factory fixture to generate a list of valid Google Member dicts or models for tests.
    Usage:
        members = google_member_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
        members = google_member_factory(n=2, as_model=True)
        # returns a list of Member models
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_members(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_batch_response_factory():
    """Factory to create Google API batch response structures."""

    def _factory(success_responses=None, error_responses=None):
        results = {}

        if success_responses:
            results.update(success_responses)

        if error_responses:
            # Add error responses - could be None or error objects
            results.update(error_responses)

        return {"results": results}

    return _factory


# AWS API fixtures


@pytest.fixture
def aws_users():
    # Delegate to factory implementation
    def _wrapper(n=3, prefix="", domain="test.com", store_id="d-123412341234"):
        return make_aws_users(n=n, prefix=prefix, domain=domain, store_id=store_id)

    return _wrapper


@pytest.fixture
def aws_groups():
    def _wrapper(n=3, prefix="", store_id="d-123412341234"):
        return make_aws_groups(n=n, prefix=prefix, store_id=store_id)

    return _wrapper


@pytest.fixture
def aws_groups_memberships():
    def _wrapper(n=3, prefix="", group_id=1, store_id="d-123412341234"):
        return make_aws_groups_memberships(
            n=n, prefix=prefix, group_id=group_id, store_id=store_id
        )

    return _wrapper


@pytest.fixture
def aws_groups_w_users(aws_groups, aws_users, aws_groups_memberships):
    def _wrapper(
        n_groups=1,
        n_users=3,
        group_prefix="",
        user_prefix="",
        domain="test.com",
        store_id="d-123412341234",
    ):
        return make_aws_groups_w_users(
            n_groups=n_groups,
            n_users=n_users,
            group_prefix=group_prefix,
            user_prefix=user_prefix,
            domain=domain,
            store_id=store_id,
        )

    return _wrapper
