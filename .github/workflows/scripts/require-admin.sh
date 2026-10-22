#!/bin/bash
# Fails unless the actor holds the admin role on the repository. Manual runs and re-runs
# of the deploy workflow choose what production runs, so only admins may start them
# (decisions/deployment.md).
#
# Usage: require-admin.sh <owner/repository> <actor>   (GH_TOKEN must be set)

set -euo pipefail

repository="${1:?usage: require-admin.sh <owner/repository> <actor>}"
actor="${2:?usage: require-admin.sh <owner/repository> <actor>}"

if ! role=$(gh api "repos/${repository}/collaborators/${actor}/permission" --jq .role_name 2> /dev/null); then
  echo "Could not read the repository role of ${actor}; only repository admins may run or re-run a deploy manually." >&2
  exit 1
fi

if [[ "$role" != "admin" ]]; then
  echo "${actor} has the ${role} role; only repository admins may run or re-run a deploy manually." >&2
  exit 1
fi

echo "${actor} is a repository admin."
