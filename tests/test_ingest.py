"""inventory_experiment and extract_experiment on a fabricated records folder (its name has no number)."""
import importlib
import os
from pathlib import Path

import yaml

from tests.test_extract import make_docx, make_xlsx
from tests.test_inventory import CONFIG, touch

EXP_DIR = "実験別フォルダ"
STUDY = "口座開設の試行"          # the identifier is the folder name; a number is not needed


def make_input(tmp_path: Path) -> Path:
    """Write a config.yaml whose input_root is a fabricated tree; return the config path."""
    raw = yaml.safe_load(open(CONFIG, encoding="utf-8"))
    raw["input_root"] = str(tmp_path / "input")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    e = tmp_path / "input" / EXP_DIR / STUDY
    (e / "1．計画").mkdir(parents=True)
    (e / "2. データ").mkdir(parents=True)
    make_docx(e / "1．計画" / "計画.docx")
    make_xlsx(e / "2. データ" / "カタログ.xlsx")
    touch(e / "1．計画" / "写真.jpg")
    touch(e / "3. 個人別" / "説明.pptx")
    touch(e / "4. 結果" / "4-3 補足" / "参加者一覧.xlsx")
    touch(tmp_path / "input" / EXP_DIR / "参考" / "023_x" / "a.docx")
    return cfg


def load_server(tmp_path):
    os.environ["PLR_CMM_RUN"] = str(tmp_path / "run")
    os.environ["PLR_CMM_WORK"] = str(tmp_path / "work")
    os.environ["PLR_CMM_CONFIG"] = str(make_input(tmp_path))
    os.environ["PLR_CMM_CONDITION"] = "full"
    import plr_cmm_mcp.server as s
    return importlib.reload(s)


def test_inventory_experiment(tmp_path):
    s = load_server(tmp_path)
    r = s.inventory_experiment(STUDY)
    assert r["experiment"] == STUDY and r["folder"].endswith(STUDY)
    assert r["used"] == ["1．計画/計画.docx", "2. データ/カタログ.xlsx"]
    reasons = {x["file"]: x["reason"] for x in r["excluded"]}
    assert reasons["1．計画/写真.jpg"] == "extension: .jpg"
    assert reasons["4. 結果/4-3 補足/参加者一覧.xlsx"] == "name contains: 参加者"
    assert reasons["3. 個人別/説明.pptx"].startswith("folder excluded")
    assert r["counts"] == {"used": 2, "excluded": 3}
    # the same folder by its absolute path, by a path relative to the experiments folder and to input_root
    assert s.inventory_experiment(r["folder"])["used"] == r["used"]
    assert s.inventory_experiment(f"./{STUDY}")["experiment"] == STUDY
    assert s.inventory_experiment(f"{EXP_DIR}/{STUDY}")["experiment"] == STUDY
    # the error cases
    assert "error" in s.inventory_experiment("参考/023_x")           # below an excluded folder
    assert "error" in s.inventory_experiment("022")                 # no such folder
    assert "error" in s.inventory_experiment(str(tmp_path))         # outside input_root
    assert "error" in s.inventory_experiment(str(tmp_path / "input"))        # input_root itself
    assert "error" in s.inventory_experiment(str(tmp_path / "input" / EXP_DIR))   # the experiments folder itself
    assert "error" in s.inventory_experiment(".") and "error" in s.inventory_experiment("..")
    assert "error" in s.inventory_experiment("") and "error" in s.inventory_experiment("../input")


def test_extract_experiment_then_read(tmp_path):
    s = load_server(tmp_path)
    r = s.extract_experiment(STUDY)
    assert r["experiment"] == STUDY and r["summary"] == {"ok": 2}
    names = [f["file"] for f in r["files"]]
    assert names == ["001_計画.docx.txt", "002_カタログ.xlsx.txt"]
    assert all("本文" not in str(f) for f in r["files"])   # no text in the result
    out = tmp_path / "work" / "text" / STUDY
    assert sorted(p.name for p in out.glob("*.txt")) == names
    assert (tmp_path / "work" / f"extract_log_{STUDY}.json").exists()
    assert not (tmp_path / "work" / "extract_log.json").exists()
    # the extracted text is then readable through the reading tools
    assert [f["file"] for f in s.list_texts(STUDY)] == names
    assert "口座の開設" in s.get_text(STUDY, "001_計画.docx.txt")
    assert "包括同意" in s.get_text(STUDY, "002_カタログ.xlsx.txt")
    # notes and a judgment are stored under the same identifier
    notes = {"experiment": STUDY, "file": names[0], "kind": "plan",
             "notes": [{"topic": "Purpose and data", "fact": "The purpose is account opening.", "quote": "口座の開設"}]}
    assert s.submit_notes(notes).startswith("accepted")
    assert s.list_experiments() == [STUDY]
    assert "Quote: 口座の開設" in s.get_notes(STUDY)
    from plr_cmm_mcp.judge import CAPABILITIES
    caps = [{"capability": c, "status": "achieved" if c == "C1-1" else "none",
             "evidence": [{"file": names[0], "quote": "口座の開設"}] if c == "C1-1" else [], "reason": "r"}
            for c in CAPABILITIES]
    assert s.submit_judgment({"experiment": STUDY, "capabilities": caps, "variables": ["Purpose"]}).startswith("accepted")
    assert (tmp_path / "run" / "judgments" / f"{STUDY}.json").exists()
    assert f"| {STUDY} | (name) | (period) | C1-1 | Purpose |" in s.render_judgment(STUDY)
