#!/usr/bin/env zsh
# Environment-name audit: one action per name (none, delete, check) for every name set in the env
# files, the Codespaces secrets, the GitHub Actions and Dependabot secrets and variables, and the production
# SSM parameters. Read-only. Never prints a value: names and a state only (set, empty, commented,
# placeholder, present). A secret parameter is compared with the terraform placeholder in-process.
# Developer helper, not part of the app.
#
# Usage (from any directory; gh auth and AWS read credentials make their sections run, else they are skipped):
#   zsh bin/env-checks.zsh                 # full audit; rows needing no action are hidden
#   zsh bin/env-checks.zsh --all           # also list the rows needing no action
#   zsh bin/env-checks.zsh ACCESS_ SLACK   # only names starting with any argument
# GitHub listings need your own login where the Codespace token is refused (Actions secrets, repo admin):
#   env -u GITHUB_TOKEN -u GH_TOKEN gh auth login --web; the script then retries with it automatically.
# User Codespaces secrets need the codespace scope once: gh auth refresh -h github.com -s codespace
# Plan and apply, as terraform does: the audit only plans. It writes tmp/env-checks/<UTC>.txt (gitignored,
# never commit it, also echoed) and tmp/env-checks/<UTC>.plan.sh, the commands for the delete rows
# (env files, Codespaces, Actions, Dependabot; never SSM or organization names). Nothing is changed until:
#   zsh bin/env-checks.zsh apply tmp/env-checks/<UTC>.plan.sh   # or: make env-checks-apply PLAN=<file>
# which prints that exact plan, asks for 'yes', runs it line by line, logs to <UTC>.plan.applied.txt and
# renames the plan so it cannot run twice. Plan again afterwards to confirm the rows are gone.
# A delete needs evidence of retirement (a RETIRED entry in audit_env_names.py); a name nothing reads
# or no default-branch workflow references is a check showing its last reference in git history, looked up here
# for those names only (the audit's --lookups pass lists them) and handed to the audit as LAST_REFS_FILE.
# Classifier: app/bin/audit_env_names.py (each present name); app/bin/audit_env_coverage.py (where each name
# supplied through the environment is missing: terraform/ssm.tf, SSM, Codespaces).
# app/.env.example is not scanned: make env-example generates it from the settings classes.

setopt no_unset pipe_fail
unsetopt xtrace verbose

# apply PLAN: show the saved plan, ask, then run it; never plans or audits.
if [[ ${1:-} == apply ]]; then
  plan=${${2:-}:A}
  [[ -n ${2:-} && -f $plan && $plan == *.plan.sh ]] || { print -u2 "usage: $0 apply tmp/env-checks/<UTC>.plan.sh (a plan this script wrote)"; exit 2 }
  lines=(${(f)"$(grep -vE '^[[:space:]]*(#|$)' $plan)"})
  (( ${#lines} )) || { print "No changes in $plan."; exit 0 }
  age=$(( $(date +%s) - $(stat -c %Y $plan) ))
  print "Plan $plan ($(( age / 60 )) min old; plan again if anything changed since):\n"
  cat $plan
  print "\n${#lines} command(s) will change env files, Codespaces, Actions or Dependabot secrets and variables."
  read -r "answer?Do you want to apply this plan? Only 'yes' will be accepted: "
  [[ $answer == yes ]] || { print "Apply cancelled; nothing changed."; exit 1 }
  log=${plan%.sh}.applied.txt
  cd ${0:A:h:h}
  for line in $lines; do
    if zsh -c $line; then print -r -- "ok      $line"; else print -r -- "FAILED  $line"; fi
  done 2>&1 | tee $log
  mv $plan ${plan%.sh}.applied.sh
  failed=$(grep -c '^FAILED' $log)
  print "\nApplied: $(grep -c '^ok' $log) ok, $failed failed; log $log; the plan is now ${plan%.sh}.applied.sh."
  print "Plan again to confirm: zsh bin/env-checks.zsh"
  exit $(( failed > 0 ))
fi

ROOT=$(git -C ${0:A:h} rev-parse --show-toplevel)
APP=$ROOT/app
REPO_SLUG=cds-snc/sre-bot
ORG=cds-snc
REGION=ca-central-1
PLACEHOLDER=set-outside-terraform   # terraform/ssm.tf value_wo
OUT_DIR=$ROOT/tmp/env-checks
mkdir -p $OUT_DIR
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=$OUT_DIR/$STAMP.txt
PLAN=$OUT_DIR/$STAMP.plan.sh
NAMES=$(mktemp)
REFS=$(mktemp)
trap 'rm -f $NAMES $REFS' EXIT
show=()
filters=()
for a in "$@"; do [[ $a == --all ]] && show=(--all) || filters+=($a); done

keep() { (( ${#filters} == 0 )) && return 0; local f; for f in $filters; do [[ $1 == $f* ]] && return 0; done; return 1; }
emit() { keep $2 && print -r -- "$1	$2	$3" >> $NAMES; }
note() { print -r -- "$*" >&2; }
# last_ref KIND NAME: the newest commit whose diff mentions the name, on the default branch first.
# workflow: a secrets.NAME or vars.NAME in .github; repo: the name anywhere but the planning docs.
last_ref() {
  local kind=$1 n=$2 main ref
  main=$(git -C $ROOT rev-parse -q --verify origin/main || git -C $ROOT rev-parse -q --verify main)
  local -a pattern paths
  if [[ $kind == workflow ]]; then pattern=(-G "(secrets|vars)\.$n\b"); paths=(-- .github)
  else pattern=(-G "\b$n\b"); paths=(-- . ':(exclude)backlog' ':(exclude)decisions'); fi
  ref=$(git -C $ROOT log $main -1 $pattern --format='%h %as %s' $paths)
  [[ -z $ref ]] && ref=$(git -C $ROOT log --all -1 $pattern --format='%h %as %s' $paths) && [[ -n $ref ]] && ref="$ref (unmerged branch only)"
  print -r -- "${ref:-no reference in git history}"
}
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

  # app/.env.example is generated (make env-example) and a test fails when it drifts, so only app/.env is scanned.
  for f in $APP/.env; do
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

  # The /sre-bot/<NAME> parameters: set, empty or still on the terraform placeholder.
  if aws sts get-caller-identity >/dev/null 2>&1; then
    for p in $(aws ssm get-parameters-by-path --region $REGION --path /sre-bot --query 'Parameters[].Name' --output text); do
      v=$(aws ssm get-parameter --region $REGION --name $p --with-decryption --query Parameter.Value --output text)
      [[ $v == $PLACEHOLDER ]] && s=placeholder || { [[ -z $v ]] && s=empty || s=set; }
      unset v
      print -r -- "ssm-param	${p#/sre-bot/}	$s" >> $NAMES
    done
  else
    note "skipped SSM: no AWS credentials"
  fi

  cd $APP
  for row in ${(f)"$(uv run --quiet python -m bin.audit_env_names --lookups < $NAMES)"}; do
    [[ -n $row ]] && print -r -- "${row#*$'\t'}	$(last_ref ${row%%$'\t'*} ${row#*$'\t'})" >> $REFS
  done
  LAST_REFS_FILE=$REFS REPO_SLUG=$REPO_SLUG PLAN_FILE=$PLAN uv run --quiet python -m bin.audit_env_names $show < $NAMES
  uv run --quiet python -m bin.audit_env_coverage $show $filters < $NAMES
} 2>&1 | tee $OUT

print "\nwritten: $OUT"
if [[ -s $PLAN ]]; then
  print "plan: $PLAN ($(grep -cvE '^[[:space:]]*(#|$)' $PLAN) command(s); nothing has run)"
  print "apply: zsh bin/env-checks.zsh apply ${PLAN#$ROOT/}   (or make env-checks-apply PLAN=${PLAN#$ROOT/})"
else
  rm -f $PLAN
  print "plan: no changes"
fi
