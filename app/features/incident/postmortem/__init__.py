"""Incident postmortem subdomain: the retro meeting and the report after the incident (decisions/incident-management.md).

Holds its settings, the meeting search rules (domain.py), its interfaces, the schedule
service, the schedule view builders and catalogue, and the adapters: Canada Holidays,
the attendee directory, the Sentinel event sink and their fakes. Dark until the
cutover (TASK-145.10.4) adds ``plugin.py`` with an entry point and the Slack handlers;
the legacy availability helpers in domain.py and adapters/public_holidays.py serve
modules/incident until then.
"""
