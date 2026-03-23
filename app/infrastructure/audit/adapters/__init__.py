"""Output adapters for audit events.

Different SIEM systems have different requirements:
- Sentinel: flat field structure for queryability
- CloudTrail: hierarchical JSON with specific field names
- DataDog: tagged events with custom metrics

Each adapter handles format-specific serialization, allowing the core audit
service to remain format-agnostic.
"""
