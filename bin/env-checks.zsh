#!/usr/bin/env zsh
# Environment-name audit: one action per name (none, delete, rename, check) for every name set in the env
# files, the Codespaces secrets, the GitHub Actions and Dependabot secrets and variables, and the production
# SSM parameters. Read-only. Never prints a value: names and a state only (set, empty, commented,
# placeholder, present). A secret parameter is compared with the terraform placeholder in-process.
# Developer helper, not part of the app. The production SSM part serves the configuration migration and is
# deleted with the blobs in TASK-111.15.2; the env-file, Codespaces and Actions part stays.
#
# Usage (from any directory; gh auth and AWS read credentials make their sections run, else they are skipped):
#   zsh bin/env-checks.zsh                 # full audit; rows needing no action are hidden
#   zsh bin/env-checks.zsh --all           # also list the rows needing no action
#   zsh bin/env-checks.zsh ACCESS_ SLACK   # only names starting with any argument
# GitHub listings need your own login where the Codespace token is refused (Actions secrets, repo admin):
#   env -u GITHUB_TOKEN -u GH_TOKEN gh auth login --web; the script then retries with it automatically.
# User Codespaces secrets need the codespace scope once: gh auth refresh -h github.com -s codespace
# Output: tmp/env-checks/<UTC timestamp>.txt (gitignored, never commit it), also echoed.
# Classifier: app/bin/audit_env_names.py (each present name); app/bin/audit_env_coverage.py (where each name
# supplied through the environment is missing: terraform/ssm.tf, SSM, the blob source line, Codespaces,
# app/.env.example).

setopt no_unset pipe_fail
unsetopt xtrace verbose

ROOT=$(git -C ${0:A:h} rev-parse --show-toplevel)
APP=$ROOT/app
BASELINE=74508713^   # parent of TASK-111.1: the tree before the configuration migration
REPO_SLUG=cds-snc/sre-bot
ORG=cds-snc
REGION=ca-central-1
BLOBS=(sre-bot-config sre-bot-config-infrastructure)
PLACEHOLDER=set-outside-terraform   # terraform/ssm.tf value_wo
OUT_DIR=$ROOT/tmp/env-checks
mkdir -p $OUT_DIR
OUT=$OUT_DIR/$(date -u +%Y%m%dT%H%M%SZ).txt
NAMES=$(mktemp)
BASE_DIR=$(mktemp -d)
trap 'rm -rf $NAMES $BASE_DIR' EXIT
show=()
filters=()
for a in "$@"; do [[ $a == --all ]] && show=(--all) || filters+=($a); done

keep() { (( ${#filters} == 0 )) && return 0; local f; for f in $filters; do [[ $1 == $f* ]] && return 0; done; return 1; }
emit() { keep $2 && print -r -- "$1	$2	$3" >> $NAMES; }
note() { print -r -- "$*" >&2; }
# gh with the session's token, then with the user's own login (the Codespace token cannot list everything).
ghx() { gh "$@" 2>/dev/null || env -u GITHUB_TOKEN -u GH_TOKEN gh "$@" 2>/dev/null; }
# list_names SOURCE STATE COMMAND...: emit one row per name the command prints; false when it fails.
list_names() {
  local source=$1 state=$2 out n; shift 2
  out=$(ghx "$@") || return 1
  for n in ${(f)out}; do [[ -n $n ]] && emit $source $n $state; done
  return 0
}

# Env-style lines: NAME=..., export NAME=..., and commented '# NAME=...' (a commented name still misleads).
scan_lines() {
  local source=$1 line name value state
  while IFS= read -r line; do
    [[ $line =~ '^[[:space:]]*(#[[:space:]]*)?(export[[:space:]]+)?([A-Z][A-Z0-9_]*)[[:space:]]*=(.*)$' ]] || continue
    name=$match[3]; value=$match[4]
    if [[ -n $match[1] ]]; then state=commented
    elif [[ -z ${value//[\'\"[:space:]]/} ]]; then state=empty
    else state=set; fi
    emit $source $name $state
  done
}

{
  print "run_at=$(date -u +%Y-%m-%dT%H:%M:%SZ) filters=${filters:-none}"

  for f in $APP/.env.example $APP/.env; do
    [[ -r $f ]] && scan_lines "file ${f#$ROOT/}" < $f || note "skipped ${f#$ROOT/}: not readable"
  done

  if gh auth status >/dev/null 2>&1 || env -u GITHUB_TOKEN -u GH_TOKEN gh auth status >/dev/null 2>&1; then
    list_names "codespaces repo $REPO_SLUG" present api repos/$REPO_SLUG/codespaces/secrets --paginate --jq '.secrets[].name' \
      || note "skipped repo Codespaces secrets (needs repo admin)"
    list_names "codespaces org $ORG (may not reach this repo)" present api orgs/$ORG/codespaces/secrets --paginate --jq '.secrets[].name' \
      || note "skipped org Codespaces secrets (needs org admin)"
    if user_secrets=$(ghx api user/codespaces/secrets --paginate --jq '.secrets[] | "\(.name)\t\(.visibility)"'); then
      for row in ${(f)user_secrets}; do
        n=${row%%$'\t'*}; vis=${row#*$'\t'}
        [[ $vis == selected ]] && ! ghx api user/codespaces/secrets/$n/repositories --jq '.repositories[].full_name' | grep -qx $REPO_SLUG && continue
        emit "codespaces user (reaches $REPO_SLUG)" $n present
      done
    else
      note "skipped user Codespaces secrets: run gh auth refresh -h github.com -s codespace"
    fi

    if list_names "actions secret repo $REPO_SLUG" present secret list --app actions --repo $REPO_SLUG --json name --jq '.[].name'; then
      print -r -- "actions-listed	-	ok" >> $NAMES
      list_names "actions variable repo $REPO_SLUG" present variable list --repo $REPO_SLUG --json name --jq '.[].name'
      list_names "actions secret org $ORG (shared with this repo)" present api repos/$REPO_SLUG/actions/organization-secrets --paginate --jq '.secrets[].name'
      list_names "actions variable org $ORG (shared with this repo)" present api repos/$REPO_SLUG/actions/organization-variables --paginate --jq '.variables[].name'
      list_names "dependabot secret repo $REPO_SLUG" present secret list --app dependabot --repo $REPO_SLUG --json name --jq '.[].name'
      for e in ${(f)"$(ghx api repos/$REPO_SLUG/environments --jq '.environments[].name')"}; do
        [[ -z $e ]] && continue
        list_names "actions secret environment $e" present secret list --env $e --repo $REPO_SLUG --json name --jq '.[].name'
        list_names "actions variable environment $e" present variable list --env $e --repo $REPO_SLUG --json name --jq '.[].name'
      done
    else
      note "skipped Actions secrets (needs repo admin through your own login: env -u GITHUB_TOKEN -u GH_TOKEN gh auth login --web)"
    fi
  else
    note "skipped GitHub: gh not authenticated"
  fi

  # Migration part: deleted with the blobs in TASK-111.15.2.
  if aws sts get-caller-identity >/dev/null 2>&1; then
    for b in $BLOBS; do
      aws ssm get-parameter --region $REGION --name $b --with-decryption --query Parameter.Value --output text \
        | tr -d '\r' | sed -E 's/^([A-Z][A-Z0-9_]*)[[:space:]]*=[[:space:]]*/\1=/' | scan_lines "ssm-blob $b"
    done
    for p in $(aws ssm get-parameters-by-path --region $REGION --path /sre-bot --query 'Parameters[].Name' --output text); do
      v=$(aws ssm get-parameter --region $REGION --name $p --with-decryption --query Parameter.Value --output text)
      [[ $v == $PLACEHOLDER ]] && s=placeholder || { [[ -z $v ]] && s=empty || s=set; }
      unset v
      print -r -- "ssm-param	${p#/sre-bot/}	$s" >> $NAMES
    done
  else
    note "skipped SSM: no AWS credentials"
  fi

  sha=$(git -C $ROOT rev-parse $BASELINE)
  if [[ $(cut -d' ' -f1 $OUT_DIR/.baseline-names.txt 2>/dev/null) == $sha ]]; then tree=(); else
    git -C $ROOT archive $sha app | tar -x -C $BASE_DIR && tree=($BASE_DIR/app); fi
  cd $APP && uv run --quiet python -m bin.audit_env_names $show $sha $tree < $NAMES
  uv run --quiet python -m bin.audit_env_coverage $show $filters < $NAMES
} 2>&1 | tee $OUT

print "\nwritten: $OUT"
