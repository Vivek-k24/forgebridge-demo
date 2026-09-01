from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET
import zipfile

WORKBOOK = (
    pathlib.Path(__file__).resolve().parents[1] / "data" / "Selected_Asian_Brands_1996_2000.xlsx"
)
XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
EXPECTED_HEADERS = (
    "Year",
    "Make",
    "Model",
    "Trim",
    "Engine Specs",
    "Transmission Specs",
)


def _cell_text(cell: ET.Element) -> str:
    if cell.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//x:t", XML_NS)).strip()
    value = cell.find("x:v", XML_NS)
    return (value.text if value is not None else "").strip()


def _rows() -> list[tuple[str, ...]]:
    with zipfile.ZipFile(WORKBOOK) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    rows: list[tuple[str, ...]] = []
    for row in root.findall(".//x:sheetData/x:row", XML_NS):
        cells = row.findall("x:c", XML_NS)
        rows.append(tuple(_cell_text(cell) for cell in cells))
    return rows


def test_selected_asian_workbook_is_packaged_with_expected_shape() -> None:
    assert WORKBOOK.is_file()
    rows = _rows()
    assert rows[0] == EXPECTED_HEADERS
    assert len(rows[1:]) == 363
    assert len(set(rows[1:])) == 363

    makes = {row[1] for row in rows[1:]}
    assert makes == {"Acura", "Honda", "Lexus", "Subaru", "Toyota"}

    year_make_model_trim = {(row[0], row[1], row[2], row[3]) for row in rows[1:]}
    assert len(year_make_model_trim) == 225
