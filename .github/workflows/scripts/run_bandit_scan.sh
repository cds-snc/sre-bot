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

# Scan source code and only report on high severity issues
docker run --rm -v "${REPO_ROOT}":/data cytopia/bandit \
	-r /data/app \
	-ll \
	-x /data/app/venv,/data/app/.venv,/data/app/__pycache__