"""Extraction tests on synthetic files created here (no real records)."""
from pathlib import Path

from plr_cmm_mcp.extract import (read_docx, read_pptx, read_xlsx, read_pdf, read_txt,
                                 scan_personal, mask_personal, extract_inventory)
from plr_cmm_mcp.inventory import Inventory, Entry


def make_docx(p: Path) -> None:
    import docx
    d = docx.Document()
    d.add_paragraph("実験の目的は口座の開設である。")
    d.add_paragraph("審査委員会が承認した。")
    d.save(p)


def make_pptx(p: Path) -> None:
    from pptx import Presentation
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "データカタログ"
    s.placeholders[1].text = "項目を定めた"
    prs.save(p)


def make_xlsx(p: Path) -> None:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "集計"
    ws.append(["項目", "件数"])
    ws.append(["包括同意", 10])
    wb.save(p)


def make_pdf(p: Path) -> None:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Consent withdrawn: 0")
    doc.save(p)


def test_readers(tmp_path):
    make_docx(tmp_path / "a.docx"); make_pptx(tmp_path / "b.pptx")
    make_xlsx(tmp_path / "c.xlsx"); make_pdf(tmp_path / "d.pdf")
    (tmp_path / "e.txt").write_text("メモ", encoding="utf-8")
    assert "口座の開設" in read_docx(str(tmp_path / "a.docx"))
    t = read_pptx(str(tmp_path / "b.pptx"))
    assert "データカタログ" in t and "slide 1" in t
    x = read_xlsx(str(tmp_path / "c.xlsx"))
    assert "包括同意 | 10" in x and "sheet 集計" in x
    assert "withdrawn" in read_pdf(str(tmp_path / "d.pdf"))
    assert read_txt(str(tmp_path / "e.txt")) == "メモ"


def test_txt_cp932(tmp_path):
    (tmp_path / "s.txt").write_bytes("日本語".encode("cp932"))
    assert read_txt(str(tmp_path / "s.txt")) == "日本語"


def test_unmasked_personal_data_is_an_error(monkeypatch, tmp_path):
    """If masking ever left a pattern behind, extraction must fail loudly (not an assert)."""
    import plr_cmm_mcp.extract as x
    from plr_cmm_mcp.inventory import Entry
    f = tmp_path / "a.txt"; f.write_text("mail a@b.jp", encoding="utf-8")
    monkeypatch.setattr(x, "mask_personal", lambda t: (t, {}))      # masking disabled on purpose
    import pytest
    with pytest.raises(RuntimeError, match="unmasked personal-data pattern"):
        x.extract_entry(Entry("099", str(f), "a.txt", True, "test"), tmp_path / "out", 1)


def test_scan_personal():
    assert scan_personal("連絡先 someone@example.com") == ["email"]
    assert scan_personal("TEL 06-1234-5678") == ["phone"]
    assert scan_personal("090-1234-5678 と a@b.jp") == ["email", "phone"]
    assert scan_personal("2026-01-01 の日程、件数 1,234") == []
    assert scan_personal("ID 2026-0101-01") == []


def test_mask_personal():
    t, c = mask_personal("担当 a@b.jp、TEL 06-1234-5678、予備 090-1234-5678")
    assert t == "担当 （略）、TEL （略）、予備 （略）"
    assert c == {"email": 1, "phone": 2}
    assert mask_personal("件数 1,234")[1] == {}


def test_extract_inventory_masks_and_writes(tmp_path):
    rec = tmp_path / "in"; rec.mkdir()
    make_docx(rec / "plan.docx")
    (rec / "contact.txt").write_text("担当 someone@example.com に連絡", encoding="utf-8")
    (rec / "empty.txt").write_text("   ", encoding="utf-8")
    inv = Inventory([
        Entry("001", str(rec / "plan.docx"), "1．計画/plan.docx", True, "document in a used folder"),
        Entry("001", str(rec / "contact.txt"), "1．計画/contact.txt", True, "document in a used folder"),
        Entry("001", str(rec / "empty.txt"), "1．計画/empty.txt", True, "document in a used folder"),
        Entry("001", str(rec / "x.jpg"), "1．計画/x.jpg", False, "extension: .jpg"),
    ])
    work = tmp_path / "work"
    log = extract_inventory(inv, work)
    assert log.summary() == {"ok": 1, "masked": 1, "empty": 1}
    masked = [r for r in log.records if r.status == "masked"][0]
    assert masked.detail == "email:1" and masked.out_file
    md = (work / "text" / "001.md").read_text(encoding="utf-8")
    assert "## File: 1．計画/plan.docx" in md and "口座の開設" in md
    assert "example.com" not in md and "担当 （略） に連絡" in md
    assert (work / "extract_log.json").exists()
