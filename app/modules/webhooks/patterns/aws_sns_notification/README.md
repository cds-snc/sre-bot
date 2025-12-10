# AWS SNS Pattern Handler System

This document describes the new AWS SNS pattern handler system that was implemented to replace the monolithic parsing approach.

## Overview

The AWS SNS webhook processing has been refactored from a single `parse()` function with multiple `format_*()` functions into a modular pattern-based system similar to the simple text webhook handling.

## Key Benefits

1. **Modularity**: Each notification type is handled by its own self-contained module
2. **Extensibility**: New notification types can be added easily by creating new pattern files
3. **Maintainability**: Each handler is isolated and easier to test and maintain
4. **Consistency**: Uses the same pattern approach as the simple text webhook system
5. **Clean Architecture**: The main AWS module focuses on core validation and coordination

## Architecture

### Core Components

- **`aws_sns.py`**: Core SNS payload validation and coordination (significantly simplified)
- **`aws_sns_notification.py`**: Pattern coordinator and registry system
- **`patterns/aws_sns_notification/`**: Directory containing individual pattern handler modules

### Pattern Handler Structure

Each pattern handler module contains:

1. **Handler Function**: Processes the specific notification type and returns Slack blocks
2. **Pattern Matcher**: Function to determine if a payload matches this pattern
3. **Pattern Registration**: AwsNotificationPattern configuration object

## Existing Pattern Handlers

The following pattern handlers have been implemented:

| Handler                | Priority | File                        | Description                                   |
| ---------------------- | -------- | --------------------------- | --------------------------------------------- |
| API Key Detected       | 60       | `api_key_detected.py`       | Handles compromised API key notifications     |
| Step Functions         | 55       | `step_functions.py`         | Handles Step Functions execution notifications |
| CloudWatch Alarm       | 50       | `cloudwatch_alarm.py`       | Handles CloudWatch alarm notifications        |
| Abuse Notification     | 45       | `abuse_notification.py`     | Handles AWS abuse reports                     |
| Budget Notification    | 40       | `budget_notification.py`    | Handles budget threshold alerts               |
| Auto Mitigation        | 35       | `auto_mitigation.py`        | Handles security group auto-mitigation        |
| IAM User               | 30       | `iam_user.py`               | Handles new IAM user creation alerts          |
| Budget Auto Adjustment | 25       | `budget_auto_adjustment.py` | Handles budget auto-adjustments (logged only) |

## Pattern Matching Types

The `AwsNotificationPattern` class supports multiple matching strategies:

### Match Types

- **`regex`**: Regular expression pattern matching
- **`contains`**: Simple substring matching
- **`callable`**: Custom function for complex matching logic
- **`message_structure`**: JSON key existence checking

### Match Targets

- **`message`**: Match against the raw message content
- **`subject`**: Match against the SNS subject field
- **`topic_arn`**: Match against the topic ARN
- **`parsed_message`**: Match against the parsed JSON message

## Adding New Pattern Handlers

To add a new AWS SNS notification pattern:

1. **Create Handler Module**: Create a new file in `modules/webhooks/patterns/aws_sns_notification/`
2. **Implement Handler Function**: Create the main processing function
3. **Implement Matcher Function**: Create the pattern matching function (if using callable matching)
4. **Register Pattern**: Create an `AwsNotificationPattern` instance with `_HANDLER` suffix

### Example Handler

```python
# modules/webhooks/patterns/aws_sns_notification/my_new_pattern.py
from typing import Dict, List, Union
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

def handle_my_notification(payload: AwsSnsPayload, client: WebClient) -> List[Dict]:
    \"\"\"Handle my specific notification type.\"\"\"
    # Process the payload and return Slack blocks
    return [
        {"type": "header", "text": {"type": "plain_text", "text": "My Notification"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": payload.Message or ""}},
    ]

def is_my_notification(payload: AwsSnsPayload, parsed_message: Union[str, dict]) -> bool:
    \"\"\"Check if this matches my notification pattern.\"\"\"
    return "MY_PATTERN" in (payload.Message or "")

MY_NOTIFICATION_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="my_notification",
    match_type="callable",
    match_target="message",
    pattern="modules.webhooks.patterns.aws_sns_notification.my_new_pattern.is_my_notification",
    handler="modules.webhooks.patterns.aws_sns_notification.my_new_pattern.handle_my_notification",
    priority=20,
    enabled=True,
)
```

## Testing

The pattern system can be tested by:

1. **Unit Testing**: Test individual pattern handlers in isolation
2. **Integration Testing**: Test the full pattern matching and coordination
3. **Manual Testing**: Use the pattern coordinator directly with sample payloads

### Example Test

```python
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import process_aws_notification_payload
from unittest.mock import Mock

# Create test payload
payload = AwsSnsPayload(Type="Notification", Message="Test message")
client = Mock()

# Test processing
blocks = process_aws_notification_payload(payload, client)
```

## Migration Notes

### Breaking Changes

- Removed `parse()` function from `aws_sns.py`
- Removed all `format_*()` functions from `aws_sns.py`
- Removed `NOTIFY_OPS_CHANNEL_ID` from `aws_sns.py`
- Removed `send_message_to_notify_chanel()` function from `aws_sns.py`

### Backward Compatibility

The public API for `process_aws_sns_payload()` remains unchanged. Only internal implementation details have changed.

### Test Updates Required

Existing tests will need to be updated to:

1. Import functions from the new pattern handler modules instead of `aws_sns.py`
2. Update mocking paths to the new module locations
3. Test the new pattern coordinator functionality

## Files Changed

### New Files

- `modules/webhooks/aws_sns_notification.py`
- `modules/webhooks/patterns/aws_sns_notification/__init__.py`
- `modules/webhooks/patterns/aws_sns_notification/cloudwatch_alarm.py`
- `modules/webhooks/patterns/aws_sns_notification/budget_notification.py`
- `modules/webhooks/patterns/aws_sns_notification/abuse_notification.py`
- `modules/webhooks/patterns/aws_sns_notification/auto_mitigation.py`
- `modules/webhooks/patterns/aws_sns_notification/iam_user.py`
- `modules/webhooks/patterns/aws_sns_notification/api_key_detected.py`
- `modules/webhooks/patterns/aws_sns_notification/budget_auto_adjustment.py`
- `modules/webhooks/patterns/aws_sns_notification/step_functions.py`

### Modified Files

- `modules/webhooks/aws_sns.py` (significantly simplified)

## Future Enhancements

1. **Dynamic Registration**: Add runtime pattern registration API
2. **Configuration**: Allow pattern enable/disable via configuration
3. **Metrics**: Add pattern matching metrics and monitoring
4. **Validation**: Add pattern configuration validation
5. **Testing Framework**: Create dedicated testing utilities for pattern handlers
