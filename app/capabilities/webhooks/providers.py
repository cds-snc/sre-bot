"""The webhooks composition root: it builds the platform adapters and the services behind the ports.

Only entrypoints and jobs import this module, so no core module reaches a platform SDK,
even indirectly (decisions/webhooks.md Checks; import-linter contract (p)). The HTTP path
shares one SNS port and one set of posters per process; the sweeper builds its own inside
each run, on that run's event loop (decisions/webhooks.md 3, step 6).
"""

from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

from capabilities.webhooks.adapters.aws_sns import AwsSnsHttp, build_aws_sns_http
from capabilities.webhooks.adapters.slack import build_slack_poster
from capabilities.webhooks.interfaces import ChannelPoster, SubscriptionConfirmer
from capabilities.webhooks.service import WebhookExtensions, WebhookProcessor
from capabilities.webhooks.settings import get_webhooks_settings
from capabilities.webhooks.store import RecordInboxStore, RecordWebhookStore, inbox_table, instances_table
from contracts.content import ContentCatalogue
from contracts.i18n.translator import Translator
from contracts.languages import LanguagePolicy
from contracts.records import RecordStore
from contracts.services import ServiceResolver
from contracts.workplace import WorkplaceSystem


def build_channel_posters() -> Mapping[WorkplaceSystem, ChannelPoster]:
    """One poster per configured platform, keyed by the system a destination names."""
    posters: dict[WorkplaceSystem, ChannelPoster] = {}
    if (slack := build_slack_poster(get_webhooks_settings())) is not None:
        posters[WorkplaceSystem.SLACK] = slack
    return MappingProxyType(posters)


@lru_cache(maxsize=1)
def get_channel_posters() -> Mapping[WorkplaceSystem, ChannelPoster]:
    """The HTTP path's posters, built once per process."""
    return build_channel_posters()


def build_sns_http() -> AwsSnsHttp:
    """A new SNS port; its owner closes it with ``aclose``."""
    return build_aws_sns_http(get_webhooks_settings())


@lru_cache(maxsize=1)
def get_sns_http() -> AwsSnsHttp:
    """The HTTP path's SNS port, so its certificate cache lives as long as the process."""
    return build_sns_http()


def build_webhook_store(services: ServiceResolver) -> RecordWebhookStore:
    """The instance store on the resolved records contract."""
    return RecordWebhookStore(services.get(RecordStore), instances_table(get_webhooks_settings().instances_table_name))


def build_processor(
    services: ServiceResolver,
    *,
    confirmer: SubscriptionConfirmer,
    posters: Mapping[WorkplaceSystem, ChannelPoster] | None = None,
) -> WebhookProcessor:
    """The processor on the resolved contracts; ``posters`` defaults to the HTTP path's."""
    settings = get_webhooks_settings()
    records = services.get(RecordStore)
    return WebhookProcessor(
        inbox=RecordInboxStore(records, inbox_table(settings.inbox_table_name)),
        instances=RecordWebhookStore(records, instances_table(settings.instances_table_name)),
        catalogue=services.get(ContentCatalogue),
        languages=services.get(LanguagePolicy),
        translator=services.get(Translator),
        extensions=services.get(WebhookExtensions),
        posters=get_channel_posters() if posters is None else posters,
        confirmer=confirmer,
        settings=settings,
    )
