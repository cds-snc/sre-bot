"""Amazon SNS HTTP vendor package: the httpx client factory and its error classifier.

SNS reaches the bot over HTTPS; the bot calls SNS back only to fetch a signing certificate
and to confirm a subscription. Signature verification is the webhooks capability's.
"""

from .client import build_sns_http_client, classify_sns_http_error

__all__ = ["build_sns_http_client", "classify_sns_http_error"]
