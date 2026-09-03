"""Pure incident retro scheduling logic relocated out of the frozen vendor package.

Holds host-surface-free domain helpers moved from
``integrations/google_workspace/google_calendar.py`` per decisions/migration.md
rule 5: it registers no plugin hooks and declares no entry point, so
``app/modules/incident`` remains the registered incident capability until the
full migration.
"""
