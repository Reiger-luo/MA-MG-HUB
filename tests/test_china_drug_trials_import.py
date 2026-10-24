import csv
import json
from datetime import datetime, timezone

import pytest

from scripts.common.china_drug_trials_import import (
    compare_records,
    import_china_drug_trials_exports,
    load_export_records,
)
from scripts.common.clinical_registry import normalize_cdt_phase


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


SPREADSHEETML_EXPORT = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="Sheet1">
  <Table>
   <Row><Cell><Data ss:Type="String">临床试验查询结果列表</Data></Cell></Row>
   <Row>
    <Cell><Data ss:Type="String">序号</Data></Cell>
    <Cell><Data ss:Type="String">登记号</Data></Cell>
    <Cell><Data ss:Type="String">试验状态</Data></Cell>
    <Cell><Data ss:Type="String">药物名称</Data></Cell>
    <Cell><Data ss:Type="String">适应症</Data></Cell>
    <Cell><Data ss:Type="String">试验通俗题目</Data></Cell>
   </Row>
   <Row>
    <Cell><Data ss:Type="Number">1</Data></Cell>
    <Cell><Data ss:Type="String">CTR20263476</Data></Cell>
    <Cell><Data ss:Type="String">进行中&nbsp;尚未招募</Data></Cell>
    <Cell><Data ss:Type="String">CG001注射液</Data></Cell>
    <Cell><Data ss:Type="String">全身型重症肌无力（gMG）</Data></Cell>
    <Cell><Data ss:Type="String">CG001 注射液在 gMG 患者中的安全性研究</Data></Cell>
   </Row>
  </Table>
 </Worksheet>
</Workbook>
"""


def test_china_drug_trials_spreadsheetml_export_is_supported(tmp_path):
    """平台「下载 Excel」默认是 Excel 2003 XML，不是 OLE 或 HTML。"""
    source = tmp_path / "试验公示和查询.xls"
    source.write_text(SPREADSHEETML_EXPORT, encoding="utf-8")

    records = load_export_records(source)

    assert records == [{
        "registry_id": "CTR20263476",
        "title": "CG001 注射液在 gMG 患者中的安全性研究",
        "drug_name": "CG001注射液",
        "indication": "全身型重症肌无力（gMG）",
        "status": "进行中 尚未招募",
    }]


def test_china_drug_trials_phase_normalization_handles_platform_wording():
    """平台把分期写成「其它 其他说明:II/III期」，不能退化为未标注。"""
    assert normalize_cdt_phase("III期") == "3"
    assert normalize_cdt_phase("II/III期") == "2/3"
    assert normalize_cdt_phase("其它 其他说明:II/III期") == "2/3"
    assert normalize_cdt_phase("其它 其他说明:生物等效性试验") == "Unknown"
    assert normalize_cdt_phase("其他") == "Unknown"
    assert normalize_cdt_phase("") == "Unknown"


def test_compare_records_separates_baseline_enrichment_from_real_updates():
    """旧缓存缺少详情字段时，补全不算更新，真实字段变化仍要计入。"""
    old = [
        {"registry_id": "CTR1", "title": "A", "phase": "Unknown", "sponsor": "", "registered_date": "", "status": "RECRUITING"},
        {"registry_id": "CTR2", "title": "B", "phase": "3", "sponsor": "S", "registered_date": "2026-01-01", "status": "COMPLETED"},
    ]
    new = [
        {"registry_id": "CTR1", "title": "A", "phase": "2", "sponsor": "S1", "registered_date": "2026-02-02", "status": "RECRUITING"},
        {"registry_id": "CTR2", "title": "B", "phase": "3", "sponsor": "S", "registered_date": "2026-01-01", "status": "TERMINATED"},
    ]

    changes = compare_records(old, new)

    assert changes["added_count"] == 0
    assert changes["updated_count"] == 1
    assert changes["enriched_count"] == 1
    assert changes["updated"][0]["registry_id"] == "CTR2"
    assert set(changes["updated"][0]["changes"]) == {"status"}
    assert changes["enriched"][0]["registry_id"] == "CTR1"
    assert set(changes["enriched"][0]["filled"]) == {"phase", "sponsor", "registered_date"}


def test_cde_live_crawl_records_can_update_cache_without_export_file(tmp_path):
    """实时抓取结果可直接进入导入器，不再依赖人工下载文件。"""
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "source": "ChinaDrugTrials.org.cn",
        "mode": "cache",
        "records": [{
            "registry_id": "CTR20260001",
            "title": "旧标题",
            "indication": "重症肌无力",
            "status": "NOT_YET_RECRUITING",
        }],
    }), encoding="utf-8")

    payload, changes = import_china_drug_trials_exports(
        cache,
        records=[{
            "registry_id": "CTR20260001",
            "title": "新标题",
            "drug_name": "药物A",
            "indication": "重症肌无力",
            "status": "进行中 招募中",
            "phase": "其它 其他说明:II/III期",
        }],
        changes_path=tmp_path / "changes.json",
        mode="live_crawl",
        now=datetime(2026, 10, 24, tzinfo=timezone.utc),
    )

    assert payload["mode"] == "live_crawl"
    assert payload["total"] == 1
    assert payload["records"][0]["status"] == "RECRUITING"
    assert payload["records"][0]["phase"] == "2/3"
    assert changes["updated_count"] == 1
