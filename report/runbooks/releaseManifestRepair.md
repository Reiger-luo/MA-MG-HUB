# Release Manifest 漂移修复

手工修改 `data/*.js` 公开产物（或不完整重跑管线）后，`data/release-manifest.js` 中的哈希与磁盘文件不一致，首页出现"发布产物已漂移"，`validatePublicRelease.py --require-release` 报"哈希不符"。

## 判断漂移

```bash
python3 scripts/validatePublicRelease.py --source-only --require-release
```

输出 `release manifest 哈希不符：<文件名>` 即为漂移。首页"数据状态"与发布状态条也会显示漂移。

## 修复（三步）

```bash
# 1. 按当前磁盘产物重建 manifest
python3 - <<'PY'
import sys
sys.path.insert(0, 'scripts')
from datetime import datetime, timezone
from pathlib import Path
from common.pipeline_runner import generate_release_manifest
from common.publicDataContract import publicArtifactPaths

PROJECT = Path('.').resolve()
DATA = PROJECT / 'data'
audit = {
    'status': 'success',
    'run_id': 'local-20260801-contract-rebuild3',   # 保留与 HTML ?v= token 一致的 run_id
    'completed_at': datetime.now(timezone.utc).isoformat(),
}
payload = generate_release_manifest(audit, publicArtifactPaths(DATA), DATA / 'release-manifest.js', project=PROJECT)
print(f"manifest rebuilt: {len(payload['artifacts'])} artifacts")
PY

# 2. 刷新 pipeline-status（release_consistency 回到 ok）
python3 scripts/generate-pipeline-status.py

# 3. 再重建一次 manifest（pipeline-status.js 自身哈希刚变过），然后验证
python3 - <<'PY'
import sys
sys.path.insert(0, 'scripts')
from datetime import datetime, timezone
from pathlib import Path
from common.pipeline_runner import generate_release_manifest
from common.publicDataContract import publicArtifactPaths

PROJECT = Path('.').resolve()
DATA = PROJECT / 'data'
audit = {
    'status': 'success',
    'run_id': 'local-20260801-contract-rebuild3',
    'completed_at': datetime.now(timezone.utc).isoformat(),
}
payload = generate_release_manifest(audit, publicArtifactPaths(DATA), DATA / 'release-manifest.js', project=PROJECT)
print(f"manifest rebuilt: {len(payload['artifacts'])} artifacts")
PY
python3 scripts/validatePublicRelease.py --source-only --require-release
```

## 注意事项

- 必须重建**两次**：第一步后 `pipeline-status.js` 内容变化，其哈希又过期，所以要在刷新状态后再重建一次。
- `audit['status']` 只有在产物确实完整时才填 `success`；`generate_release_manifest` 会拒绝 `failed` 状态。
- `run_id` 保持与活动页面 `?v=` token 一致（查 `index.html` 的 script src），避免前端缓存 token 与 manifest 脱节。
- 修复后连同 `data/release-manifest.js`、`data/pipeline-status.js` 一起提交，并跑 `python3 -m pytest -q` 确认全绿。

## 根因避免

首选完整周更管线 `python3 scripts/run-weekly-pipeline.py`，它在末尾自动生成 manifest。仅当需要绕过抓取（如只改了叙事文本）时才用本 runbook 手工重建。
