import csv
import json
from datetime import datetime, timezone

import pytest

from scripts.common.china_drug_trials_import import (
    import_china_drug_trials_exports,
    load_export_records,
)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_china_drug_trials_csv_import_compares_and_normalizes(tmp_path):
    cache = tmp_path / "cache.json"
    changes_path = tmp_path / "changes.json"
    cache.write_text(json.dumps({
        "schema_version": "1.0",
        "source": "ChinaDrugTrials.org.cn",
        "mode": "cache",
        "records": [
            {
                "registry_id": "CTR20260001",
                "title": "旧 MG 试验",
                "drug_name": "药物A",
                "indication": "重症肌无力",
                "status": "NOT_YET_RECRUITING",
            },
            {
                "registry_id": "CTR20250009",
                "title": "将被移除的 MG 试验",
                "drug_name": "药物C",
                "indication": "重症肌无力",
                "status": "COMPLETED",
            },
        ],
    }), encoding="utf-8")
    source = tmp_path / "monthly.csv"
    write_csv(source, [
        {
            "试验登记号": "CTR20260001",
            "试验题目": "更新后的 MG 试验",
            "药物名称": "药物A",
            "适应症": "重症肌无力",
            "试验状态": "进行中 招募中",
            "试验分期": "III期",
        },
        {
            "试验登记号": "CTR20260002",
            "试验题目": "新增 MG 试验",
            "药物名称": "药物B",
            "适应症": "全身型重症肌无力",
            "试验状态": "进行中 尚未招募",
            "试验分期": "II期",
        },
    ])

    payload, changes = import_china_drug_trials_exports(
        cache,
        [source],
        changes_path=changes_path,
        now=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert payload["total"] == 2
    assert changes["added_count"] == 1
    assert changes["updated_count"] == 1
    assert changes["removed_count"] == 1
    by_id = {item["registry_id"]: item for item in payload["records"]}
    assert by_id["CTR20260001"]["status"] == "RECRUITING"
    assert by_id["CTR20260002"]["status"] == "NOT_YET_RECRUITING"
    assert by_id["CTR20260002"]["official_url"].endswith("keyword=CTR20260002")
    assert json.loads(changes_path.read_text(encoding="utf-8"))["added_count"] == 1


def test_china_drug_trials_html_xls_export_is_supported(tmp_path):
    source = tmp_path / "official-export.xls"
    source.write_text(
        """
        <html><body><table>
          <tr><td>下载时间</td><td>2026-07-28</td></tr>
          <tr><th>登记号</th><th>试验题目</th><th>药物名称</th><th>适应症</th></tr>
          <tr><td>CTR20260003</td><td>MG monthly study</td><td>Drug C</td><td>Myasthenia Gravis</td></tr>
        </table></body></html>
        """,
        encoding="utf-8",
    )

    records = load_export_records(source)

    assert records == [{
        "registry_id": "CTR20260003",
        "title": "MG monthly study",
        "drug_name": "Drug C",
        "indication": "Myasthenia Gravis",
    }]


def test_china_drug_trials_large_drop_preserves_last_good_cache(tmp_path):
    cache = tmp_path / "cache.json"
    old_records = [
        {
            "registry_id": f"CTR2025{index:04d}",
            "title": f"MG study {index}",
            "indication": "重症肌无力",
        }
        for index in range(10)
    ]
    cache.write_text(json.dumps({
        "source": "ChinaDrugTrials.org.cn",
        "mode": "cache",
        "records": old_records,
    }), encoding="utf-8")
    before = cache.read_bytes()
    source = tmp_path / "partial.csv"
    write_csv(source, [{
        "登记号": "CTR20260004",
        "试验题目": "Only one MG record",
        "适应症": "重症肌无力",
    }])

    with pytest.raises(ValueError, match="60%"):
        import_china_drug_trials_exports(cache, [source])

    assert cache.read_bytes() == before
