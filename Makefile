# Repo-level entry point. Repo-wide targets live here; anything else is
# forwarded to app/Makefile so dev commands work from the repo root
# (e.g. `make test`, `make lint`, `make dev`).

.DEFAULT_GOAL := help

.PHONY: help sync-issues sync-issues-apply backlog-board

help:
	@echo "Repo-level targets:"
	@echo "  sync-issues        dry-run sync of backlog tasks -> GitHub issues"
	@echo "  sync-issues-apply  apply the sync (creates/updates/closes issues)"
	@echo "  backlog-board      Backlog.md web UI at http://localhost:6421"
	@echo ""
	@echo "Any other target is forwarded to app/Makefile (test, lint, fmt, dev, ...)."

sync-issues:
	uv run --script bin/backlog_issue_sync.py

sync-issues-apply:
	uv run --script bin/backlog_issue_sync.py --apply

backlog-board:
	backlog browser --no-open --port 6421

.DEFAULT:
	@$(MAKE) -C app $@
