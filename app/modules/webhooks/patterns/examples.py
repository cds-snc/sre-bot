"""
Example patterns showing the different match types and configuration options.
"""

from modules.webhooks.simple_text import SimpleTextPattern, register_pattern

# Example patterns using different match types
EXAMPLE_PATTERNS = [
    # Simple substring matching
    {
        "name": "error_alerts",
        "pattern": "ERROR:",
        "handler": "modules.webhooks.simple_text.handle_generic_text",
        "match_type": "contains",
        "priority": 5,
        "enabled": True,
    },
    # Regex pattern for structured log parsing
    {
        "name": "structured_logs",
        "pattern": r"\[\d{4}-\d{2}-\d{2}.*\]\s+(ERROR|WARN|CRITICAL)",
        "handler": "modules.webhooks.simple_text.handle_generic_text",
        "match_type": "regex",
        "priority": 8,
        "enabled": True,
    },
    # Custom callable for complex logic
    {
        "name": "upptime_monitoring",
        "pattern": "modules.webhooks.patterns.simple_text.upptime.is_upptime_pattern",
        "handler": "modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload",
        "match_type": "callable",
        "priority": 10,
        "enabled": True,
    },
    # Disabled pattern (for testing)
    {
        "name": "disabled_pattern",
        "pattern": "test",
        "handler": "modules.webhooks.simple_text.handle_generic_text",
        "match_type": "contains",
        "priority": 1,
        "enabled": False,
    },
]


def register_example_patterns():
    """Register all example patterns."""
    for pattern_config in EXAMPLE_PATTERNS:
        pattern = SimpleTextPattern.from_dict(pattern_config)
        register_pattern(pattern)


def register_patterns_from_config(config_list):
    """Register patterns from a configuration list."""
    for config in config_list:
        try:
            pattern = SimpleTextPattern.from_dict(config)
            register_pattern(pattern)
            print(f"Registered pattern: {pattern.name}")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Failed to register pattern {config.get('name', 'unknown')}: {e}")


if __name__ == "__main__":
    # Example usage
    register_example_patterns()
    print("Example patterns registered successfully!")
