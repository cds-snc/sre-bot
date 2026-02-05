# Response Format Abstraction

## Platform-Agnostic Models

**Decision**: Business logic returns platform-agnostic models; each platform has a formatter to convert models to platform-specific formats.

Core models enable single business logic output to format for Slack, Teams, Discord, or API:

```python
# infrastructure/platforms/models.py
from typing import Literal
from pydantic import BaseModel, Field

class Card(BaseModel):
    """Platform-agnostic card (converts to Block Kit, Adaptive Card, Embed, or JSON)."""
    title: str
    description: str | None = None
    fields: list[dict] = Field(default_factory=list)  # {"label": ..., "value": ...}
    buttons: list[dict] = Field(default_factory=list)  # {"text": ..., "action_id": ..., "style": ...}
    thumbnail_url: str | None = None
    color: Literal["success", "warning", "error", "info"] = "info"
    footer: str | None = None

class ErrorMessage(BaseModel):
    """Platform-agnostic error."""
    message: str
    error_code: str | None = None
    details: str | None = None

class SuccessMessage(BaseModel):
    """Platform-agnostic success."""
    message: str
    data: dict | None = None
```

**Business logic returns models**:

```python
def get_group_details(group_id: str, request_id: str) -> Card:
    log = logger.bind(group_id=group_id, request_id=request_id)
    group = fetch_group(group_id)
    return Card(
        title=f"Group: {group.name}",
        fields=[
            {"label": "Members", "value": str(group.member_count)},
        ],
        buttons=[{"text": "View Members", "action_id": f"view_members_{group_id}", "style": "primary"}],
    )
```

Rules:
- ✅ Business logic returns Card, ErrorMessage, or SuccessMessage
- ✅ All fields platform-agnostic (no Slack/Teams/Discord specifics)
- ❌ Never include platform-specific fields (blocks, attachments, embeds)
- ❌ Never mix formatting logic with business logic

---

## Platform Formatters

**Decision**: Each platform has a dedicated formatter that converts platform-agnostic models to platform-specific JSON.

**Formatter pattern** (all platforms implement same interface):

```python
# infrastructure/platforms/formatters/slack.py
import structlog
from infrastructure.platforms.models import Card, ErrorMessage, SuccessMessage

logger = structlog.get_logger()

class SlackFormatter:
    """Converts Card/ErrorMessage/SuccessMessage to Slack Block Kit."""
    
    def format_card(self, card: Card) -> dict:
        """Convert Card to Block Kit JSON."""
        log = logger.bind(formatter="slack", model="card")
        
        blocks = [{"type": "header", "text": {"type": "plain_text", "text": card.title}}]
        
        if card.description:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": card.description}})
        
        if card.fields:
            blocks.append({"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*{f['label']}*\n{f['value']}"}
                for f in card.fields
            ]})
        
        if card.buttons:
            blocks.append({"type": "actions", "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": b["text"]},
                    "action_id": b["action_id"],
                    "style": b.get("style", "default"),
                }
                for b in card.buttons
            ]})
        
        log.debug("card_formatted", block_count=len(blocks))
        return {"blocks": blocks}
    
    def format_error(self, error: ErrorMessage) -> dict:
        """Convert ErrorMessage to Block Kit JSON."""
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f":x: *Error*\n{error.message}"}}]
        if error.details:
            blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": error.details}]})
        return {"blocks": blocks}
    
    def format_success(self, success: SuccessMessage) -> dict:
        """Convert SuccessMessage to Block Kit JSON."""
        return {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": f":white_check_mark: {success.message}"}}]}
```

**Factory function** (select formatter by platform):

```python
# infrastructure/platforms/formatters/__init__.py
from .slack import SlackFormatter
from .teams import TeamsFormatter
from .discord import DiscordFormatter

def get_formatter(platform: str) -> SlackFormatter | TeamsFormatter | DiscordFormatter:
    """Get platform-specific formatter.
    
    Args:
        platform: "slack", "teams", or "discord"
    
    Returns:
        Formatter instance
    
    Raises:
        ValueError: If platform unsupported
    """
    formatters = {
        "slack": SlackFormatter,
        "teams": TeamsFormatter,
        "discord": DiscordFormatter,
    }
    formatter_class = formatters.get(platform)
    if not formatter_class:
        raise ValueError(f"Unsupported platform: {platform}")
    return formatter_class()
```

**Platform adapter usage**:

```python
# packages/groups/platforms/slack.py
from infrastructure.platforms.formatters import get_formatter
from modules.groups.service import get_group_details

async def handle_group_details_command(payload: dict, request_id: str) -> dict:
    """Handle /group-details command."""
    log = logger.bind(command="group_details", user_id=payload["user_id"], request_id=request_id)
    
    group_id = payload["text"].strip()
    
    # ✅ Get platform-agnostic Card from business logic
    card = get_group_details(group_id, request_id)
    
    # ✅ Format for Slack
    formatter = get_formatter("slack")
    response = formatter.format_card(card)
    
    log.info("response_formatted", platform="slack")
    return response
```

Rules:
- ✅ Each platform has dedicated formatter class
- ✅ Formatters are stateless (no instance state)
- ✅ Log formatting operations with formatter type and model
- ✅ Use factory function to select formatter
- ✅ Platform adapters call business logic → format result
- ❌ Never import platform SDK in business logic (only formatters)
- ❌ Never mix formatting logic with business logic
- ❌ Never pass formatter to business logic

---

## Response vs Notification Routing

**Critical Distinction**: 
- **HTTP Response**: Sent to API caller (always happens immediately)
- **Platform Notifications**: Async side effects sent to users based on configuration (separate from HTTP response)

**Flow**:
1. External API calls `POST /api/v1/groups/add` (JWT authenticated)
2. Endpoint processes request → adds user to group
3. Endpoint returns `200 OK` JSON response to API caller ✅ (always)
4. Business logic checks config and sends platform notifications asynchronously:
   - If Slack enabled AND user has Slack identity → send Slack DM via formatter
   - If Teams enabled AND user has Teams identity → send Teams notification
   - If email configured → send email
5. All notifications use Card model with formatters; platform SDK only in notification handler

**Key**: HTTP response always goes to requester. Notifications are event-driven parallel actions.

Rules:
- ✅ FastAPI endpoint always returns HTTP response to requester
- ✅ Platform notifications are async side effects (separate from response)
- ✅ Notifications configured via application settings (which platforms enabled)
- ✅ Each notification uses same Card + formatter pattern
- ❌ Never block HTTP response on notification delivery
- ❌ Never treat platform notifications as alternative responses
- ❌ Never skip HTTP response to requester