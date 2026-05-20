"""Directory core service package.

Provides an IDP-agnostic directory abstraction for security group reads.
Feature packages should access the service via the singleton accessor:
"""

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.directory.provider import DirectoryProvider
from infrastructure.directory.factory import (
    get_directory_provider,
)

__all__ = [
    "DirectoryGroup",
    "DirectoryMember",
    "DirectoryUser",
    "DirectoryProvider",
    "MembershipCheckResult",
    "get_directory_provider",
]
