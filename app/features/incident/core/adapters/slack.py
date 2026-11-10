"""Slack adapters implementing ``IncidentTranscriptReader`` and ``IncidentConversation`` on the Slack Web API.

``SlackIncidentTranscriptReader`` owns everything Slack-shaped about a
transcript: the history and thread-replies calls, their cursor paging and
timestamp format, display-name resolution, chronological ordering, and the
optional filtering of this bot's own posts and Slack system events. It reads on
the synchronous Web client its callers still use.

``SlackIncidentConversation`` writes to an incident's conversation on the async
write handle, which retries only rate-limited requests, and checks writability
on the async read client.

Both take the incident's ``ConversationReference``; a reference of another
system is refused as ``UNSUPPORTED_OPERATION`` before any call. Slack errors are
classified through the Slack vendor table (``classify_slack_error``): the codes
for a conversation the bot cannot write to become ``CONVERSATION_NOT_WRITABLE``,
and a code the table does not name propagates. A failure after a transcript's
first page (a later page, a thread, a name or identity lookup) is logged and the
read keeps what it has.
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.web import SlackResponse
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.workplace import WorkplaceSystem
from features.incident.core.domain import ConversationName, ConversationReference, MessageReference, TranscriptMessage
from integrations.slack.client import (
    classify_slack_error,
    get_async_slack_web_client,
    get_async_slack_write_client,
    get_slack_web_client,
)
from integrations.slack.settings import get_slack_settings

logger = structlog.get_logger()

# Slack system events that are channel plumbing, not incident conversation.
_SYSTEM_SUBTYPES = frozenset(
    {
        "bot_add",
        "bot_remove",
        "pinned_item",
        "unpinned_item",
        "group_join",
        "group_leave",
        "group_topic",
        "group_purpose",
        "group_name",
        "reminder_add",
        "tombstone",
    }
)


class SlackIncidentTranscriptReader:
    """Read an incident conversation's start time and transcript from Slack."""

    def __init__(self, client: WebClient) -> None:
        self._client = client

    def conversation_started_at(self, conversation: ConversationReference) -> OperationResult[datetime | None]:
        """Return the channel's creation time; ``None`` when Slack gives none.

        A failed ``conversations.info`` call (a missing ``channels:read`` or
        ``groups:read`` scope, for one) is the classified result.
        """
        if conversation.system is not WorkplaceSystem.SLACK:
            return _transcript_unsupported(conversation)
        log = logger.bind(conversation_id=conversation.vendor_id)
        try:
            response = self._client.conversations_info(channel=conversation.vendor_id)
        except SlackApiError as exc:
            return _transcript_failure(exc, "incident_transcript_conversation_info_failed", log)
        created = (response.get("channel") or {}).get("created")
        try:
            return OperationResult.success(None if created is None else datetime.fromtimestamp(float(created), tz=UTC))
        except TypeError, ValueError:
            return OperationResult.success(None)

    def read_transcript(
        self,
        conversation: ConversationReference,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> OperationResult[Sequence[TranscriptMessage]]:
        """Return the channel's messages since ``since``, thread replies included, oldest first.

        Decisive facts often land in threads, so every message Slack reports
        replies for is expanded with them. ``limit`` caps the whole transcript
        and the newest messages are kept. A failed first history page is the
        classified result; a failed later page or thread is logged and skipped.
        """
        if conversation.system is not WorkplaceSystem.SLACK:
            return _transcript_unsupported(conversation)
        conversation_id = conversation.vendor_id
        log = logger.bind(conversation_id=conversation_id)
        try:
            top_level = self._read_history(conversation_id, since=since, limit=limit, log=log)
        except SlackApiError as exc:
            return _transcript_failure(exc, "incident_transcript_history_fetch_failed", log)

        raw_messages = _merge_chronologically(top_level, self._read_thread_replies(conversation_id, top_level, limit, log))[
            -limit:
        ]

        name_cache: dict[str, str] = {}
        messages: list[TranscriptMessage] = []
        identity = self._resolve_self_identity(log) if exclude_own_and_system_messages else {}
        skipped = 0

        for raw in raw_messages:
            text = (raw.get("text") or "").strip()
            user_id = raw.get("user")
            if not text or not (user_id or raw.get("bot_id")):
                continue
            if exclude_own_and_system_messages and _is_channel_event(raw):
                # "set the channel topic", joins/leaves and similar system events
                # are channel plumbing, never incident facts.
                skipped += 1
                continue
            # Webhook and alerting posts carry only a bot id; they are named
            # from their bot fields rather than looked up as a user.
            author = self._resolve_display_name(user_id, name_cache, log) if user_id else _bot_name(raw)
            if _is_own_message(raw, author, identity):
                # This bot's own posts (topic changes, hangout links, "an incident
                # report has been created at...") are scaffolding. Other bots are
                # kept: an alerting bot's message is often the first real event.
                skipped += 1
                continue
            messages.append(
                TranscriptMessage(author=author, text=text, posted_at=_posted_at(raw.get("ts")), is_bot=_is_bot_post(raw))
            )

        log.info(
            "incident_transcript_history_fetched",
            raw_count=len(raw_messages),
            kept_count=len(messages),
            skipped_own_and_system_messages=skipped,
        )
        return OperationResult.success(messages)

    def _read_history(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        log: structlog.stdlib.BoundLogger,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``limit`` top-level messages since ``since``, oldest first.

        Follows Slack's cursor across pages. The first page's failure is raised
        for the caller to classify; a later page's classified failure keeps what was read.
        """
        newest_first: list[Mapping[str, Any]] = []
        cursor = ""
        while len(newest_first) < limit:
            kwargs: dict[str, Any] = {
                "channel": conversation_id,
                "limit": limit - len(newest_first),
                "oldest": f"{since.timestamp():.6f}",
            }
            if cursor:
                kwargs["cursor"] = cursor
            try:
                response = self._client.conversations_history(**kwargs)
            except SlackApiError as exc:
                if not cursor:
                    raise
                _raise_if_unclassified(exc)
                log.warning("incident_transcript_history_page_failed", error=str(exc), read_so_far=len(newest_first))
                break
            newest_first.extend(response.get("messages") or [])
            cursor = _next_cursor(response)
            if not cursor:
                break
        # conversations_history returns newest-first; the transcript is chronological.
        return list(reversed(newest_first[:limit]))

    def _read_thread_replies(
        self,
        conversation_id: str,
        top_level: Sequence[Mapping[str, Any]],
        limit: int,
        log: structlog.stdlib.BoundLogger,
    ) -> list[Mapping[str, Any]]:
        """Return the replies of every threaded top-level message, without the parents.

        A thread whose replies fail with a classified Slack error is logged and skipped.
        """
        replies: list[Mapping[str, Any]] = []
        for parent in top_level:
            thread_ts = parent.get("ts")
            if not thread_ts or not parent.get("reply_count"):
                continue
            cursor = ""
            try:
                while True:
                    kwargs: dict[str, Any] = {"channel": conversation_id, "ts": thread_ts, "limit": limit}
                    if cursor:
                        kwargs["cursor"] = cursor
                    response = self._client.conversations_replies(**kwargs)
                    # Slack repeats the parent as the first message of every thread read.
                    replies.extend(m for m in response.get("messages") or [] if m.get("ts") != thread_ts)
                    cursor = _next_cursor(response)
                    if not cursor:
                        break
            except SlackApiError as exc:
                _raise_if_unclassified(exc)
                log.warning("incident_transcript_replies_fetch_failed", thread_ts=thread_ts, error=str(exc))
        return replies

    def _resolve_self_identity(self, log: structlog.stdlib.BoundLogger) -> dict[str, str]:
        """Return this bot's own ``user_id``, ``bot_id`` and name from ``auth.test``.

        Matching on the user id alone proved unreliable -- depending on how a
        message was posted it may carry only a ``bot_id``, or a display name that
        differs from the authenticated user. All three signals are collected so
        ``_is_own_message`` can match on any of them. Returns an empty mapping if
        the lookup fails with a classified Slack error, which disables the filter
        rather than failing the read.
        """
        try:
            response = self._client.auth_test()
        except SlackApiError as exc:
            _raise_if_unclassified(exc)
            log.warning("incident_transcript_auth_test_failed", error=str(exc))
            return {}

        identity = {
            "user_id": str(response.get("user_id") or ""),
            "bot_id": str(response.get("bot_id") or ""),
            "name": _normalize_name(str(response.get("user") or "")),
        }
        log.info("incident_transcript_self_identity", **identity)
        return identity

    def _resolve_display_name(
        self,
        user_id: str,
        cache: dict[str, str],
        log: structlog.stdlib.BoundLogger,
    ) -> str:
        """Resolve a Slack user's display name, caching lookups; fall back to the id."""
        if user_id in cache:
            return cache[user_id]

        name = user_id
        try:
            user: Mapping[str, Any] = self._client.users_info(user=user_id).get("user") or {}
            profile: Mapping[str, Any] = user.get("profile") or {}
            name = profile.get("display_name") or profile.get("real_name") or user.get("real_name") or user_id
        except SlackApiError as exc:
            _raise_if_unclassified(exc)
            log.warning("incident_transcript_user_lookup_failed", user_id=user_id, error=str(exc))

        cache[user_id] = name
        return name


def build_incident_transcript_reader() -> SlackIncidentTranscriptReader:
    """Build the adapter on the bot's Web client."""
    return SlackIncidentTranscriptReader(get_slack_web_client())


# Slack answers an invite of someone already there, or of the bot itself, with an
# error; for the incident the invite is done.
_INVITE_DONE = frozenset({"already_in_channel", "cant_invite_self"})
_ARCHIVE_DONE = frozenset({"already_archived"})
_CANVAS_DONE = frozenset({"channel_canvas_already_exists"})
_NAME_TAKEN = "name_taken"
_OWN_CONVERSATION_TYPES = "public_channel,private_channel"
_OWN_CONVERSATIONS_PAGE = 200
_CHANNEL_NAME_MAX = 80
_CHANNEL_NAME_REFUSED = re.compile(r"[^a-z0-9_-]+")


def slack_channel_name(name: ConversationName) -> str:
    """Render ``name`` under Slack's channel rules: lowercase letters, digits, ``-`` and ``_``, at most 80 characters.

    Accents are dropped and every other run of refused characters becomes one dash.
    The prefix and title are cut to fit before the attempt suffix, so every attempt
    keeps its number and stays distinct.
    """
    ascii_title = unicodedata.normalize("NFKD", name.title).encode("ascii", "ignore").decode("ascii").lower()
    slug = _CHANNEL_NAME_REFUSED.sub("-", ascii_title).strip("-")
    base = name.prefix + (f"-{slug}" if slug else "")
    if not name.suffix:
        return base[:_CHANNEL_NAME_MAX]
    return base[: _CHANNEL_NAME_MAX - len(name.suffix)].rstrip("-") + name.suffix


class SlackIncidentConversation:
    """Write to an incident's Slack channel and say whether the bot can.

    ``reads`` is the async bot client (``conversations.info``, ``users.conversations``,
    ``usergroups.users.list``); ``writes`` is the write handle, which retries only
    rate-limited requests, so a create or a post is never replayed after Slack may
    already have applied it. ``tenant`` is the configured Slack tenant id, which
    names the channels this adapter creates or finds; ``None`` when Slack has no
    tenant entry.
    """

    def __init__(self, reads: AsyncWebClient, writes: AsyncWebClient, *, tenant: str | None = None) -> None:
        self._reads = reads
        self._writes = writes
        self._tenant = tenant

    async def create(self, name: ConversationName, *, private: bool) -> OperationResult[ConversationReference]:
        """Create the channel named ``slack_channel_name(name)`` in one call; ``is_private`` only for a private one.

        ``name_taken`` is reported as ``CONVERSATION_NAME_TAKEN`` and logged at
        info: the caller tries its next name.
        """
        if self._tenant is None:
            return _slack_not_configured()
        channel_name = slack_channel_name(name)
        arguments: dict[str, Any] = {"name": channel_name}
        if private:
            arguments["is_private"] = True
        try:
            response = await self._writes.conversations_create(**arguments)
        except SlackApiError as exc:
            if exc.response.get("error") == _NAME_TAKEN:
                logger.info("incident_conversation_name_taken", name=channel_name)
                return OperationResult.permanent_error(
                    f"Slack channel name taken: {channel_name}", ErrorCode.CONVERSATION_NAME_TAKEN
                )
            return _named_failure("create", channel_name, exc)
        channel: Mapping[str, Any] = response.get("channel") or {}
        return OperationResult.success(
            ConversationReference(system=WorkplaceSystem.SLACK, tenant=self._tenant, vendor_id=str(channel.get("id")))
        )

    async def find_own(self, name: ConversationName) -> OperationResult[ConversationReference | None]:
        """Page through the bot's non-archived channels, public and private, for one named ``slack_channel_name(name)``."""
        if self._tenant is None:
            return _slack_not_configured()
        channel_name = slack_channel_name(name)
        cursor: str | None = None
        while True:
            try:
                response = await self._reads.users_conversations(
                    types=_OWN_CONVERSATION_TYPES, exclude_archived=True, limit=_OWN_CONVERSATIONS_PAGE, cursor=cursor
                )
            except SlackApiError as exc:
                return _named_failure("find_own", channel_name, exc)
            for channel in response.get("channels") or []:
                if channel.get("name") == channel_name:
                    return OperationResult.success(
                        ConversationReference(system=WorkplaceSystem.SLACK, tenant=self._tenant, vendor_id=str(channel["id"]))
                    )
            cursor = _next_cursor(response) or None
            if cursor is None:
                return OperationResult.success(None)

    async def post(
        self, conversation: ConversationReference, text: str, *, blocks: Sequence[Mapping[str, object]] = ()
    ) -> OperationResult[MessageReference]:
        """Post ``text`` (with ``blocks`` when given) to the channel and return the message's reference (its ``ts``)."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        arguments: dict[str, Any] = {"channel": conversation.vendor_id, "text": text}
        if blocks:
            arguments["blocks"] = list(blocks)
        try:
            response = await self._writes.chat_postMessage(**arguments)
        except SlackApiError as exc:
            return _conversation_failure("post", conversation, exc)
        return OperationResult.success(
            MessageReference(
                system=WorkplaceSystem.SLACK,
                tenant=conversation.tenant,
                conversation_id=str(response.get("channel") or conversation.vendor_id),
                message_id=str(response.get("ts")),
            )
        )

    async def set_purpose(self, conversation: ConversationReference, text: str) -> OperationResult[None]:
        """Set the channel's purpose to ``text``."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        try:
            await self._writes.conversations_setPurpose(channel=conversation.vendor_id, purpose=text)
        except SlackApiError as exc:
            return _conversation_failure("set_purpose", conversation, exc)
        return OperationResult.success()

    async def set_topic(self, conversation: ConversationReference, text: str) -> OperationResult[None]:
        """Set the channel's topic to ``text``."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        try:
            await self._writes.conversations_setTopic(channel=conversation.vendor_id, topic=text)
        except SlackApiError as exc:
            return _conversation_failure("set_topic", conversation, exc)
        return OperationResult.success()

    async def create_canvas(self, conversation: ConversationReference, markdown: str) -> OperationResult[None]:
        """Create the channel canvas from ``markdown``; a channel that has one counts as done."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        try:
            await self._writes.conversations_canvases_create(
                channel_id=conversation.vendor_id, document_content={"type": "markdown", "markdown": markdown}
            )
        except SlackApiError as exc:
            if exc.response.get("error") in _CANVAS_DONE:
                return OperationResult.success()
            return _conversation_failure("create_canvas", conversation, exc)
        return OperationResult.success()

    async def group_members(self, conversation: ConversationReference, group_id: str) -> OperationResult[tuple[str, ...]]:
        """Read the user group's member ids on the read client."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        try:
            response = await self._reads.usergroups_users_list(usergroup=group_id)
        except SlackApiError as exc:
            return _conversation_failure("group_members", conversation, exc)
        return OperationResult.success(tuple(str(user) for user in response.get("users") or []))

    async def add_bookmark(self, conversation: ConversationReference, title: str, link: str) -> OperationResult[None]:
        """Add a link bookmark titled ``title`` to the channel."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        try:
            await self._writes.bookmarks_add(channel_id=conversation.vendor_id, title=title, type="link", link=link)
        except SlackApiError as exc:
            return _conversation_failure("add_bookmark", conversation, exc)
        return OperationResult.success()

    async def invite(self, conversation: ConversationReference, account_ids: Sequence[str]) -> OperationResult[None]:
        """Invite the Slack accounts in one call; members already there and the bot itself count as invited.

        ``force`` lets the other accounts in when one of them cannot be invited.
        No accounts makes no call.
        """
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        if not account_ids:
            return OperationResult.success()
        try:
            await self._writes.conversations_invite(channel=conversation.vendor_id, users=list(account_ids), force=True)
        except SlackApiError as exc:
            if exc.response.get("error") in _INVITE_DONE:
                return OperationResult.success()
            return _conversation_failure("invite", conversation, exc)
        return OperationResult.success()

    async def archive(self, conversation: ConversationReference) -> OperationResult[None]:
        """Archive the channel; a channel already archived counts as archived."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        try:
            await self._writes.conversations_archive(channel=conversation.vendor_id)
        except SlackApiError as exc:
            if exc.response.get("error") in _ARCHIVE_DONE:
                return OperationResult.success()
            return _conversation_failure("archive", conversation, exc)
        return OperationResult.success()

    async def is_writable(self, conversation: ConversationReference) -> OperationResult[bool]:
        """Say whether the bot can write to the channel: not archived and a member. Never joins."""
        if conversation.system is not WorkplaceSystem.SLACK:
            return _conversation_unsupported(conversation)
        try:
            response = await self._reads.conversations_info(channel=conversation.vendor_id)
        except SlackApiError as exc:
            return _conversation_failure("is_writable", conversation, exc)
        channel: Mapping[str, Any] = response.get("channel") or {}
        return OperationResult.success(not channel.get("is_archived") and channel.get("is_member") is True)


def build_incident_conversation() -> SlackIncidentConversation:
    """Build the adapter on the bot's async read client, its rate-limit-only write handle and the Slack tenant id."""
    tenant = get_slack_settings().tenant
    return SlackIncidentConversation(
        get_async_slack_web_client(),
        get_async_slack_write_client(),
        tenant=tenant.tenant_id if tenant is not None else None,
    )


def _conversation_unsupported[T](conversation: ConversationReference) -> OperationResult[T]:
    logger.warning("incident_conversation_system_unsupported", system=conversation.system.value)
    return OperationResult.permanent_error(
        f"Slack cannot reach a conversation on {conversation.system.value}", ErrorCode.UNSUPPORTED_OPERATION
    )


def _conversation_failure[T](operation: str, conversation: ConversationReference, exc: SlackApiError) -> OperationResult[T]:
    """Classify a Slack error on ``operation``; a code the Slack table does not name propagates."""
    return _classified_failure(operation, exc, conversation_id=conversation.vendor_id)


def _named_failure[T](operation: str, name: str, exc: SlackApiError) -> OperationResult[T]:
    """Classify a Slack error on ``operation`` for the channel name ``name``; an unnamed code propagates."""
    return _classified_failure(operation, exc, name=name)


def _classified_failure[T](operation: str, exc: SlackApiError, **context: str) -> OperationResult[T]:
    status, code, retry_after = classify_slack_error(exc)
    logger.warning(f"incident_conversation_{operation}_failed", **context, slack_error=code, status=status.value)
    not_writable = code in get_slack_settings().not_writable_errors
    return OperationResult(
        status=status,
        message=f"Slack {operation} failed: {code}",
        error_code=ErrorCode.CONVERSATION_NOT_WRITABLE if not_writable else code,
        retry_after=retry_after,
        cause=exc,
    )


def _slack_not_configured[T]() -> OperationResult[T]:
    return OperationResult.permanent_error("slack.tenant is not configured", ErrorCode.CONFIG_NOT_CONFIGURED)


def _raise_if_unclassified(exc: SlackApiError) -> None:
    """Re-raise a Slack error whose code the Slack table does not name; a classified one is only logged by the caller."""
    classify_slack_error(exc)


def _transcript_unsupported[T](conversation: ConversationReference) -> OperationResult[T]:
    logger.warning("incident_transcript_system_unsupported", system=conversation.system.value)
    return OperationResult.permanent_error(
        f"Slack cannot read a conversation on {conversation.system.value}", ErrorCode.UNSUPPORTED_OPERATION
    )


def _transcript_failure[T](exc: SlackApiError, event: str, log: structlog.stdlib.BoundLogger) -> OperationResult[T]:
    """Classify a failed transcript read; a code the Slack table does not name propagates."""
    status, code, retry_after = classify_slack_error(exc)
    log.warning(event, error=str(exc), slack_error=code, status=status.value)
    return OperationResult(
        status=status,
        message=f"Slack transcript read failed: {code}",
        error_code=code,
        retry_after=retry_after,
        cause=exc,
    )


def _is_own_message(raw: Mapping[str, Any], author: str, identity: dict[str, str]) -> bool:
    """Whether a message was posted by this bot, matched on any known signal."""
    if not identity:
        return False
    if identity.get("user_id") and raw.get("user") == identity["user_id"]:
        return True
    if identity.get("bot_id") and raw.get("bot_id") == identity["bot_id"]:
        return True
    # Display name is the last resort: it catches posts made under an identity
    # auth_test does not report, which is how bot messages slipped through.
    own_name = identity.get("name")
    return bool(own_name) and _normalize_name(author) == own_name


def _is_channel_event(raw: Mapping[str, Any]) -> bool:
    """Whether a message is a Slack system event rather than someone talking."""
    subtype = str(raw.get("subtype") or "")
    return subtype.startswith("channel_") or subtype in _SYSTEM_SUBTYPES


def _is_bot_post(raw: Mapping[str, Any]) -> bool:
    """Whether a bot or an integration posted the message rather than a person."""
    return bool(raw.get("bot_id")) or raw.get("subtype") == "bot_message"


def _bot_name(raw: Mapping[str, Any]) -> str:
    """Name a user-less bot post by its username, then its bot profile name, then its bot id."""
    profile: Mapping[str, Any] = raw.get("bot_profile") or {}
    return str(raw.get("username") or profile.get("name") or raw.get("bot_id"))


def _normalize_name(name: str) -> str:
    """Reduce a Slack name to a comparable form (``SRE Dev`` -> ``sredev``)."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _next_cursor(response: SlackResponse | AsyncSlackResponse | Mapping[str, Any]) -> str:
    """Return the cursor of the next page, or ``""`` when this was the last one."""
    return str((response.get("response_metadata") or {}).get("next_cursor") or "")


def _merge_chronologically(
    top_level: Sequence[Mapping[str, Any]], replies: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Interleave replies with the top-level messages by time, each ``ts`` once.

    A reply broadcast to the channel is in both lists and is kept once. A
    top-level message with an unreadable time stays right after the message
    before it, so it never jumps to the start or end of the transcript.
    """
    seen = {str(raw.get("ts")) for raw in top_level if raw.get("ts")}
    keyed: list[tuple[float, int, Mapping[str, Any]]] = []
    previous = float("-inf")
    for position, raw in enumerate(top_level):
        posted_at = _posted_at(raw.get("ts"))
        previous = posted_at.timestamp() if posted_at else previous
        keyed.append((previous, position, raw))
    for position, raw in enumerate(replies, start=len(top_level)):
        posted_at = _posted_at(raw.get("ts"))
        if posted_at is None or str(raw.get("ts")) in seen:
            continue
        seen.add(str(raw.get("ts")))
        keyed.append((posted_at.timestamp(), position, raw))
    return [raw for _, _, raw in sorted(keyed, key=lambda item: (item[0], item[1]))]


def _posted_at(raw_ts: Any) -> datetime | None:
    """Convert a Slack ``ts`` to an aware UTC datetime; ``None`` when missing or malformed."""
    try:
        return datetime.fromtimestamp(float(raw_ts), tz=UTC)
    except TypeError, ValueError:
        return None
