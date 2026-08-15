"""Tests for app.busy.xml_util against real captured BUSY XML fixtures.

Uses real data (tests/fixtures/real_xml_samples/, see its README for provenance) rather
than invented shapes — the discipline that caught both real bugs in the Node prototype
(BlockedMaster as text, undecoded numeric entities). Don't lose that discipline.
"""

from pathlib import Path

from app.busy.xml_util import decode_xml_entities, parse_element_xml, parse_rowset_xml

FIXTURES = Path(__file__).parent.parent / "fixtures" / "real_xml_samples"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_rowset_xml_real_tables() -> None:
    rows = parse_rowset_xml(_load("tables_rowset.xml"))
    table_names = {r["TABLE_NAME"] for r in rows}
    assert {"Master1", "Tran1", "Tran2"}.issubset(table_names)


def test_parse_rowset_xml_real_columns() -> None:
    rows = parse_rowset_xml(_load("columns_master1_rowset.xml"))
    column_names = {r["COLUMN_NAME"] for r in rows}
    assert {"Code", "MasterType", "Name", "Stamp"}.issubset(column_names)


def test_parse_rowset_xml_real_vchno_sample_needs_stripping() -> None:
    """Real VchNo values come back left-padded — CLAUDE.md §8's "VchNo is padded" gotcha."""
    rows = parse_rowset_xml(_load("vchno_sample_rowset.xml"))
    assert len(rows) == 300
    assert any(r["VchNo"] != r["VchNo"].strip() for r in rows)
    assert all(r["VchNo"].strip() for r in rows)


def test_parse_rowset_xml_decodes_numeric_entities_in_real_customer_name() -> None:
    """Regression for the real bug: &#x27;ENAIBE... only handling the 5 named entities
    missed numeric refs like &#x27;/&#39; (docs/reference/14-command-center.md)."""
    rows = parse_rowset_xml(_load("customers_with_entities_rowset.xml"))
    names = {r["Code"]: r["Name"] for r in rows}
    assert names["4021"] == "'ENAIBE L C (MRS)"
    assert names["4022"] == "O'Brien Chukwu"


def test_parse_rowset_xml_bit_columns_are_text_true_false() -> None:
    """Regression for the real bug: BlockedMaster/DeactiveMaster are 'True'/'False' text,
    not '1'/'0' — checking only '1' silently missed real blocked records."""
    rows = parse_rowset_xml(_load("customers_with_entities_rowset.xml"))
    blocked = {r["Code"]: r["BlockedMaster"] for r in rows}
    assert blocked["4021"] == "False"
    assert blocked["4023"] == "True"


def test_parse_element_xml_real_item_master() -> None:
    result = parse_element_xml(_load("item_master_xml.xml"))
    assert isinstance(result, dict)
    item = result["Item"]
    assert isinstance(item, dict)
    assert item["Name"] == "Cable-infinix Micro"
    assert item["SalePrice"] == "1000"
    assert item["MainUnit"] == "Pcs."
    assert item["ParentGroup"] == "General"


def test_parse_element_xml_decodes_named_entities_in_real_item() -> None:
    result = parse_element_xml(_load("item_master_xml.xml"))
    assert isinstance(result, dict)
    item = result["Item"]
    assert isinstance(item, dict)
    assert item["TaxCategory"] == "<<---None--->>"


def test_decode_xml_entities_numeric_and_named() -> None:
    assert decode_xml_entities("&#x27;ENAIBE L C (MRS)") == "'ENAIBE L C (MRS)"
    assert decode_xml_entities("&#39;quoted&#39;") == "'quoted'"
    assert decode_xml_entities("Tom &amp; Jerry") == "Tom & Jerry"
    assert decode_xml_entities("&lt;tag&gt;") == "<tag>"


def test_parse_rowset_xml_empty_when_no_data_element() -> None:
    assert parse_rowset_xml("<xml></xml>") == []
