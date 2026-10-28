# Repo-level entry point. Repo-wide targets live here; anything else is
# forwarded to app/Makefile so dev commands work from the repo root
# (e.g. `make test`, `make lint`, `make dev`).

.DEFAULT_GOAL := help

.PHONY: help sync-issues sync-issues-apply backlog-board backlog-install bootstrap env-checks env-checks-apply

help:
	@echo "Repo-level targets:"
	@echo "  sync-issues        dry-run sync of backlog tasks -> GitHub issues"
	@echo "  sync-issues-apply  apply the sync (creates/updates/closes issues)"
	@echo "  backlog-board      Backlog.md web UI at http://localhost:6421"
	@echo "  backlog-install    install the Backlog.md CLI (npm i -g backlog.md)"
	@echo "  bootstrap          one-shot setup for a fresh checkout/codespace (dev deps + Backlog.md CLI)"
	@echo "  env-checks         audit env names in app/.env*, Codespaces and SSM; plans fixes, changes nothing"
	@echo "  env-checks-apply   apply a saved plan after a yes prompt: make env-checks-apply PLAN=tmp/env-checks/<UTC>.plan.sh"
	@echo ""
	@echo "Any other target is forwarded to app/Makefile (test, lint, fmt, dev, ...)."

env-checks:
	zsh bin/env-checks.zsh

env-checks-apply:
	@test -n "$(PLAN)" || { echo "usage: make env-checks-apply PLAN=tmp/env-checks/<UTC>.plan.sh"; exit 2; }
	zsh bin/env-checks.zsh apply $(PLAN)

sync-issues:
	uv run --script bin/backlog_issue_sync.py

sync-issues-apply:
	uv run --script bin/backlog_issue_sync.py --apply

backlog-board:
	@command -v backlog >/dev/null 2>&1 || { echo "backlog CLI not found. Run 'make backlog-install' first."; exit 1; }
	backlog browser --no-open --port 6421

backlog-install:
	npm i -g backlog.md

bootstrap: backlog-install
	@$(MAKE) -C app install-dev

.DEFAULT:
	@$(MAKE) -C app $@
