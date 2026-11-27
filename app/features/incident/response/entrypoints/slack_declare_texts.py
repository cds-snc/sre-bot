"""The declare's words on Slack: ``DeclareTexts`` rendered from the ``incident_response`` catalogue.

A message posted to a conversation is rendered in the languages the service passes
for it, one line block per language in order (decisions/languages.md). The slots
that hold one text (topic, purpose, canvas, bookmark titles, report placeholders)
use the instance's first language. The product a declare names is the chosen
report placement's label; the record keeps no product.
"""

from collections.abc import Mapping

from capabilities.oncall.api import OnCallPerson
from contracts.languages import MultilingualText
from features.incident.common.vocabulary import Severity
from features.incident.core.api import (
    ConversationReference,
    Incident,
    MessageReference,
    ReportPlacement,
    ReportReference,
    VideoCallReference,
    slack_conversation_link,
)
from features.incident.core.api import translate as t

DECLARE_DOMAIN = "incident_response.declare"


def severity_label(severity: Severity) -> str:
    """What a severity reads as in the declare: ``SEV-<n>``."""
    return f"SEV-{severity.value}"


class SlackDeclareTexts:
    """``DeclareTexts`` for one Slack declare: the placement it names and the instance's first language."""

    def __init__(self, placement: ReportPlacement | None, *, primary: str) -> None:
        self._placement = placement
        self._primary = primary

    def topic(self, incident: Incident) -> str:
        """``Incident: <title> / <product>``."""
        return _t("post.topic", self._primary, name=incident.title, product=self._product(self._primary))

    def purpose(self, incident: Incident) -> str:
        """The incident's title."""
        return incident.title

    def canvas(self, incident: Incident) -> str:
        """The canvas's starting markdown."""
        return _t("post.canvas", self._primary)

    def announcement(
        self, incident: Incident, conversation: ConversationReference, languages: tuple[str, ...]
    ) -> MultilingualText:
        """Who declared which incident, for which product, in which channel."""
        return MultilingualText.of(
            languages,
            lambda language: _t(
                "post.announcement",
                language,
                user=f"<@{incident.declared_by}>",
                name=incident.title,
                product=self._product(language),
                channel=f"<#{conversation.vendor_id}>",
            ),
        )

    def severity_warning(self, incident: Incident, languages: tuple[str, ...]) -> MultilingualText | None:
        """The severity the incident was declared with; ``None`` while not rated."""
        severity = incident.severity
        if severity is None:
            return None
        return MultilingualText.of(
            languages, lambda language: _t("post.severity_warning", language, severity=severity_label(severity))
        )

    def report_bookmark(self) -> str:
        """The report bookmark's title."""
        return _t("post.report_bookmark", self._primary)

    def report_posted(self, report: ReportReference, languages: tuple[str, ...]) -> MultilingualText:
        """The link to the new report."""
        return MultilingualText.of(languages, lambda language: _t("post.report_posted", language, url=report.url or ""))

    def report_placeholders(
        self, incident: Incident, conversation: ConversationReference | None, on_call: tuple[OnCallPerson, ...]
    ) -> Mapping[str, str]:
        """The report template's placeholders: day, name, on-call people, product, channel link and status."""
        people = (person.email or (person.account.account_id if person.account else "") for person in on_call)
        return {
            "{{date}}": incident.declared_at.date().isoformat(),
            "{{name}}": incident.title,
            "{{on-call-names}}": ", ".join(person for person in people if person),
            "{{team}}": self._placement.label if self._placement is not None else "",
            "{{slack-channel}}": slack_conversation_link(conversation) if conversation is not None else "",
            "{{status}}": incident.status.value,
        }

    def video_call_bookmark(self) -> str:
        """The video call bookmark's title."""
        return _t("post.video_call_bookmark", self._primary)

    def video_call_posted(self, call: VideoCallReference, languages: tuple[str, ...]) -> MultilingualText:
        """The link to the new video call."""
        return MultilingualText.of(languages, lambda language: _t("post.video_call_posted", language, url=call.url or ""))

    def source_alert_bookmark(self) -> str:
        """The source alert bookmark's title."""
        return _t("post.source_alert_bookmark", self._primary)

    def source_alert_posted(self, alert: MessageReference, languages: tuple[str, ...]) -> MultilingualText:
        """The link to the alert; without its permalink, the channel it was posted in."""
        if alert.url:
            url = alert.url
            return MultilingualText.of(languages, lambda language: _t("post.source_alert_posted", language, url=url))
        channel = f"<#{alert.conversation_id}>"
        return MultilingualText.of(languages, lambda language: _t("post.source_alert_unlinked", language, channel=channel))

    def on_call_unavailable(self, incident: Incident, languages: tuple[str, ...]) -> MultilingualText:
        """Nobody on call was invited."""
        return MultilingualText.of(languages, lambda language: _t("post.on_call_unavailable", language))

    def next_steps(self, incident: Incident, languages: tuple[str, ...]) -> MultilingualText:
        """The commands responders use next."""
        return MultilingualText.of(languages, lambda language: _t("post.next_steps", language))

    def _product(self, language: str) -> str:
        return self._placement.label if self._placement is not None else _t("post.no_product", language)


def _t(key: str, locale: str, **variables: str) -> str:
    """Translate ``key`` of the declare catalogue; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{DECLARE_DOMAIN}.{key}"
    return t(full_key, locale, full_key, **variables)
