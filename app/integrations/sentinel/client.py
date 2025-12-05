import base64
from datetime import datetime, timezone
import hmac
import hashlib
import json
import requests

from core.logging import get_module_logger
from core.config import settings

logger = get_module_logger()
SENTINEL_CUSTOMER_ID = settings.sentinel.SENTINEL_CUSTOMER_ID
SENTINEL_LOG_TYPE = settings.sentinel.SENTINEL_LOG_TYPE
SENTINEL_SHARED_KEY = settings.sentinel.SENTINEL_SHARED_KEY


def send_event(payload):
    customer_id = SENTINEL_CUSTOMER_ID
    log_type = SENTINEL_LOG_TYPE
    shared_key = SENTINEL_SHARED_KEY

    if customer_id is None or shared_key is None:
        logger.error("send_event_error", error="customer_id or shared_key is missing")
        return False

    post_data(customer_id, shared_key, json.dumps(payload), log_type)
    return True


def build_signature(
    customer_id, shared_key, date, content_length, method, content_type, resource
):
    x_headers = "x-ms-date:" + date
    string_to_hash = (
        method
        + "\n"
        + str(content_length)
        + "\n"
        + content_type
        + "\n"
        + x_headers
        + "\n"
        + resource
    )
    bytes_to_hash = bytes(string_to_hash, encoding="utf-8")
    decoded_key = base64.b64decode(shared_key)
    encoded_hash = base64.b64encode(
        hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()
    ).decode()
    authorization = "SharedKey {}:{}".format(customer_id, encoded_hash)
    return authorization


def post_data(customer_id, shared_key, body, log_type):
    method = "POST"
    content_type = "application/json"
    resource = "/api/logs"
    rfc1123date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    content_length = len(body)
    signature = build_signature(
        customer_id,
        shared_key,
        rfc1123date,
        content_length,
        method,
        content_type,
        resource,
    )
    uri = (
        "https://"
        + customer_id
        + ".ods.opinsights.azure.com"
        + resource
        + "?api-version=2016-04-01"
    )

    headers = {
        "content-type": content_type,
        "Authorization": signature,
        "Log-Type": log_type,
        "x-ms-date": rfc1123date,
    }

    response = requests.post(uri, data=body, headers=headers, timeout=60)
    if response.status_code >= 200 and response.status_code <= 299:
        logger.info(
            "sentinel_event_sent",
            customer_id=customer_id,
            log_type=log_type,
            content_length=content_length,
        )
        return True
    else:
        print(response.text)
        logger.error(
            "sentinel_event_error",
            customer_id=customer_id,
            log_type=log_type,
            content_length=content_length,
        )
        return False


def log_to_sentinel(event, message):
    is_event_sent = False
    payload = {"event": event, "message": message}

    try:
        is_event_sent = send_event(payload)
    except Exception as e:
        logger.exception("log_to_sentinel_error", error=str(e))

    if is_event_sent:
        logger.info("sentinel_event_sent", payload=payload)
    else:
        logger.error("sentinel_event_error", payload=payload)
