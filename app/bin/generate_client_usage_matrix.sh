#!/usr/bin/env bash
set -euo pipefail

# Rebuilds client usage audit artifacts used by Wave 0 migration tracking.
# Output files are written under <repo>/tmp/.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

mkdir -p tmp

all_modules_file="tmp/_client_modules.txt"
total_usage_file="tmp/client_callsite_audit_sorted.tsv"
external_usage_file="tmp/client_external_usage_sorted.tsv"
joined_usage_file="tmp/client_usage_matrix.tsv"

find app/infrastructure/clients app/integrations \
  -type f -name '*.py' ! -path '*/__pycache__/*' | sort > "$all_modules_file"

: > tmp/client_callsite_audit.tsv
while IFS= read -r file; do
  rel="${file#app/}"
  mod="${rel%.py}"
  mod_dot="${mod//\//.}"
  pattern="(^|[[:space:]])(from|import)[[:space:]]+(app\\.)?${mod_dot}([[:space:]]|\\.|,|$)"

  hits=$(grep -RInE "$pattern" app tests --include='*.py' --exclude-dir='__pycache__' 2>/dev/null | grep -v "^${file}:" || true)
  count=$(printf '%s\n' "$hits" | sed '/^$/d' | wc -l | tr -d ' ')
  printf '%s\t%s\n' "$count" "$file" >> tmp/client_callsite_audit.tsv
done < "$all_modules_file"

sort -nr tmp/client_callsite_audit.tsv > "$total_usage_file"

: > tmp/client_external_usage.tsv
while IFS= read -r file; do
  rel="${file#app/}"
  mod="${rel%.py}"
  mod_dot="${mod//\//.}"
  pattern="(^|[[:space:]])(from|import)[[:space:]]+(app\\.)?${mod_dot}([[:space:]]|\\.|,|$)"

  hits=$(grep -RInE "$pattern" app --include='*.py' --exclude-dir='__pycache__' 2>/dev/null \
    | grep -v "^${file}:" \
    | grep -v '^app/tests/' \
    | grep -v '^app/integrations/' \
    | grep -v '^app/infrastructure/clients/' || true)
  count=$(printf '%s\n' "$hits" | sed '/^$/d' | wc -l | tr -d ' ')
  printf '%s\t%s\n' "$count" "$file" >> tmp/client_external_usage.tsv
done < "$all_modules_file"

sort -nr tmp/client_external_usage.tsv > "$external_usage_file"

awk -F '\t' '{a[$2]=$1} END {for (k in a) print k"\t"a[k]}' "$total_usage_file" | sort > tmp/_total.tsv
awk -F '\t' '{a[$2]=$1} END {for (k in a) print k"\t"a[k]}' "$external_usage_file" | sort > tmp/_external.tsv

join -t $'\t' -a1 -a2 -e 0 -o '0,1.2,2.2' tmp/_total.tsv tmp/_external.tsv \
  | awk -F '\t' 'BEGIN{OFS="\t"; print "module","total_refs_including_tests_and_internal","external_runtime_refs","classification"} {
      total=$2+0; ext=$3+0; cls="";
      if (total==0 && ext==0) cls="SAFE_PRUNE_CANDIDATE";
      else if (ext==0 && total>0) cls="INTERNAL_ONLY_OR_TEST_ONLY";
      else if (ext>=5) cls="HIGH_USAGE_SLOW_MIGRATION";
      else cls="MODERATE_USAGE_PHASED";
      print $1,total,ext,cls
    }' \
  | sort -t $'\t' -k4,4 -k3,3nr > "$joined_usage_file"

echo "Generated:"
echo "- $total_usage_file"
echo "- $external_usage_file"
echo "- $joined_usage_file"
