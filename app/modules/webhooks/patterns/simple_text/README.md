# Simple Text Pattern Matching System

This system provides a flexible pattern matching framework for processing simple text webhooks. It supports multiple match types, dynamic handler imports, and priority-based pattern resolution.

## RuntimePattern Fields

```python
@dataclass 
class RuntimePattern:
    name: str                                          # Unique identifier
    pattern: str                                       # Pattern string (content depends on match_type)
    handler: str                                       # Import path to handler function
    match_type: Literal["regex", "contains", "callable"] = "contains"
    priority: int = 0                                  # Higher = checked first  
    enabled: bool = True                               # Enable/disable pattern
```

## Match Types

### 1. "contains" (Substring Matching)
- **Pattern**: Simple substring to search for
- **Example**: `"ERROR:"` matches any text containing "ERROR:"

### 2. "regex" (Regular Expression)  
- **Pattern**: Regular expression pattern
- **Example**: `r"\[\d{4}-\d{2}-\d{2}.*\]\s+(ERROR|WARN)"` matches structured log entries

### 3. "callable" (Custom Function)
- **Pattern**: Import path to a callable function `(str) -> bool`
- **Example**: `"modules.webhooks.patterns.simple_text.upptime.is_upptime_pattern"`

## Handler Functions

Handler functions must have the signature:
```python
def handler_function(text: str) -> WebhookPayload:
    # Process text and return WebhookPayload
    pass
```

## Usage Examples

### Direct Registration
```python
from modules.webhooks.simple_text import RuntimePattern, register_pattern

# Simple substring pattern
error_pattern = RuntimePattern(
    name="error_alerts",
    pattern="ERROR:",
    handler="modules.webhooks.simple_text.handle_generic_text",
    match_type="contains",
    priority=5
)
register_pattern(error_pattern)

# Regex pattern
log_pattern = RuntimePattern(
    name="structured_logs", 
    pattern=r"\[\d{4}-\d{2}-\d{2}.*\]\s+(ERROR|WARN)",
    handler="modules.my_handlers.handle_structured_log",
    match_type="regex",
    priority=8
)
register_pattern(log_pattern)

# Callable pattern
custom_pattern = RuntimePattern(
    name="custom_logic",
    pattern="modules.my_patterns.my_detection_function", 
    handler="modules.my_handlers.my_custom_handler",
    match_type="callable",
    priority=10
)
register_pattern(custom_pattern)
```

### Configuration-based Registration
```python
patterns_config = [
    {
        "name": "error_alerts",
        "pattern": "ERROR:",
        "handler": "modules.webhooks.simple_text.handle_generic_text",
        "match_type": "contains",
        "priority": 5,
        "enabled": True
    },
    {
        "name": "critical_alerts",
        "pattern": r"CRITICAL.*\s+(.+)",
        "handler": "modules.handlers.critical_alert_handler", 
        "match_type": "regex",
        "priority": 10,
        "enabled": True
    }
]

for config in patterns_config:
    pattern = RuntimePattern.from_dict(config)
    register_pattern(pattern)
```

## Processing Flow

1. **Pattern Matching**: Enabled patterns are checked in priority order (highest first)
2. **Handler Import**: Matching pattern's handler is dynamically imported
3. **Processing**: Handler function processes the text and returns WebhookPayload
4. **Fallback**: If no patterns match or handler fails, generic text handler is used

## Best Practices

1. **Priority Assignment**: Use higher priorities for more specific patterns
2. **Error Handling**: Handlers should be robust; system falls back to generic handler on errors  
3. **Performance**: Callable patterns are most flexible but potentially slower than regex/contains
4. **Testing**: Disable patterns temporarily using `enabled: false`
5. **Organization**: Group related patterns in separate modules (e.g., `upptime.py`, `logs.py`)

## Example Pattern Module Structure

```
modules/webhooks/patterns/simple_text/
├── __init__.py
├── upptime.py           # Upptime monitoring patterns
├── logs.py              # Log processing patterns  
├── alerts.py            # Generic alert patterns
└── examples.py          # Example patterns and utilities
```