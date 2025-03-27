from core.logging import get_module_logger
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

logger = get_module_logger()


@handle_aws_api_errors
def get_queue_url(queue_name):
    """Get the URL of an SQS queue.

    Args:
        queue_name (str): The name of the SQS queue.

    Returns:
        str: The URL of the SQS queue.
    """
    logger.info(
        "getting_queue_url",
        service="sqs",
        queue_name=queue_name,
    )
    if not queue_name:
        raise ValueError("Queue_name must not be empty")
    return execute_aws_api_call("sqs", "get_queue_url", QueueName=queue_name)[
        "QueueUrl"
    ]


@handle_aws_api_errors
def send_message(queue_url, message_body, message_group_id):
    """Send a message to an SQS queue.

    Args:
        queue_url (str): The URL of the SQS queue.
        message_body (str): The message body.
        message_group_id (str): The message group ID. By default, it is the incident name.

    Returns:
        dict: The response from the SQS service.
    """
    logger.info(
        "sending_message",
        service="sqs",
        queue_url=queue_url,
        message_body=message_body,
        message_group_id=message_group_id,
    )
    return execute_aws_api_call(
        "sqs",
        "send_message",
        QueueUrl=queue_url,
        MessageBody=message_body,
        MessageGroupId=message_group_id,
    )


@handle_aws_api_errors
def receive_message(queue_url, max_number_of_messages=10, wait_time_seconds=10):
    """Receive messages from an SQS queue.

    Args:
        queue_url (str): The URL of the SQS queue.
        max_number_of_messages (int): The maximum number of messages to receive.
        wait_time_seconds (int): The duration (in seconds) for which the call waits for a message to arrive in the queue before returning.

    Returns:
        list: A list of messages.
    """
    logger.info(
        "receiving_message",
        service="sqs",
        queue_url=queue_url,
        max_number_of_messages=max_number_of_messages,
        wait_time_seconds=wait_time_seconds,
    )
    return execute_aws_api_call(
        "sqs",
        "receive_message",
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_number_of_messages,
        WaitTimeSeconds=wait_time_seconds,
    )


@handle_aws_api_errors
def delete_message(queue_url, receipt_handle):
    """Delete a message from an SQS queue.

    Args:
        queue_url (str): The URL of the SQS queue.
        receipt_handle (str): The receipt handle of the message.

    Returns:
        dict: The response from the SQS service.
    """
    logger.info(
        "deleting_message",
        service="sqs",
        queue_url=queue_url,
        receipt_handle=receipt_handle,
    )

    return execute_aws_api_call(
        "sqs", "delete_message", QueueUrl=queue_url, ReceiptHandle=receipt_handle
    )
