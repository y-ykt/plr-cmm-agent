"""Tests for the inventory rules, using a synthetic folder tree only."""
import unicodedata
from pathlib import Path

import yaml

import pytest

from plr_cmm_mcp.ids import check_study_id, is_study_id
from plr_cmm_mcp.inventory import Rules, build_inventory, classify, experiment_id, find_experiment_dir, nfc

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config.yaml"


def make_rules(tmp_path: Path) -> Rules:
    raw = yaml.safe_load(open(CONFIG, encoding="utf-8"))
    raw["input_root"] = str(tmp_path)
    cfg = tmp_path / "cfg" / "config.yaml"
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return Rules.load(cfg)


def touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def build_tree(tmp_path: Path) -> None:
    exp = tmp_path / "実験別フォルダ"
    e1 = exp / "001_テスト実験"
    touch(e1 / "1．計画" / "計画.docx")
    touch(e1 / "1．計画" / "当日記録" / "記録.docx")
    touch(e1 / "1．計画" / "写真.jpg")
    # NFD-named folder, as macOS stores it
    nfd = unicodedata.normalize("NFD", "2. データ")
    touch(e1 / nfd / "カタログ.xlsx")
    touch(e1 / "3. 個人別" / "3-1 個人" / "説明.pptx")
    touch(e1 / "3. 個人別" / "3-2 提供者" / "計画書.docx")
    touch(e1 / "4. 結果" / "4-1 成果" / "成果.pptx")
    touch(e1 / "4. 結果" / "4-2 調査票" / "回答.xlsx")
    touch(e1 / "4. 結果" / "4-3 補足" / "参加者一覧.xlsx")
    touch(e1 / "予行" / "data.xlsx")
    touch(exp / "旧" / "古い.xlsx")
    touch(exp / "参考" / "022_x" / "a.docx")
    touch(tmp_path / "2026_0101 実験一覧 .xlsx")
    touch(tmp_path / "2026_0101_実験俯瞰図ver1.pptx")
    touch(tmp_path / "2026_0101_実験俯瞰図ver2.pptx")
    touch(tmp_path / "旧" / "実験一覧20251201.xlsx")


def test_classify_rules(tmp_path):
    rules = make_rules(tmp_path)
    assert classify("1．計画/計画.docx", rules) == (True, "document in a used folder")
    assert classify("3. 個人別/3-2 提供者/計画書.docx", rules)[0] is False
    assert classify("4. 結果/4-2 調査票/回答.xlsx", rules)[0] is False
    assert classify("4. 結果/4-3 補足/参加者一覧.xlsx", rules) == (False, "name contains: 参加者")
    assert classify("1．計画/写真.jpg", rules) == (False, "extension: .jpg")
    assert classify("予行/data.xlsx", rules)[0] is False
    assert classify("5. 不明/x.docx", rules)[0] is False
    assert classify("1．計画/当日/2026_0101_ログイン履歴_r1.xlsx", rules) == (False, "name contains: ログイン履歴")
    assert classify("4. 結果/4-1 成果/集計表2026_0101.xlsx", rules)[0] is True
    assert classify("4. 結果/4-1 成果/受付名簿.xlsx", rules)[0] is False
    assert classify("1．計画/案内文_r1.txt", rules)[0] is True


def test_nfd_names_match(tmp_path):
    rules = make_rules(tmp_path)
    nfd = unicodedata.normalize("NFD", "2. データ/カタログ.xlsx")
    assert classify(nfd, rules)[0] is True


def test_build_inventory_counts(tmp_path):
    build_tree(tmp_path)
    rules = make_rules(tmp_path)
    inv = build_inventory(rules)
    used = sorted(e.relpath for e in inv.used)
    assert used == sorted([
        "1．計画/計画.docx",
        "2. データ/カタログ.xlsx",
        "4. 結果/4-1 成果/成果.pptx",
        "2026_0101 実験一覧 .xlsx",
        "2026_0101_実験俯瞰図ver2.pptx",
    ])
    assert all(nfc(p) == p for p in used)
    assert inv.counts_by_experiment() == {"001_テスト実験": 3, "top": 2}
    reasons = inv.counts_by_reason()
    assert reasons["folder excluded: 3. 個人別 (participant-level records)"] == 2
    assert reasons["experiment dir excluded: 旧"] == 2
    assert len(inv.entries) == 16


def test_used_names_are_names_only(tmp_path):
    build_tree(tmp_path)
    inv = build_inventory(make_rules(tmp_path))
    names = inv.used_names()
    assert len(names) == 5
    assert all("\t" in n for n in names)


def test_experiment_id_is_the_folder_name():
    assert experiment_id("014_実験Ａ２") == "014_実験Ａ２"
    assert experiment_id("口座開設の試行") == "口座開設の試行"
    assert experiment_id(unicodedata.normalize("NFD", "019_実験B PJ")) == "019_実験B PJ"


def test_study_id_rule():
    for ok in ("001", "014_実験Ａ２", "口座開設の試行", "Account opening 2026", "a.b"):
        assert is_study_id(ok) and check_study_id(ok) == ok
    assert check_study_id(unicodedata.normalize("NFD", "口座開設の試行")) == "口座開設の試行"
    for bad in ("", " ", ".", "..", ".hidden", "a/b", "a\\b", "top", " x", "x\n", None, 3, "x" * 201):
        assert not is_study_id(bad)
        with pytest.raises(ValueError):
            check_study_id(bad)


def test_find_experiment_dir(tmp_path):
    build_tree(tmp_path)
    rules = make_rules(tmp_path)
    exp = tmp_path / "実験別フォルダ"
    (exp / "口座開設の試行" / "1．計画").mkdir(parents=True)
    (exp / "参考" / "022_x").mkdir(parents=True, exist_ok=True)   # build_tree already put a file there
    # by name, by absolute path, by paths relative to the experiments folder and to input_root; NFD input
    for given in ("001_テスト実験", str(exp / "001_テスト実験"), "./001_テスト実験", "実験別フォルダ/001_テスト実験",
                  unicodedata.normalize("NFD", "001_テスト実験")):
        eid, dp = find_experiment_dir(rules, given)
        assert eid == "001_テスト実験" and dp == (exp / "001_テスト実験").resolve()
    assert find_experiment_dir(rules, "口座開設の試行")[0] == "口座開設の試行"
    # refused: unknown, excluded (the folder and anything below it), outside, the roots themselves, fragments
    for bad in ("001", "no_such", "旧", "参考", "参考/022_x", str(exp / "参考" / "022_x"), "..", "../x",
                str(tmp_path), str(exp), ".", "", str(Path("/"))):
        with pytest.raises(ValueError):
            find_experiment_dir(rules, bad)
