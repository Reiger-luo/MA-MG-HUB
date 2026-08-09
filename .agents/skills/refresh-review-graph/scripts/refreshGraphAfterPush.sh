#!/usr/bin/env bash

set -euo pipefail

showUsage() {
  printf 'Usage: bash refreshGraphAfterPush.sh --base <pre-push-commit> [--upstream <remote-ref>]\n' >&2
}

baseRef=""
upstreamRef=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      baseRef="${2:-}"
      shift 2
      ;;
    --upstream)
      upstreamRef="${2:-}"
      shift 2
      ;;
    *)
      showUsage
      exit 2
      ;;
  esac
done

if [[ -z "$baseRef" ]]; then
  showUsage
  exit 2
fi

projectRoot=$(git rev-parse --show-toplevel)
cd "$projectRoot"

if ! git cat-file -e "${baseRef}^{commit}" 2>/dev/null; then
  printf 'CRG refresh failed: base commit %s is not available locally.\n' "$baseRef" >&2
  exit 3
fi

if [[ -z "$upstreamRef" ]]; then
  upstreamRef=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)
fi

if [[ -z "$upstreamRef" ]]; then
  printf 'CRG refresh failed: current branch has no upstream reference.\n' >&2
  exit 4
fi

currentHead=$(git rev-parse HEAD)
upstreamHead=$(git rev-parse "$upstreamRef")

if [[ "$currentHead" != "$upstreamHead" ]]; then
  printf 'CRG refresh refused: local HEAD %s is not pushed to %s (%s).\n' \
    "$currentHead" "$upstreamRef" "$upstreamHead" >&2
  exit 5
fi

# 避免把 push 之后尚未提交的源码混入上线后的图谱
dirtyState=$(git status --porcelain --untracked-files=all -- \
  scripts worker tests ':(glob)assets/*.js')
if [[ -n "$dirtyState" ]]; then
  printf 'CRG refresh refused: graph-covered paths contain uncommitted changes.\n%s\n' \
    "$dirtyState" >&2
  exit 6
fi

graphableCount=0
while IFS= read -r filePath; do
  case "$filePath" in
    scripts/*|assets/*.js|worker/*|tests/*)
      graphableCount=$((graphableCount + 1))
      ;;
  esac
done < <(git diff --name-only --diff-filter=ACMRD "${baseRef}..${currentHead}")

if [[ "$graphableCount" -eq 0 ]]; then
  printf 'CRG_REFRESH_SKIPPED=no graph-covered files changed between %s and %s\n' \
    "$baseRef" "$currentHead"
  exit 0
fi

if command -v code-review-graph >/dev/null 2>&1; then
  graphCommand=(code-review-graph)
elif command -v uvx >/dev/null 2>&1; then
  graphCommand=(uvx --from code-review-graph==2.3.7 code-review-graph)
else
  printf 'CRG refresh failed: neither code-review-graph nor uvx is available.\n' >&2
  exit 7
fi

# 每次 push 后完整重建，避免空图或陈旧基线被误判为可增量更新
"${graphCommand[@]}" build --repo "$projectRoot"
"${graphCommand[@]}" detect-changes --repo "$projectRoot" --base "$baseRef" --brief

printf 'CRG_REFRESH_HEAD=%s\n' "$currentHead"
printf 'CRG_REFRESH_UPSTREAM=%s\n' "$upstreamRef"
"${graphCommand[@]}" status --repo "$projectRoot" --json
