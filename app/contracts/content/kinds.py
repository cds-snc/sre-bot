"""Provisioned-content contract: the kind a plugin registers, the file model every kind extends, the read port.

A kind is one family of files an owning plugin reads from the content root, laid out as
``<root>/<owner>/<name>/[<folder>/...]<id>.yaml`` (decisions/provisioned-content.md). The
file model is the untrusted-input boundary for those files; what the loader hands consumers
is the frozen item the kind's ``build`` returns.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

CONTENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CONTENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
# A plugin's entry-point name may be dotted, as in "incident.response".
CONTENT_OWNER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[-.][a-z0-9]+)*$")
# Directory names under the content root that are never an owner: the generated schemas and the examples.
RESERVED_OWNERS = frozenset({"schemas", "examples"})


class ContentDocument(BaseModel):
    """The fields every provisioned file carries; a kind's file model extends it.

    The loader checks ``kind`` against the file's directory and ``version`` against the
    kind's supported versions before the rest of the model is validated.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(description="The owner and kind name the file belongs to, as '<owner>/<kind>'.")
    version: int = Field(description="The version of the kind's file format.")
    id: str = Field(
        pattern=CONTENT_ID_PATTERN.pattern,
        description="The item's identifier; it equals the file name without the .yaml extension.",
    )


@dataclass(frozen=True)
class ContentKind[M: ContentDocument, T]:
    """One kind of provisioned content, registered by the plugin that consumes it.

    Attributes:
        owner: The registering plugin's name, a namespace so two plugins cannot collide.
        name: The kind's plural kebab name, the directory under the owner.
        model: The file model; it extends ``ContentDocument``.
        build: Turns a validated file model into the frozen item consumers read.
        versions: The file format versions the kind accepts.
        required: Whether a deployment must provide at least one item.
        max_file_bytes: A file size limit lower than the instance ceiling, never higher.
        max_items: An item count limit lower than the instance ceiling, never higher.
    """

    owner: str
    name: str
    model: type[M]
    build: Callable[[M], T]
    versions: frozenset[int] = frozenset({1})
    required: bool = False
    max_file_bytes: int | None = None
    max_items: int | None = None
    key: str = field(init=False)

    def __post_init__(self) -> None:
        """Refuse a kind that could not be told apart from the layout's own directories."""
        if not CONTENT_OWNER_PATTERN.fullmatch(self.owner) or self.owner in RESERVED_OWNERS:
            raise ValueError(f"owner {self.owner!r} must be a lowercase plugin name and not one of {sorted(RESERVED_OWNERS)}")
        if not CONTENT_NAME_PATTERN.fullmatch(self.name):
            raise ValueError(f"name {self.name!r} must be lowercase kebab")
        if not self.versions or any(version < 1 for version in self.versions):
            raise ValueError("versions must be a non-empty set of positive integers")
        if (self.max_file_bytes is not None and self.max_file_bytes < 1) or (self.max_items is not None and self.max_items < 1):
            raise ValueError("max_file_bytes and max_items must be positive when set")
        object.__setattr__(self, "key", f"{self.owner}/{self.name}")


@dataclass(frozen=True)
class ContentProblem:
    """One thing wrong with the content; it names where, never the offending input."""

    kind: str
    file: str
    field: str
    message: str


class ContentLoadError(Exception):
    """Loading failed; ``problems`` lists every one found, so a deployment fixes them in one pass."""

    def __init__(self, problems: tuple[ContentProblem, ...]) -> None:
        super().__init__(f"{len(problems)} provisioned-content problem(s)")
        self.problems = problems


class ContentKindRegistrar(Protocol):
    """Registration boundary a plugin declares its content kinds through."""

    def register(self, kind: ContentKind[Any, Any]) -> None:
        """Register a kind; a second kind with the same owner and name is refused."""
        ...


class ContentCatalogue(Protocol):
    """Read port over the loaded content."""

    def items[T](self, kind: ContentKind[Any, T]) -> Mapping[str, T]:
        """Return the kind's items by id; empty when the deployment provides none."""
        ...
