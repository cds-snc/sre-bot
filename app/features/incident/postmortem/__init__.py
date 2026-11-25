"""Incident postmortem subdomain: the retro meeting and the report after the incident (decisions/incident-management.md).

Holds its settings, the pure availability rules (domain.py), the HolidayCalendar
interface (interfaces.py) with its Canada Holidays adapter and in-memory fake, and
the legacy public-holiday lookup (adapters/public_holidays.py) until the rebuild
(TASK-145.10) moves the rest of the behaviour in from modules/incident.
"""
