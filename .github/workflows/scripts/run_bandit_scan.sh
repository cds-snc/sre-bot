#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

if [ ! -d "${REPO_ROOT}/app" ]; then
  echo "Expected app directory not found under repo root: ${REPO_ROOT}" >&2
  exit 1
fi

# Make sure we are using the latest version
docker pull cytopia/bandit:latest

# Paths already migrated to ruff (see app/Makefile RUFF_SCOPE): ruff's "S" rule
# family (bandit-via-ruff, see decisions/toolchain.md) already covers these, and
# cytopia/bandit's bundled Python predates PEP 695 (3.12)/PEP 758 (3.14) syntax
# used in some migrated files, so it can't parse them. Exclude them here to
# avoid false AST-parse failures without losing security coverage. Keep this
# list in sync with RUFF_SCOPE as later TASK-15.x slices land; the whole
# workflow is deleted once the migration completes (TASK-15.12).
RUFF_MIGRATED_PATHS="/data/app/api,/data/app/tests/api,/data/app/infrastructure,/data/app/tests/unit/infrastructure,/data/app/integrations/aws,/data/app/integrations/utils,/data/app/integrations/maxmind,/data/app/integrations/trello,/data/app/integrations/notify,/data/app/integrations/sentinel,/data/app/integrations/opsgenie,/data/app/tests/integrations/aws,/data/app/tests/integrations/utils,/data/app/tests/integrations/maxmind,/data/app/tests/integrations/trello,/data/app/tests/integrations/notify,/data/app/tests/integrations/sentinel,/data/app/tests/integrations/opsgenie,/data/app/tests/unit/integrations"

# Scan source code and only report on high severity issues
docker run --rm -v "${REPO_ROOT}":/data cytopia/bandit \
	-r /data/app \
	-ll \
	-x "/data/app/venv,/data/app/.venv,/data/app/__pycache__,${RUFF_MIGRATED_PATHS}"