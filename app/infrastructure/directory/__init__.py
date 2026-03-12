"""Directory core service package.

Provides an IDP-agnostic directory abstraction for security group reads.
Feature packages should access the service via the singleton accessor:

    from infrastructure.services import get_directory_provider

    provider = get_directory_provider()
    result = provider.check_membership("sg-admin@example.com", "user@example.com")
"""
