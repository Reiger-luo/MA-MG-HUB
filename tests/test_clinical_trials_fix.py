"""临床试验 tab 的发布契约测试（源自 t_e44f4b49）。

三条历史缺陷：?tab=trials 深链、clinical-trials-data.js 空壳、决策信号与分面无数据。

隔离约定：builder 通过 MG_DATA_DIR 把数据根指向临时目录，测试只读真实缓存、
不写仓库 data/。真实产物改动会让周更的前置「工作树必须干净」校验失败。
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
REPO_DATA = PROJECT / "data"
# 只读种子：真实缓存 + 上一期基线，复制进临时目录后 builder 在隔离数据根里跑
SEED_FILES = (
    "clinicaltrials-pipeline-cache.json",
    "chictr-trials-cache.json",
    "china-drug-trials-cache.json",
    "clinicaltrials-weekly-changes-snapshot.json",
    "clinicalTrialsSummary.js",
)
# 测试绝不允许改写的已发布产物
PUBLISHED_ARTIFACTS = (
    "clinical-trials-data.js",
    "clinicalTrialsSummary.js",
    "clinicaltrials-weekly-changes-snapshot.json",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """复制缓存后在临时数据根里跑一次 builder，返回隔离目录与运行结果。"""
    data_dir = tmp_path_factory.mktemp("clinical-trials-data")
    for name in SEED_FILES:
        source = REPO_DATA / name
        if source.is_file():
            shutil.copy2(source, data_dir / name)

    published = [REPO_DATA / name for name in PUBLISHED_ARTIFACTS]
    before = {path: _digest(path) for path in published}

    result = subprocess.run(
        [sys.executable, str(_find_builder())],
        cwd=str(PROJECT),
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "MG_SKIP_CLINICALTRIALS": "1", "MG_DATA_DIR": str(data_dir)},
    )

    after = {path: _digest(path) for path in published}
    return {
        "data_dir": data_dir,
        "result": result,
        "published_before": before,
        "published_after": after,
    }


# ── 缺陷 1：?tab=trials 深链必须激活「临床试验」tab ──────────────────

def test_literature_js_reads_tab_query_param():
    """literature.js 必须读取 ?tab= 并作为 initialKey 传给 initTabs。"""
    js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    assert re.search(r"params\.get\(['\"]tab['\"]\)", js), (
        "literature.js must read 'tab' from URLSearchParams"
    )
    assert "initialKey" in js, (
        "literature.js must pass initialKey to hub.initTabs for deep-link support"
    )


# ── 缺陷 2：builder 必须从真实缓存产出非空记录 ──────────────────────

def test_builder_script_exists():
    """必须存在确定性的 builder 脚本。"""
    assert _find_builder(), "A builder script (scripts/build*clinical*) must exist"


def test_builder_does_not_touch_published_artifacts(built):
    """builder 在隔离数据根里运行，不得改写仓库已发布产物。"""
    assert built["result"].returncode == 0, f"Builder failed: {built['result'].stderr}"
    changed = [
        path.name
        for path in built["published_before"]
        if built["published_before"][path] != built["published_after"][path]
    ]
    assert not changed, f"builder 改写了仓库已发布产物: {changed}"


def test_builder_produces_nonzero_ctgov_records(built):
    """ClinicalTrials.gov 记录必须非空。"""
    data = _load_trials_data(built["data_dir"])
    ct_source = _get_source(data, "ClinicalTrials.gov")
    assert len(ct_source["records"]) > 0, (
        "ClinicalTrials.gov records must be nonzero (cache has 313 items)"
    )


def test_builder_produces_nonzero_chictr_records(built):
    """ChiCTR 记录必须非空。"""
    data = _load_trials_data(built["data_dir"])
    chictr_source = _get_source(data, "ChiCTR")
    assert len(chictr_source["records"]) > 0, (
        "ChiCTR records must be nonzero (cache has 4 items)"
    )


def test_builder_total_count_matches_sum(built):
    """meta.total_count 必须等于各来源记录数之和。"""
    data = _load_trials_data(built["data_dir"])
    total = sum(len(s.get("records", [])) for s in data.get("sources", []))
    assert data["meta"]["total_count"] == total, (
        f"total_count={data['meta']['total_count']} != sum={total}"
    )


# ── 缺陷 3：决策信号与分面必须有真实数据 ────────────────────────────

def test_builder_produces_decision_signals(built):
    """必须产出至少一条决策信号，且带 title/detail。"""
    data = _load_trials_data(built["data_dir"])
    signals = data.get("decision_signals", [])
    assert len(signals) > 0, "decision_signals must be non-empty"
    for signal in signals:
        assert signal.get("title"), f"Signal missing title: {signal}"
        assert signal.get("detail"), f"Signal missing detail: {signal}"


def test_builder_records_have_facet_fields(built):
    """记录必须带 drug_class / indication / status_label 以供分面。"""
    data = _load_trials_data(built["data_dir"])
    all_records = []
    for source in data.get("sources", []):
        all_records.extend(source.get("records", []))
    assert len(all_records) > 0, "No records at all"
    with_drug = [r for r in all_records if r.get("drug_class")]
    with_indication = [r for r in all_records if r.get("indication")]
    with_status = [r for r in all_records if r.get("status_label")]
    assert len(with_status) > 0, "No records have status_label"
    assert len(with_drug) > 0 or len(with_indication) > 0, (
        "No records have drug_class or indication — facets will be empty"
    )


def test_builder_source_order(built):
    """来源顺序必须固定：ClinicalTrials.gov → ChiCTR → ChinaDrugTrials。"""
    data = _load_trials_data(built["data_dir"])
    source_names = [s["source"] for s in data.get("sources", [])]
    assert source_names == ["ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials"], (
        f"Source order wrong: {source_names}"
    )


def test_builder_china_drug_trials_empty_with_warning(built):
    """ChinaDrugTrials 可以为空，但必须给出显式 mode。"""
    data = _load_trials_data(built["data_dir"])
    cdt = _get_source(data, "ChinaDrugTrials")
    if not cdt["records"]:
        assert cdt["meta"].get("mode") in ("unavailable", "audited"), (
            f"Empty ChinaDrugTrials must have explicit mode, got: {cdt['meta']}"
        )


def test_builder_writes_lightweight_dashboard_summary(built):
    """首页摘要必须独立于完整矩阵，且远小于完整明细。"""
    data_dir = built["data_dir"]
    summary_path = data_dir / "clinicalTrialsSummary.js"
    summary_text = summary_path.read_text(encoding="utf-8")
    match = re.search(r"=\s*(\{.*\})\s*;?\s*$", summary_text, re.S)
    assert match, f"Cannot parse JSON from {summary_path}"
    summary = json.loads(match.group(1))
    full_data = _load_trials_data(data_dir)

    assert summary["meta"]["total_count"] == full_data["meta"]["total_count"]
    assert summary["pipeline_matrix_count"] == len(full_data["pipeline_matrix"])
    assert len(summary["source_counts"]) == 3

    # 首页摘要必须远小于完整明细：相对比例约束，试验数量增长后依然有效。
    summary_size = summary_path.stat().st_size
    full_size = (data_dir / "clinical-trials-data.js").stat().st_size
    assert summary_size < 64_000, f"首页摘要过大: {summary_size} bytes"
    assert summary_size < full_size * 0.05, (
        f"首页摘要应远小于完整明细: summary={summary_size} full={full_size}"
    )


# ── Helpers ───────────────────────────────────────────────────────────

def _find_builder():
    candidates = sorted(PROJECT.glob("scripts/build*clinical*"))
    assert candidates, "No builder script found matching scripts/build*clinical*"
    return candidates[0]


def _digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_trials_data(data_dir: Path):
    js_path = data_dir / "clinical-trials-data.js"
    text = js_path.read_text(encoding="utf-8")
    match = re.search(r"=\s*(\{.*\})\s*;?\s*$", text, re.S)
    assert match, f"Cannot parse JSON from {js_path}"
    return json.loads(match.group(1))


def _get_source(data, name):
    for source in data.get("sources", []):
        if source["source"] == name:
            return source
    raise AssertionError(f"Source '{name}' not found in data")