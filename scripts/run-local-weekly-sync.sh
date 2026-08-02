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
DRY_RUN_INGEST_BACKUP=""
DRY_RUN_INGEST_EXISTED="0"

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
    if [ -n "${DRY_RUN_INGEST_BACKUP}" ] && [ -f "${DRY_RUN_INGEST_BACKUP}" ]; then
      cp "${DRY_RUN_INGEST_BACKUP}" "${ROOT_DIR}/data/literature-ingest-latest.json" || true
      rm -f "${DRY_RUN_INGEST_BACKUP}" || true
    elif [ "${DRY_RUN_INGEST_EXISTED}" = "0" ]; then
      rm -f "${ROOT_DIR}/data/literature-ingest-latest.json" || true
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

if git status --porcelain --untracked-files=all -- data assets pages index.html | grep -q . || ! git diff --quiet || ! git diff --cached --quiet; then
  echo "存在未提交改动或公开目录未跟踪文件，停止周更以避免混入自动提交。" >&2
  git status --short
  exit 3
fi

if [ "${DRY_RUN}" = "1" ]; then
  DRY_RUN_FULL_BACKUP="$(mktemp "${LOG_DIR}/literature-full.dry-run.XXXXXX.json")"
  cp "data/literature-full.json" "${DRY_RUN_FULL_BACKUP}"
  if [ -f "data/literature-ingest-latest.json" ]; then
    DRY_RUN_INGEST_EXISTED="1"
    DRY_RUN_INGEST_BACKUP="$(mktemp "${LOG_DIR}/literature-ingest-latest.dry-run.XXXXXX.json")"
    cp "data/literature-ingest-latest.json" "${DRY_RUN_INGEST_BACKUP}"
  fi
  echo "MG_WEEKLY_DRY_RUN=1：将完整执行管线和校验，但不 commit/push；退出时恢复本地 full 与 tracked 产物。"
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [ "${CURRENT_BRANCH}" != "main" ]; then
  echo "当前分支是 ${CURRENT_BRANCH}，本地周更只允许在 main 分支执行。" >&2
  exit 4
fi

git fetch origin main
git pull --ff-only origin main

# full 模式在合并后执行 MG-core 原子过滤/归档，再重分类并完成全部公开产物；所有步骤共用同一审计 run id。
python3 scripts/run-weekly-pipeline.py --mode authoritative-full --run-id "local-${STAMP}"

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
data_match = re.search(r"window\.MG_LITERATURE_DATA\s*=\s*(.*);\s*$", recent_text, re.S)

def readWindowNumber(name):
    match = re.search(rf"window\.{re.escape(name)}\s*=\s*(\d+);", recent_text)
    return int(match.group(1)) if match else None

if not data_match:
    raise SystemExit("无法解析 data/literature-recent.js")

recent = json.loads(data_match.group(1))
publicRollingCount = readWindowNumber("MG_PUBLIC_ROLLING_COUNT")
semanticFullCount = readWindowNumber("MG_SEMANTIC_FULL_COUNT") or readWindowNumber("MG_TOTAL_COUNT")
full_dt, full_item = latest(full)
recent_dt, recent_item = latest(recent)

if publicRollingCount is not None and publicRollingCount != len(recent):
    raise SystemExit(f"MG_PUBLIC_ROLLING_COUNT={publicRollingCount} 与 recent_count={len(recent)} 不一致")
if semanticFullCount != len(full):
    raise SystemExit(f"MG_SEMANTIC_FULL_COUNT={semanticFullCount} 与 full_count={len(full)} 不一致")
if full_dt and recent_dt and recent_dt < full_dt:
    raise SystemExit(
        f"recent 最新日期 {recent_item.get('entry_date')} 早于 full 最新日期 {full_item.get('entry_date')}"
    )

print("同步校验通过")
print(f"  full_count: {len(full)}")
print(f"  recent_count: {len(recent)}")
print(f"  public_rolling_count: {publicRollingCount if publicRollingCount is not None else len(recent)}")
print(f"  semantic_full_count: {semanticFullCount}")
print(f"  latest_full: {full_item.get('pmid')} {full_item.get('entry_date')}")
print(f"  latest_recent: {recent_item.get('pmid')} {recent_item.get('entry_date')}")
PY

if [ "${DRY_RUN}" = "1" ]; then
  echo "MG_WEEKLY_DRY_RUN=1，跳过 git add/commit/push。"
else
  if git ls-files --others --exclude-standard -- data assets pages index.html | grep -q .; then
    echo "管线生成了未纳入版本控制的公开文件，停止提交；请先审查并显式加入仓库。" >&2
    git ls-files --others --exclude-standard -- data assets pages index.html >&2
    exit 5
  fi
  # 只暂存已经纳入版本控制的公开产物，避免通配符把意外文件带入发布。
  git add -u -- data assets pages index.html

  if git diff --cached --quiet; then
    echo "没有公开数据变更需要提交。"
  else
    git commit -m "chore: update MG hub weekly data"
    git push origin main
  fi
fi

echo "Finished: $(date '+%Y-%m-%d %H:%M:%S %Z')"
