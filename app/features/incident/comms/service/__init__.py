"""Status-update use cases, one module per use case.

``draft`` starts, saves and AI-fills the pending draft; ``form`` assembles what
the responder's form shows; ``approval`` reads a draft for review and approves
it; ``publication`` marks an approved update published and reads its
copy-ready text; ``history`` reads the pending draft and the approved updates;
``prompt`` holds the drafting prompt and its answer parser.
"""
