"""前端运行时冒烟：用 jsdom 真实执行页面脚本。

仓库测试多为静态契约，无法覆盖 renderGroupedStatements / renderChapterContent /
renderGuidelineDivergence / collectMajorEvents 等 DOM 渲染函数；本测试调用
scripts/verifyFrontendRender.js 在真实 DOM 里跑一遍并核对关键输出。
node 或 jsdom 不可用时跳过，不阻塞其余测试。
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]


def test_frontend_render_smoke():
    if not shutil.which("node"):
        pytest.skip("node 不可用，跳过前端运行时冒烟")
    if not (PROJECT / "node_modules" / "jsdom").is_dir():
        pytest.skip("jsdom 不可用，跳过前端运行时冒烟")

    result = subprocess.run(
        ["node", str(PROJECT / "scripts" / "verifyFrontendRender.js")],
        cwd=str(PROJECT),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"冒烟脚本未返回 JSON（exit={result.returncode}）：\n"
            f"stdout={result.stdout[-500:]}\nstderr={result.stderr[-500:]}"
        )

    failed = [item for item in payload.get("checks") or [] if not item.get("ok")]
    assert not failed and result.returncode == 0, (
        "前端运行时冒烟失败："
        + "; ".join(f"{item['name']}（{item['detail']}）" for item in failed)
    )
    assert len(payload.get("checks") or []) >= 12, "冒烟检查项不足，可能被意外裁剪"
