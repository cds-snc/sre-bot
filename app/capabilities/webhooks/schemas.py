"""The capability's untrusted-input boundary: the sender-kind file model and the protocol envelopes.

A sender kind is provisioned content (decisions/provisioned-content.md): this model
validates every file, its JSON Schema is exported to ``app/content/schemas/`` and
``build_sender_kind`` turns a valid file into the frozen ``SenderKind`` the engines read.
Checks that need the [webhooks] limits, compile a path or parse a template raise ValueError,
so the loader reports the file and the field.

The SNS envelope is a discriminated union on ``Type`` (decisions/webhooks.md 2 Three layers):
a body that fits none of the variants fails its protocol's decode, and no other model is tried.
"""

from collections.abc import Callable
from typing import Annotated, Literal, Self

from liquid import Template
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from capabilities.webhooks.domain.events import EventType
from capabilities.webhooks.domain.extraction import compile_path
from capabilities.webhooks.domain.kinds import (
    AlertSpec,
    Condition,
    ConditionGroup,
    ConditionOp,
    FieldSpec,
    FieldType,
    GroupMode,
    LinkSpec,
    LocalizedTemplate,
    SenderKind,
)
from capabilities.webhooks.domain.limits import WebhookLimits
from capabilities.webhooks.domain.rendering import parse_template
from capabilities.webhooks.domain.values import normalise_https_url
from capabilities.webhooks.settings import content_settings
from contracts.content import ContentDocument, ContentKind

SENDER_KINDS_OWNER = "webhooks"
SENDER_KINDS_NAME = "sender-kinds"

FIELD_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
HANDLER_ID_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_-]*)+$"

type ScalarValue = Annotated[str, Field(max_length=1024)] | int | float | bool


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _limits() -> WebhookLimits:
    return content_settings().limits()


class ConditionFile(_Strict):
    """One test of the decoded payload."""

    path: str = Field(description="An RFC 9535 singular JSONPath query (name and index segments), such as $.Type.")
    op: ConditionOp = Field(description="The operator: equals, in, exists, starts_with or contains.")
    value: ScalarValue | list[ScalarValue] = Field(
        description="The operand: a scalar, a list for 'in', a boolean for 'exists', a string for 'starts_with'."
    )

    @field_validator("path")
    @classmethod
    def _singular(cls, path: str) -> str:
        compile_path(path)
        return path

    @model_validator(mode="after")
    def _operand_fits(self) -> Self:
        if self.op is ConditionOp.IN:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("'in' takes a non-empty list")
        elif isinstance(self.value, list):
            raise ValueError(f"'{self.op}' takes a single value")
        if self.op is ConditionOp.EXISTS and not isinstance(self.value, bool):
            raise ValueError("'exists' takes true or false")
        if self.op is ConditionOp.STARTS_WITH and not isinstance(self.value, str):
            raise ValueError("'starts_with' takes a string")
        return self


class GroupFile(_Strict):
    """Conditions combined: every one (all) or at least one (any). Exactly one of the two is set."""

    all: list[ConditionFile | GroupFile] | None = Field(default=None, min_length=1, description="Every item holds.")
    any: list[ConditionFile | GroupFile] | None = Field(default=None, min_length=1, description="One item holds.")

    @model_validator(mode="after")
    def _one_mode(self) -> Self:
        if (self.all is None) == (self.any is None):
            raise ValueError("a group sets exactly one of 'all' and 'any'")
        return self

    def items(self) -> list[ConditionFile | GroupFile]:
        return self.all if self.all is not None else self.any or []


class FieldFile(_Strict):
    """One field the kind extracts from the payload."""

    path: str = Field(description="An RFC 9535 singular JSONPath query.")
    type: FieldType = Field(default=FieldType.STRING, description="string, integer, number, boolean, string_list or url.")
    required: bool = Field(default=False, description="Whether a delivery without the field fails rendering.")
    allowed_hosts: list[str] = Field(
        default_factory=list, description="For a url field: the hosts a link may point at; any https host when empty."
    )

    @field_validator("path")
    @classmethod
    def _singular(cls, path: str) -> str:
        compile_path(path)
        return path

    @field_validator("allowed_hosts")
    @classmethod
    def _punycode_hosts(cls, hosts: list[str]) -> list[str]:
        return _hosts(hosts, _limits())

    @model_validator(mode="after")
    def _hosts_for_urls(self) -> Self:
        if self.allowed_hosts and self.type is not FieldType.URL:
            raise ValueError("allowed_hosts applies to url fields only")
        return self


class LocalizedTemplateFile(_Strict):
    """The bot's wording in every language the app supports, each a Liquid template."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    en_us: str = Field(alias="en-US", description="The English (en-US) template.")
    fr_fr: str = Field(alias="fr-FR", description="The French (fr-FR) template.")

    def by_language(self) -> dict[str, str]:
        """Return the templates keyed by language tag."""
        return {field.alias or name: getattr(self, name) for name, field in type(self).model_fields.items()}


class LinkFile(_Strict):
    """A link from a url field, under fixed wording that names no payload field."""

    field: str = Field(pattern=FIELD_NAME_PATTERN, description="The url field the link points at.")
    label: LocalizedTemplateFile = Field(description="The link's label in every supported language.")


class AlertFile(_Strict):
    """Templates for an alert's status, severity and dedup key."""

    status: str | None = Field(default=None, description="Renders firing, resolved or info; firing when absent.")
    severity: str | None = Field(default=None, description="Renders critical, error, warning or info; none when empty.")
    dedup_key: str | None = Field(default=None, description="Renders the key grouping deliveries of one condition.")


class TemplatesFile(_Strict):
    """The event's wording: the bot's title and summary per language, the sender's details once."""

    title: LocalizedTemplateFile = Field(description="The event's title, in every supported language.")
    summary: LocalizedTemplateFile = Field(description="The event's summary, in every supported language.")
    details: str | None = Field(
        default=None, description="The sender's own text, in its source language, shown once beside the bot's lines."
    )


class SenderKindFile(ContentDocument):
    """A webhook sender kind: which deliveries it matches, what it extracts and how the event reads."""

    event: Literal[EventType.ALERT, EventType.NOTIFICATION] = Field(description="The event type: alert or notification.")
    match: GroupFile = Field(description="The conditions a delivery must meet; kinds are tried in the instance's order.")
    fields: dict[Annotated[str, Field(pattern=FIELD_NAME_PATTERN)], FieldFile] = Field(
        default_factory=dict, description="The fields to extract, by name; templates read them as fields.<name>."
    )
    templates: TemplatesFile | None = Field(default=None, description="The wording; required unless suppress is true.")
    links: list[LinkFile] = Field(default_factory=list, description="Links built from url fields.")
    alert: AlertFile | None = Field(default=None, description="Alert values; only for event alert.")
    handler: str | None = Field(
        default=None, pattern=HANDLER_ID_PATTERN, description="A code handler a plugin registers, by its dotted id."
    )
    suppress: bool = Field(default=False, description="Match and post nothing.")
    mentions: bool = Field(default=False, description="Turn email addresses in the text into mentions.")

    @model_validator(mode="after")
    def _within_limits(self) -> Self:
        limits = _limits()
        conditions, depth = _measure(self.match)
        if conditions > limits.max_conditions:
            raise ValueError(f"match holds {conditions} conditions; the limit is {limits.max_conditions}")
        if depth > limits.max_condition_depth:
            raise ValueError(f"match nests {depth} groups deep; the limit is {limits.max_condition_depth}")
        if len(self.fields) > limits.max_extracted_fields:
            raise ValueError(f"{len(self.fields)} fields exceed the limit of {limits.max_extracted_fields}")
        if len(self.links) > limits.max_extracted_fields:
            raise ValueError(f"{len(self.links)} links exceed the limit of {limits.max_extracted_fields}")
        return self

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if not self.suppress and self.templates is None:
            raise ValueError("templates are required unless suppress is true")
        if self.alert is not None and self.event is not EventType.ALERT:
            raise ValueError("alert values apply to event alert only")
        for link in self.links:
            spec = self.fields.get(link.field)
            if spec is None or spec.type is not FieldType.URL:
                raise ValueError(f"link field {link.field!r} is not an extracted url field")
        return self

    @model_validator(mode="after")
    def _templates_parse(self) -> Self:
        limits = _limits()
        names = frozenset(self.fields)
        for location, source, allow_fields in self._template_sources():
            try:
                parse_template(source, limits, field_names=names, allow_fields=allow_fields)
            except ValueError as error:
                raise ValueError(f"{location}: {error}") from None
        return self

    def _template_sources(self) -> list[tuple[str, str, bool]]:
        sources: list[tuple[str, str, bool]] = []
        if self.templates is not None:
            for name in ("title", "summary"):
                localized: LocalizedTemplateFile = getattr(self.templates, name)
                sources += [(f"templates.{name}.{lang}", text, True) for lang, text in localized.by_language().items()]
            if self.templates.details is not None:
                sources.append(("templates.details", self.templates.details, True))
        for index, link in enumerate(self.links):
            sources += [(f"links.{index}.label.{lang}", text, False) for lang, text in link.label.by_language().items()]
        if self.alert is not None:
            for name in ("status", "severity", "dedup_key"):
                if (text := getattr(self.alert, name)) is not None:
                    sources.append((f"alert.{name}", text, True))
        return sources


def _measure(group: GroupFile, depth: int = 1) -> tuple[int, int]:
    """Return the number of conditions under ``group`` and its nesting depth."""
    conditions, deepest = 0, depth
    for item in group.items():
        if isinstance(item, GroupFile):
            count, nested = _measure(item, depth + 1)
            conditions, deepest = conditions + count, max(deepest, nested)
        else:
            conditions += 1
    return conditions, deepest


def build_sender_kind(document: SenderKindFile) -> SenderKind:
    """Compile a validated file into the frozen kind the engines read."""
    limits = _limits()
    names = frozenset(document.fields)

    def template(source: str, *, allow_fields: bool = True) -> Template:
        return parse_template(source, limits, field_names=names, allow_fields=allow_fields)

    def localized(file: LocalizedTemplateFile, *, allow_fields: bool = True) -> LocalizedTemplate:
        return LocalizedTemplate({lang: template(text, allow_fields=allow_fields) for lang, text in file.by_language().items()})

    templates = document.templates
    return SenderKind(
        id=document.id,
        event_type=EventType(document.event),
        match=_group(document.match),
        fields=tuple(
            FieldSpec(
                name=name,
                path=compile_path(spec.path),
                type=spec.type,
                required=spec.required,
                allowed_hosts=frozenset(spec.allowed_hosts),
            )
            for name, spec in document.fields.items()
        ),
        title=localized(templates.title) if templates else None,
        summary=localized(templates.summary) if templates else None,
        details=template(templates.details) if templates and templates.details is not None else None,
        links=tuple(LinkSpec(field=link.field, label=localized(link.label, allow_fields=False)) for link in document.links),
        alert=_alert(document, template),
        handler=document.handler,
        suppress=document.suppress,
        mentions=document.mentions,
    )


def _alert(document: SenderKindFile, template: Callable[[str], Template]) -> AlertSpec | None:
    """An alert kind's value templates; a notification kind has none."""
    if document.event is not EventType.ALERT:
        return None
    values = document.alert or AlertFile()
    return AlertSpec(
        status=template(values.status) if values.status is not None else None,
        severity=template(values.severity) if values.severity is not None else None,
        dedup_key=template(values.dedup_key) if values.dedup_key is not None else None,
    )


def _group(group: GroupFile) -> ConditionGroup:
    mode = GroupMode.ALL if group.all is not None else GroupMode.ANY
    return ConditionGroup(
        mode=mode,
        items=tuple(
            _group(item)
            if isinstance(item, GroupFile)
            else Condition(
                path=compile_path(item.path),
                op=item.op,
                value=tuple(item.value) if isinstance(item.value, list) else item.value,
            )
            for item in group.items()
        ),
    )


def _hosts(hosts: list[str], limits: WebhookLimits) -> list[str]:
    """Return each allowed host in punycode, as link hosts are compared."""
    normalised = []
    for host in hosts:
        url = normalise_https_url(f"https://{host}/", max_chars=limits.max_url_chars)
        if url is None:
            raise ValueError(f"allowed host {host!r} is not a host name")
        normalised.append(url.removeprefix("https://").removesuffix("/"))
    return normalised


def sender_kinds_content_kind() -> ContentKind[SenderKindFile, SenderKind]:
    """The sender-kind content kind: its file model, its builder and its limits.

    The plugin registers it and the extension point reads the loaded kinds through it; the
    catalogue keys items by the kind's owner and name, so both see the same items.
    """
    settings = content_settings()
    return ContentKind(
        owner=SENDER_KINDS_OWNER,
        name=SENDER_KINDS_NAME,
        model=SenderKindFile,
        build=build_sender_kind,
        max_file_bytes=settings.max_kind_file_bytes,
        max_items=settings.max_kinds,
    )


class _SnsEnvelope(BaseModel):
    """Fields every SNS message carries; unknown fields are ignored, every known one is strict text."""

    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)

    MessageId: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9-]+$")
    TopicArn: str = Field(min_length=1, max_length=1024)
    Message: str
    Timestamp: str = Field(min_length=1, max_length=64)
    SignatureVersion: str = Field(min_length=1, max_length=8)
    Signature: str = Field(min_length=1, max_length=4096)
    SigningCertURL: str = Field(min_length=1, max_length=2048)


class SnsNotification(_SnsEnvelope):
    """A message published to the topic."""

    Type: Literal["Notification"]
    Subject: str | None = Field(default=None, max_length=100)
    UnsubscribeURL: str | None = Field(default=None, max_length=2048)


class SnsSubscriptionConfirmation(_SnsEnvelope):
    """SNS asks the endpoint to confirm a subscription."""

    Type: Literal["SubscriptionConfirmation"]
    Token: str = Field(min_length=1, max_length=2048)
    SubscribeURL: str = Field(min_length=1, max_length=2048)


class SnsUnsubscribeConfirmation(_SnsEnvelope):
    """SNS reports that the subscription was removed."""

    Type: Literal["UnsubscribeConfirmation"]
    Token: str = Field(min_length=1, max_length=2048)
    SubscribeURL: str = Field(min_length=1, max_length=2048)


type SnsMessage = Annotated[
    SnsNotification | SnsSubscriptionConfirmation | SnsUnsubscribeConfirmation, Field(discriminator="Type")
]
SNS_MESSAGE = TypeAdapter[SnsMessage](SnsMessage)
