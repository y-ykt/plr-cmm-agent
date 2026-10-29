"""Notes validation and the reading tools of the server (fabricated text files only)."""
import importlib
from pathlib import Path
import json
import os

from plr_cmm_mcp.notes import MAX_NOTES_PER_FILE, validate_notes


def good_notes(**over):
    obj = {"experiment": "099", "file": "001_計画.docx.txt", "kind": "計画",
           "notes": [{"topic": "同意の取り方", "fact": "包括同意を示した。", "quote": "包括同意を示す"}]}
    obj.update(over)
    return obj


def test_validate_notes_accepts_good():
    assert validate_notes(good_notes()) == []
    assert validate_notes(good_notes(notes=[])) == []
    # English topics (current instructions) and Japanese topics (earlier notes) are both accepted
    en = [{"topic": "Consent method", "fact": "Broad consent was offered.", "quote": "包括同意を示す"}]
    assert validate_notes(good_notes(notes=en)) == []
    from plr_cmm_mcp.notes import TOPICS, TOPICS_JA, topic_en
    assert sorted(TOPICS_JA.values()) == sorted(TOPICS) and len(TOPICS) == 9
    assert topic_en("同意の取り方") == "Consent method" and topic_en("Other") == "Other"
    # the reading instructions list the same topics as config.yaml
    prompts = Path(__file__).resolve().parent.parent / "agents" / "prompts"
    reader = prompts.joinpath("reader.md").read_text(encoding="utf-8")
    assert '"topic": "' + " | ".join(TOPICS) + '"' in reader
    assert "`topic` is one of: " + ", ".join(TOPICS) in prompts.joinpath("ingest.md").read_text(encoding="utf-8")


def test_validate_notes_rejects_bad():
    assert validate_notes(good_notes(experiment="99")) == []            # any plain folder name is an identifier
    assert validate_notes(good_notes(experiment="口座開設の試行")) == []
    for bad in ("../x", "a/b", "top", "", ".h"):
        assert any("study identifier" in e for e in validate_notes(good_notes(experiment=bad)))
    assert any("file" in e for e in validate_notes(good_notes(file="../x.txt")))
    assert any("unknown topic" in e for e in validate_notes(
        good_notes(notes=[{"topic": "感想", "fact": "a", "quote": "b"}])))
    assert any("longer than" in e for e in validate_notes(
        good_notes(notes=[{"topic": "その他", "fact": "a", "quote": "x" * 201}])))
    assert any("personal-data" in e for e in validate_notes(
        good_notes(notes=[{"topic": "その他", "fact": "a", "quote": "連絡は a@b.jp まで"}])))
    many = [{"topic": "その他", "fact": "a", "quote": "b"}] * (MAX_NOTES_PER_FILE + 1)
    assert any("more than" in e for e in validate_notes(good_notes(notes=many)))


def load_server(tmp_path):
    os.environ["PLR_CMM_RUN"] = str(tmp_path / "run")
    os.environ["PLR_CMM_WORK"] = str(tmp_path / "work")
    os.environ["PLR_CMM_CONDITION"] = "full"
    import plr_cmm_mcp.server as s
    return importlib.reload(s)


def test_reading_tools(tmp_path):
    s = load_server(tmp_path)
    d = tmp_path / "work" / "text" / "099"; d.mkdir(parents=True)
    (d / "001_計画.docx.txt").write_text("計画の本文。包括同意を示す。", encoding="utf-8")
    (d / "002_長い.pptx.txt").write_text("あ" * (s.TEXT_CHUNK_CHARS + 10), encoding="utf-8")
    assert s.list_texts("098") == []
    files = s.list_texts("099")
    assert [f["file"] for f in files] == ["001_計画.docx.txt", "002_長い.pptx.txt"]
    assert files[0]["notes_done"] is False
    t = s.get_text("099", "001_計画.docx.txt")
    assert "包括同意を示す" in t and "continued" not in t
    t2 = s.get_text("099", "002_長い.pptx.txt")
    assert "[continued: offset=%d]" % s.TEXT_CHUNK_CHARS in t2
    assert "continued" not in s.get_text("099", "002_長い.pptx.txt", offset=s.TEXT_CHUNK_CHARS)
    assert s.get_text("099", "../x.txt").startswith("rejected")
    assert s.get_text("099", "nope.txt").startswith("rejected")
    # path fragments are refused before any file access, in every tool that takes an experiment id
    for bad in ("../099", "099/..", "", "../../etc", "top", ".h"):
        assert s.get_text(bad, "001_計画.docx.txt").startswith("rejected")
        assert s.get_notes(bad).startswith("rejected")
        assert s.render_judgment(bad).startswith("rejected")
        assert s.list_texts(bad) == []
        assert s.get_premise(bad)["level"] == "none"
    (tmp_path / "work" / "text" / "outside.txt").write_text("x", encoding="utf-8")
    assert s.get_text("099", "../outside.txt").startswith("rejected")
    assert s.get_text("099", "sub/x.txt").startswith("rejected")
    assert s.get_text("099", ".hidden.txt").startswith("rejected")
    # submit: unknown file is rejected, good notes are saved and seen by get_notes
    assert s.submit_notes(good_notes(file="nope.txt")).startswith("rejected")
    r = s.submit_notes(good_notes())
    assert r.startswith("accepted: experiment 099, 001_計画.docx.txt, 1 notes")
    saved = json.loads((tmp_path / "run" / "notes" / "099" / "001_計画.docx.json").read_text(encoding="utf-8"))
    assert saved["file"] == "001_計画.docx.txt" and "experiment" not in saved
    assert s.list_texts("099")[0]["notes_done"] is True
    assert "Quote: 包括同意を示す" in s.get_notes("099")
    assert s.list_experiments() == ["099"]
    assert "notes" in s.notes_schema()["properties"]


def test_render_judgment_and_ingest_prompt(tmp_path):
    s = load_server(tmp_path)
    assert "no accepted judgment" in s.render_judgment("099")
    from tests.test_judge import full_judgment
    j = full_judgment("099", **{"C2-2": "achieved", "C2-1": "partial"})
    j["variables"] = ["Trustee", "Purpose"]
    assert s.submit_judgment(j).startswith("accepted")
    md = s.render_judgment("099")
    assert "| 099 | (name) | (period) | (C2-1), C2-2 | Trustee/Purpose |" in md
    # with an overview sheet (record template), name and period are taken from it
    d = tmp_path / "work" / "text" / "099"; d.mkdir(parents=True, exist_ok=True)
    (d / "001_000_概要.md.txt").write_text("番号：099\n\n名前：試しの実験\n\n時期：2026-01〜2026-02\n\n## 目的とデータ\n", encoding="utf-8")
    assert "| 099 | 試しの実験 | 2026-01〜2026-02 | (C2-1), C2-2 |" in s.render_judgment("099")
    assert "level taken as premise: none (all 16 capabilities judged from the records)" in s.render_judgment("099")
    assert "### C2-2 (achieved)" in md and "### C2-1 (partial)" in md
    assert "C1-1" not in md.split("## Evidence by capability")[1]
    p = s.ingest_experiment("099")
    assert "inventory_experiment" in p and "submit_notes" in p and "You do not judge" in p
    assert "## Rules" in p and "At most 12 notes" in p
    assert p.rstrip().endswith("Study to ingest: 099")
    assert s.judge_experiment("099").rstrip().endswith("Study to judge: 099")
    assert "render_judgment" in s.judge_experiment("099") and '"accepted"' not in s.judge_experiment("099")
    r = s.report_experiment("099")
    assert "render_judgment" in r and r.rstrip().endswith("Study to report: 099")
    assert "/mcp__plr-cmm__judge_experiment" in s.ingest_experiment("099")


def test_premise_from_overview(tmp_path):
    s = load_server(tmp_path)
    from tests.test_judge import full_judgment
    assert s.get_premise("099")["level"] == "none" and s.get_premise("099")["premise"] == []
    d = tmp_path / "work" / "text" / "099"; d.mkdir(parents=True)
    (d / "001_000_overview.md.txt").write_text(
        "Number: 099\n\nOrganization: Test org\n\nLevel: L3\n\nName: Test study\n\nPeriod: 2026-03\n", encoding="utf-8")
    pr = s.get_premise("099")
    assert pr["organization"] == "Test org" and pr["level"] == "L3"
    (d / "001_000_overview.md.txt").unlink()
    (d / "001_000_概要.md.txt").write_text(
        "番号：099\n\n組織：試しの組織\n\nレベル：L3\n\n名前：試しの実験\n\n時期：2026-03\n", encoding="utf-8")
    pr = s.get_premise("099")
    assert pr["organization"] == "試しの組織" and pr["level"] == "L3"       # Japanese field names still work
    assert pr["premise"] == ["C1-1", "C1-2", "C1-3", "C2-1", "C2-2", "C2-3", "C3-1", "C3-2", "C3-3"]
    assert "premises" in pr["note"]
    # a capability below the level judged from the records is rejected; premise status is required
    bad = full_judgment("099", **{"C2-3": "partial", "C4-1": "achieved"})
    r = s.submit_judgment(bad)
    assert r.startswith("rejected") and "C2-3" in r and "must be premise" in r
    good = full_judgment("099", **{c: "premise" for c in pr["premise"]}, **{"C4-1": "achieved", "C5-1": "partial"})
    assert s.submit_judgment(good) == "accepted: experiment 099, shown 2 of 16 capabilities, 9 premise"
    md = s.render_judgment("099")
    assert "Organization: 試しの組織; level taken as premise: L3 (not judged from the records: C1-1, C1-2, C1-3, C2-1, C2-2, C2-3, C3-1, C3-2, C3-3)" in md
    assert "| 099 | 試しの実験 | 2026-03 | C4-1, (C5-1) | Trust |" in md
    assert "lists only the capabilities above the premise level" in md and "Table A-I" not in md
    assert "### C2-3" not in md
    # the placeholders of the template are not a level
    (d / "001_000_概要.md.txt").write_text("レベル：（L1〜L5）\n", encoding="utf-8")
    assert s.get_premise("099")["level"] == "none"
    (d / "001_000_概要.md.txt").write_text("Level: (L1 to L5, or none)\n", encoding="utf-8")
    assert s.get_premise("099")["level"] == "none"
