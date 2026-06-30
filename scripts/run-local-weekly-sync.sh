#!/usr/bin/env bash
# Hermes/本地工作站周更入口：以本地 literature-full.json 为源头生成公开数据并推送。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/.hermes-audit"
LOCK_DIR="${LOG_DIR}/weekly-sync.lock"
STAMP="$(date '+%Y%m%d-%H%M%S')"
LOG_FILE="${LOG_DIR}/weekly-sync-${STAMP}.log"
DRY_RUN="${MG_WEEKLY_DRY_RUN:-0}"
DRY_RUN_FULL_BACKUP=""

mkdir -p "${LOG_DIR}"

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "已有周更任务在运行：${LOCK_DIR}" >&2
  exit 9
fi

cleanup() {
  local status=$?
  if [ "${DRY_RUN}" = "1" ]; then
    if [ -n "${DRY_RUN_FULL_BACKUP}" ] && [ -f "${DRY_RUN_FULL_BACKUP}" ]; then
      cp "${DRY_RUN_FULL_BACKUP}" "${ROOT_DIR}/data/literature-full.json" || true
      rm -f "${DRY_RUN_FULL_BACKUP}" || true
    fi
    git -C "${ROOT_DIR}" restore --staged --worktree -- data assets pages index.html 2>/dev/null || true
  fi
  rmdir "${LOCK_DIR}" 2>/dev/null || true
  return "${status}"
}
trap cleanup EXIT

exec > >(tee -a "${LOG_FILE}") 2>&1

cd "${ROOT_DIR}"

echo "MA-MG-HUB local weekly sync"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Repo: ${ROOT_DIR}"
echo "Log: ${LOG_FILE}"

if [ ! -f "data/literature-full.json" ]; then
  echo "缺少 data/literature-full.json；本地/Hermes 周更必须以 full 库为源头。" >&2
  exit 2
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "存在未提交的 tracked 改动，停止周更以避免混入自动提交。" >&2
  git status --short
  exit 3
fi

if [ "${DRY_RUN}" = "1" ]; then
  DRY_RUN_FULL_BACKUP="$(mktemp "${LOG_DIR}/literature-full.dry-run.XXXXXX.json")"
  cp "data/literature-full.json" "${DRY_RUN_FULL_BACKUP}"
  echo "MG_WEEKLY_DRY_RUN=1：将完整执行管线和校验，但不 commit/push；退出时恢复本地 full 与 tracked 产物。"
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [ "${CURRENT_BRANCH}" != "main" ]; then
  echo "当前分支是 ${CURRENT_BRANCH}，本地周更只允许在 main 分支执行。" >&2
  exit 4
fi

git fetch origin main
git pull --ff-only origin main

python3 scripts/run-weekly-pipeline.py --skip-status

# 分类规则可能独立于周更变化；周更后重扫 recent，保证公开数据使用最新证据规则。
python3 scripts/reclassify-existing-iii.py --modes ALL --recent-days 365

# reclassify 会重建文献与前端数据；这里再刷新依赖证据等级的下游产物。
python3 scripts/buildFullLiteratureIndex.py
python3 scripts/buildCommunityData.py
python3 scripts/build-knowledge-data.py
python3 scripts/build-curated-topic-data.py
python3 scripts/generate-weekly-summary.py
python3 scripts/generate-pipeline-status.py

python3 - <<'PY'
import json
import re
from datetime import datetime
from pathlib import Path


def parse_date(value):
    if not value:
        return None
    value = str(value).strip()
    for pattern in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    match = re.match(r"(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?", value)
    if match:
        year, month, day = match.groups()
        return datetime(int(year), int(month), int(day or 1))
    return None


def latest(items):
    dated = [(parse_date(item.get("entry_date")) or parse_date(item.get("pub_date")), item) for item in items]
    dated = [(dt, item) for dt, item in dated if dt]
    return max(dated, key=lambda pair: pair[0]) if dated else (None, None)


full = json.loads(Path("data/literature-full.json").read_text(encoding="utf-8"))
recent_text = Path("data/literature-recent.js").read_text(encoding="utf-8")
total_match = re.search(r"window\.MG_TOTAL_COUNT\s*=\s*(\d+);", recent_text)
data_match = re.search(r"window\.MG_LITERATURE_DATA\s*=\s*(.*);\s*$", recent_text, re.S)
if not total_match or not data_match:
    raise SystemExit("无法解析 data/literature-recent.js")

recent = json.loads(data_match.group(1))
recent_total = int(total_match.group(1))
full_dt, full_item = latest(full)
recent_dt, recent_item = latest(recent)

if recent_total != len(full):
    raise SystemExit(f"MG_TOTAL_COUNT={recent_total} 与 full_count={len(full)} 不一致")
if full_dt and recent_dt and recent_dt < full_dt:
    raise SystemExit(
        f"recent 最新日期 {recent_item.get('entry_date')} 早于 full 最新日期 {full_item.get('entry_date')}"
    )

print("同步校验通过")
print(f"  full_count: {len(full)}")
print(f"  recent_count: {len(recent)}")
print(f"  latest_full: {full_item.get('pmid')} {full_item.get('entry_date')}")
print(f"  latest_recent: {recent_item.get('pmid')} {recent_item.get('entry_date')}")
PY

if [ "${DRY_RUN}" = "1" ]; then
  echo "MG_WEEKLY_DRY_RUN=1，跳过 git add/commit/push。"
else
  git add \
    data/*.js \
    data/weekly-summary.md \
    data/china-regulatory-status.json \
    data/clinicaltrials-pipeline-cache.json \
    assets/*.js \
    assets/*.css \
    pages/*.html \
    index.html

  if git diff --cached --quiet; then
    echo "没有公开数据变更需要提交。"
  else
    git commit -m "chore: update MG hub weekly data"
    git push origin main
  fi
fi

echo "Finished: $(date '+%Y-%m-%d %H:%M:%S %Z')"
