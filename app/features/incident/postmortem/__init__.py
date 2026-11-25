"""Incident postmortem subdomain: the retro meeting and the report after the incident (decisions/incident-management.md).

Holds its settings, the meeting search rules (domain.py), its interfaces, the schedule
service, the schedule view builders and catalogue, and the adapters: Canada Holidays,
the attendee directory, the Sentinel event sink and their fakes. No entry point names
the package and no handler opens its views, so nothing in production reaches the
schedule flow; the legacy availability helpers in domain.py and
adapters/public_holidays.py serve modules/incident.
"""
