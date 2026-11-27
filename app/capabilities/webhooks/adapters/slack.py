"""The Slack channel poster: platform-neutral messages laid out as Block Kit, every value escaped.

Output encoding (decisions/webhooks.md 9, security.md Webhooks): every content-derived value
is escaped for mrkdwn (``&``, ``<``, ``>``) in a text object with ``verbatim: true``, and only
then are trusted tokens inserted: mentions this adapter resolved and links built from the
re-encoded https URLs. ``plain_text`` carries only code-owned wording (button labels). Each
limit is measured on the escaped text and escaping is the last step, so a cut never splits
an entity or a token.

Calls are bounded by the delivery: the clients carry a short per-attempt timeout, a post is
never retried in process (a 429's ``retry_after`` goes back to the inbox), and email lookups
are capped per delivery and cached across its destinations, hits and misses alike.
"""

import asyncio
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import aiohttp
import structlog
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from capabilities.webhooks.domain.events import Link
from capabilities.webhooks.domain.extensions import EventAction
from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.domain.mentions import find_email_addresses
from capabilities.webhooks.domain.messages import ChannelMessage, FallbackMessage, OutboundMessage, PassthroughMessage
from capabilities.webhooks.domain.values import ELLIPSIS, truncate
from capabilities.webhooks.interfaces import ChannelPoster, DeliveryPoster
from capabilities.webhooks.settings import WebhooksSettings
from contracts.operations import ErrorCode, OperationResult
from contracts.workplace import WorkplaceSystem
from integrations.slack.client import classify_slack_error, get_async_slack_web_client, get_async_slack_write_client
from integrations.slack.settings import get_slack_settings

logger = structlog.get_logger()

# Slack API facts (docs.slack.dev Block Kit and chat.postMessage references), not tuning.
SECTION_TEXT_CHARS = 3000
MAX_BLOCKS = 50
MAX_ACTIONS = 25
BUTTON_LABEL_CHARS = 75
BUTTON_VALUE_CHARS = 2000
ACTION_ID_CHARS = 255
MESSAGE_TEXT_CHARS = 4000

_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
_USER_ID = re.compile(r"[UW][A-Z0-9]{2,}")
_LINK_BREAKERS = frozenset("|<> \t\r\n")
_WHITESPACE = re.compile(r"(\s+)")
_SLACK_UNREACHABLE = (TimeoutError, aiohttp.ClientError)
# chat.postMessage arguments a sender-built message may set; any other key (``channel``,
# ``token``, ``as_user``...) is never forwarded, so a payload cannot pick the conversation or
# the credential (OWASP API10:2023). TODO(TASK-37.5): drop the hardening fields as well.
PASSTHROUGH_ARGUMENTS = (
    "attachments",
    "blocks",
    "icon_emoji",
    "icon_url",
    "link_names",
    "mrkdwn",
    "parse",
    "reply_broadcast",
    "text",
    "thread_ts",
    "unfurl_links",
    "unfurl_media",
    "username",
)


@dataclass(frozen=True)
class _Token:
    """Trusted mrkdwn the adapter built: inserted as is and never cut."""

    text: str


type _Part = str | _Token


def escape_mrkdwn(text: str) -> str:
    """Escape Slack's three control characters, ``&`` first."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fit(parts: Sequence[_Part], budget: int) -> str:
    """Join ``parts`` escaped, cut so the escaped result fits ``budget``.

    Raw text is escaped character by character as it is counted, so the cut falls on a
    whole escaped character; a token is kept whole or dropped. A cut ends in an ellipsis
    inside the budget.
    """
    rendered = [part.text if isinstance(part, _Token) else escape_mrkdwn(part) for part in parts]
    if sum(map(len, rendered)) <= budget:
        return "".join(rendered)
    room = budget - len(ELLIPSIS)
    kept: list[str] = []
    for part in parts:
        pieces = (part.text,) if isinstance(part, _Token) else (_ESCAPES.get(character, character) for character in part)
        for piece in pieces:
            if len(piece) > room:
                return "".join(kept) + ELLIPSIS
            kept.append(piece)
            room -= len(piece)
    return "".join(kept) + ELLIPSIS


def _with_mentions(text: str, resolved: Mapping[str, str]) -> list[_Part]:
    """Split ``text`` into raw text and mention tokens for the resolved addresses in it."""
    if not resolved:
        return [text]
    parts: list[_Part] = []
    for chunk in _WHITESPACE.split(text):
        found = find_email_addresses(chunk, 1) if "@" in chunk else ()
        user_id = resolved.get(found[0]) if found else None
        start = chunk.lower().find(found[0].lower()) if found and user_id else -1
        if user_id is None or start < 0:
            parts.append(chunk)
            continue
        parts.extend([chunk[:start], _Token(f"<@{user_id}>"), chunk[start + len(found[0]) :]])
    return parts


def _section(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text, "verbatim": True}}


def _link(link: Link, label: str) -> _Token:
    return _Token(f"<{link.url}|{fit([label], SECTION_TEXT_CHARS // 4)}>")


def _button(action: EventAction) -> dict[str, Any] | None:
    if len(action.action_id) > ACTION_ID_CHARS or len(action.value) > BUTTON_VALUE_CHARS:
        logger.warning("webhook_action_dropped", reason="over_platform_limit")
        return None
    label = truncate(" / ".join(text for _, text in action.label.parts), BUTTON_LABEL_CHARS)
    return {"type": "button", "text": {"type": "plain_text", "text": label}, "action_id": action.action_id, "value": action.value}


class SlackDeliveryPoster(DeliveryPoster):
    """Posts one delivery's messages to Slack; caches its mention lookups for the delivery."""

    def __init__(self, *, writes: AsyncWebClient, reads: AsyncWebClient, tenant: str, lookups_per_message: int) -> None:
        self._writes = writes
        self._reads = reads
        self._tenant = tenant
        self._lookup_budget = lookups_per_message
        self._lookups = 0
        self._cache: dict[str, str | None] = {}

    async def post(self, destination: Destination, message: OutboundMessage) -> OperationResult[str]:
        """Lay out ``message`` and post it; failures are classified, never retried here."""
        if destination.system is not WorkplaceSystem.SLACK or destination.tenant != self._tenant:
            return OperationResult.permanent_error("destination is not in the configured Slack tenant", ErrorCode.TENANT_MISMATCH)
        if isinstance(message, PassthroughMessage):
            arguments = {name: message.message[name] for name in PASSTHROUGH_ARGUMENTS if name in message.message}
        else:
            if isinstance(message, ChannelMessage):
                blocks, text = await self._channel_layout(message)
            else:
                blocks, text = _fallback_layout(message)
            arguments = {"text": text, "blocks": blocks, "unfurl_links": False, "unfurl_media": False}
        try:
            response = await self._writes.chat_postMessage(channel=destination.conversation_id, **arguments)
        except SlackApiError as exc:
            status, code, retry_after = classify_slack_error(exc)
            return OperationResult.error(status=status, message="slack post failed", error_code=code, retry_after=retry_after)
        except TimeoutError:
            return OperationResult.transient_error("slack post timed out", error_code=ErrorCode.TIMEOUT)
        except aiohttp.ClientError:
            return OperationResult.transient_error("slack post did not complete", error_code=ErrorCode.CONNECTION_ERROR)
        timestamp = response.get("ts")
        return OperationResult.success(data=timestamp if isinstance(timestamp, str) else None)

    async def _channel_layout(self, message: ChannelMessage) -> tuple[list[dict[str, Any]], str]:
        summaries = dict(message.summary.parts)
        resolved = await self._mentions(message) if message.mentions else {}
        blocks: list[dict[str, Any]] = []
        for language, title in message.title.parts:
            parts: list[_Part] = [_Token(f"*{fit([title], SECTION_TEXT_CHARS // 2)}*")]
            if summary := summaries.get(language):
                parts += [_Token("\n"), *_with_mentions(summary, resolved)]
            for link in message.links:
                label = dict(link.label.parts).get(language)
                if label and not _LINK_BREAKERS.intersection(link.url):
                    parts += [_Token("\n"), _link(link, label)]
            blocks.append(_section(fit(parts, SECTION_TEXT_CHARS)))
        if message.details:
            blocks.append(_section(fit(_with_mentions(message.details, resolved), SECTION_TEXT_CHARS)))
        buttons = [button for action in message.actions[:MAX_ACTIONS] if (button := _button(action)) is not None]
        if buttons:
            blocks.append({"type": "actions", "elements": buttons})
        lines = [line for language, title in message.title.parts for line in (title, summaries.get(language, "")) if line]
        text = fit(["\n".join([*lines, message.details or ""]).strip()], MESSAGE_TEXT_CHARS)
        return blocks[:MAX_BLOCKS], text

    async def _mentions(self, message: ChannelMessage) -> dict[str, str]:
        texts = [text for _, text in message.summary.parts] + [message.details or ""]
        addresses = find_email_addresses("\n".join(texts), self._lookup_budget)
        pending = [address for address in addresses if address not in self._cache][: max(self._lookup_budget - self._lookups, 0)]
        self._lookups += len(pending)
        self._cache.update(zip(pending, await asyncio.gather(*(self._lookup(address) for address in pending)), strict=True))
        resolved = {address: user_id for address in addresses if (user_id := self._cache.get(address))}
        logger.debug("webhook_mentions_resolved", found=len(addresses), looked_up=len(pending), resolved=len(resolved))
        return resolved

    async def _lookup(self, address: str) -> str | None:
        try:
            response = await self._reads.users_lookupByEmail(email=address)
        except (SlackApiError, *_SLACK_UNREACHABLE):
            return None
        user = response.get("user")
        user_id = user.get("id") if isinstance(user, dict) else None
        return user_id if isinstance(user_id, str) and _USER_ID.fullmatch(user_id) else None


def _fallback_layout(message: FallbackMessage) -> tuple[list[dict[str, Any]], str]:
    header: list[_Part] = []
    for _, line in message.header.parts:
        header += [_Token("*"), line, _Token("*\n")]
    header.append(message.source)
    blocks = [_section(fit(header, SECTION_TEXT_CHARS))]
    if message.body:
        blocks.append(_section(fit([message.body], SECTION_TEXT_CHARS)))
    text = fit([f"{message.header.plain_text()}\n{message.source}\n{message.body}".strip()], MESSAGE_TEXT_CHARS)
    return blocks, text


class SlackChannelPoster(ChannelPoster):
    """The Slack poster for one tenant; each delivery gets its own lookup cache."""

    def __init__(self, *, writes: AsyncWebClient, reads: AsyncWebClient, tenant: str, lookups_per_message: int) -> None:
        self._writes = writes
        self._reads = reads
        self._tenant = tenant
        self._lookups_per_message = lookups_per_message

    def for_delivery(self) -> SlackDeliveryPoster:
        """A poster holding this delivery's mention cache."""
        return SlackDeliveryPoster(
            writes=self._writes, reads=self._reads, tenant=self._tenant, lookups_per_message=self._lookups_per_message
        )


def build_slack_poster(settings: WebhooksSettings) -> SlackChannelPoster | None:
    """The Slack poster on the configured tenant, or None when Slack is not configured.

    Posts get no in-process retry (the inbox is the one retry point) and lookups none
    either; both carry the per-attempt timeout (decisions/outbound-clients.md).
    """
    tenant = get_slack_settings().tenant
    if tenant is None:
        return None
    timeout = settings.post_attempt_timeout_seconds
    return SlackChannelPoster(
        writes=get_async_slack_write_client(timeout_seconds=timeout, rate_limit_retries=0),
        reads=get_async_slack_web_client(timeout_seconds=timeout, retries=0),
        tenant=tenant.tenant_id,
        lookups_per_message=settings.email_lookups_per_message,
    )
