"""Extract text from the records listed in the inventory (docx, pptx, xlsx, pdf, txt, md).

Output goes under work_dir (git-ignored):
  work/text/<experiment>/<nn>_<basename>.txt   one file per record
  work/text/<experiment>.md                    all records of an experiment, with headings
  work/extract_log.json                        what was read, skipped, flagged, truncated

E-mail addresses and phone numbers in the text are replaced by MASK before the
text is kept (README, Input); the file name and the number of replacements are logged.
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass, asdict, field
from pathlib import Path

from .inventory import Inventory, Entry, nfc

MAX_CHARS_PER_FILE = 120_000
MAX_CELLS_PER_SHEET = 20_000

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\d-])0\d{1,4}-\d{1,4}-\d{3,4}(?![\d-])|(?<!\d)0[789]0\d{8}(?!\d)")


MASK = "（略）"


def scan_personal(text: str) -> list[str]:
    """Return the kinds of personal-data patterns found (empty if none)."""
    kinds = []
    if EMAIL_RE.search(text):
        kinds.append("email")
    if PHONE_RE.search(text):
        kinds.append("phone")
    return kinds


def mask_personal(text: str) -> tuple[str, dict[str, int]]:
    """Replace e-mail addresses and phone numbers with MASK; return counts by kind."""
    counts: dict[str, int] = {}
    text, n = EMAIL_RE.subn(MASK, text)
    if n:
        counts["email"] = n
    text, n = PHONE_RE.subn(MASK, text)
    if n:
        counts["phone"] = n
    return text, counts


# ---------------------------------------------------------------- readers

def read_txt(path: str | os.PathLike) -> str:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp932", "euc_jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_docx(path: str) -> str:
    """Take every w:t of document.xml, including tracked insertions and
    excluding tracked deletions (python-docx's paragraph.text drops w:ins)."""
    import xml.etree.ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out: list[str] = []

    def walk(el, parts):
        for ch in el:
            if ch.tag == ns + "del":
                continue
            if ch.tag == ns + "t" and ch.text:
                parts.append(ch.text)
            elif ch.tag == ns + "tab":
                parts.append("\t")
            else:
                walk(ch, parts)

    for p in root.iter(ns + "p"):
        parts: list[str] = []
        walk(p, parts)
        line = "".join(parts)
        if line.strip():
            out.append(line)
    return "\n".join(out)


def read_pptx(path: str) -> str:
    from pptx import Presentation
    prs = Presentation(path)
    out = []
    for i, slide in enumerate(prs.slides, 1):
        out.append(f"--- slide {i} ---")
        for shape in slide.shapes:
            _shape_text(shape, out)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            nt = slide.notes_slide.notes_text_frame.text.strip()
            if nt:
                out.append("[notes] " + nt)
    return "\n".join(out)


def _shape_text(shape, out: list[str]) -> None:
    if shape.shape_type == 6 and hasattr(shape, "shapes"):  # group
        for s in shape.shapes:
            _shape_text(s, out)
        return
    if shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            t = "".join(r.text for r in para.runs).strip()
            if t:
                out.append(t)
    if getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                out.append(" | ".join(cells))


def read_xlsx(path: str) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"--- sheet {ws.title} ---")
        n = 0
        for row in ws.iter_rows(values_only=True):
            cells = ["" if v is None else str(v).strip() for v in row]
            if any(cells):
                out.append(" | ".join(cells).rstrip(" |"))
            n += len(cells)
            if n > MAX_CELLS_PER_SHEET:
                out.append("[sheet truncated]")
                break
    wb.close()
    return "\n".join(out)


def read_pdf(path: str | os.PathLike) -> str:
    import fitz
    out = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, 1):
            out.append(f"--- page {i} ---")
            out.append(page.get_text())
    return "\n".join(out)


READERS = {".txt": read_txt, ".md": read_txt, ".docx": read_docx, ".pptx": read_pptx,
           ".xlsx": read_xlsx, ".pdf": read_pdf}


def read_any(path: str | os.PathLike) -> str:
    ext = Path(path).suffix.lower()
    if ext not in READERS:
        raise ValueError("unsupported extension: " + ext)
    return READERS[ext](path)


# ---------------------------------------------------------------- driver

@dataclass
class ExtractRecord:
    experiment: str
    relpath: str
    status: str            # "ok", "masked", "error", "empty"
    chars: int = 0
    truncated: bool = False
    detail: str = ""       # mask counts or error message (never the text itself)
    out_file: str = ""


@dataclass
class ExtractLog:
    records: list[ExtractRecord] = field(default_factory=list)

    def summary(self) -> dict:
        s: dict[str, int] = {}
        for r in self.records:
            s[r.status] = s.get(r.status, 0) + 1
        return s


def safe_name(rel: str) -> str:
    base = os.path.basename(rel)
    return re.sub(r"[^\w.\-（）()]+", "_", base)[:80]


def extract_entry(e: Entry, out_dir: Path, idx: int) -> tuple[ExtractRecord, str | None]:
    rec = ExtractRecord(e.experiment, e.relpath, "ok")
    try:
        text = read_any(e.path)
    except Exception as ex:  # noqa: BLE001
        rec.status, rec.detail = "error", f"{type(ex).__name__}: {str(ex)[:120]}"
        return rec, None
    text = nfc(text)
    if not text.strip():
        rec.status = "empty"
        return rec, None
    text, masked = mask_personal(text)
    if masked:
        rec.status = "masked"
        rec.detail = ",".join(f"{k}:{v}" for k, v in masked.items())
    left = scan_personal(text)
    if left:   # the masking above must leave none of these; never trust it silently
        raise RuntimeError(f"unmasked personal-data pattern ({', '.join(left)}) in {e.relpath}")
    if len(text) > MAX_CHARS_PER_FILE:
        text = text[:MAX_CHARS_PER_FILE] + "\n[truncated]"
        rec.truncated = True
    rec.chars = len(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{idx:03d}_{safe_name(e.relpath)}.txt"
    out.write_text(text, encoding="utf-8")
    rec.out_file = str(out)
    return rec, text


def extract_inventory(inv: Inventory, work_dir: str | os.PathLike,
                      log_name: str = "extract_log.json") -> ExtractLog:
    work = Path(work_dir)
    log = ExtractLog()
    by_exp: dict[str, list[tuple[Entry, str]]] = {}
    counters: dict[str, int] = {}
    for e in inv.used:
        counters[e.experiment] = counters.get(e.experiment, 0) + 1
        rec, text = extract_entry(e, work / "text" / e.experiment, counters[e.experiment])
        log.records.append(rec)
        if text is not None:
            by_exp.setdefault(e.experiment, []).append((e, text))
    for exp, items in by_exp.items():
        md = [f"# Records of study {exp} ({len(items)} files)", ""]
        for e, text in items:
            md.append(f"## File: {e.relpath}")
            md.append("")
            md.append(text)
            md.append("")
        (work / "text").mkdir(parents=True, exist_ok=True)
        (work / "text" / f"{exp}.md").write_text("\n".join(md), encoding="utf-8")
    work.mkdir(parents=True, exist_ok=True)
    with open(work / log_name, "w", encoding="utf-8") as f:
        json.dump({"summary": log.summary(), "records": [asdict(r) for r in log.records]},
                  f, ensure_ascii=False, indent=1)
    return log


def main(argv: list[str] | None = None) -> int:
    import argparse
    from .inventory import Rules, build_inventory
    ap = argparse.ArgumentParser(description="Extract text from the inventoried records.")
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args(argv)
    rules = Rules.load(a.config)
    inv = build_inventory(rules)
    log = extract_inventory(inv, rules.work_dir)
    print(log.summary())
    for r in log.records:
        if r.status in ("masked", "error"):
            print(f"  {r.status:8s} {r.experiment} {r.relpath}  {r.detail}")
    total = sum(r.chars for r in log.records)
    print(f"chars total {total:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
