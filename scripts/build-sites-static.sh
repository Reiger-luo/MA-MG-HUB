#!/usr/bin/env bash
set -euo pipefail

projectRoot="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
buildTemp="$(mktemp -d)"
trap 'rm -rf "$buildTemp"' EXIT

mkdir -p "$buildTemp/assets" "$buildTemp/server"

# 只复制 Git 管理的公开站点文件，避免把本地 full 数据带入部署包。
while IFS= read -r -d '' sourceFile; do
  mkdir -p "$buildTemp/assets/$(dirname "$sourceFile")"
  cp "$projectRoot/$sourceFile" "$buildTemp/assets/$sourceFile"
done < <(git -C "$projectRoot" ls-files -z -- index.html pages assets data .nojekyll)

cp "$projectRoot/worker/index.js" "$buildTemp/server/index.js"

if [ -d "$projectRoot/dist" ]; then
  rm -rf "$projectRoot/dist"
fi
mv "$buildTemp" "$projectRoot/dist"
trap - EXIT
