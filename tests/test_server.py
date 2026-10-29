"""Server tool functions, called directly (no transport)."""
import importlib
import json
import os


def load_server(tmp_path, condition):
    os.environ["PLR_CMM_RUN"] = str(tmp_path)
    os.environ["PLR_CMM_CONDITION"] = condition
    import plr_cmm_mcp.server as s
    return importlib.reload(s)


def test_usage_instructions_are_handed_to_the_client(tmp_path):
    s = load_server(tmp_path, "full")
    for word in ("ingest_experiment", "judge_experiment", "render_judgment", "submit_judgment", "(omitted)"):
        assert word in s.INSTRUCTIONS
    assert getattr(s.mcp, "instructions", s.INSTRUCTIONS) == s.INSTRUCTIONS


def test_full_condition_exposes_definitions(tmp_path):
    s = load_server(tmp_path, "full")
    assert "C5-4" in s.get_capabilities() and "Criterion in the paper" in s.get_capabilities()
    assert "## Steps" in s.get_procedure() and "decision 2" in s.get_procedure()
    assert "Trust Scaling" in s.get_levels()
    assert s.list_experiments() == []


def test_names_condition_hides_definitions(tmp_path):
    s = load_server(tmp_path, "names")
    caps = s.get_capabilities()
    assert "- C1-1 Clarify research objectives and data requirements" in caps
    assert caps.count("- C") == 16 and "granularity" not in caps
    assert "no procedure under this condition" in s.get_procedure()
    assert "not given under this condition" in s.get_levels()


def test_notes_and_submit(tmp_path):
    s = load_server(tmp_path, "full")
    d = tmp_path / "notes" / "003"; d.mkdir(parents=True)
    (d / "001_a.json").write_text(json.dumps({"file": "a.docx", "kind": "計画",
        "notes": [{"topic": "同意の取り方", "fact": "包括同意を示した", "quote": "包括同意"}]},
        ensure_ascii=False), encoding="utf-8")
    (tmp_path / "notes" / "top").mkdir()                   # notes of the overview materials: not a study
    assert s.list_experiments() == ["003"]
    t = s.get_notes("003")
    assert "## File: a.docx (計画)" in t and "Quote: 包括同意" in t
    assert "- [Consent method] 包括同意を示した" in t      # a Japanese topic of earlier notes is shown in English
    from tests.test_judge import full_judgment
    bad = full_judgment("003", **{"C2-2": "achieved"}); bad["capabilities"].pop()
    assert s.submit_judgment(bad).startswith("rejected")
    good = full_judgment("003", **{"C2-2": "achieved"})
    assert s.submit_judgment(good).startswith("accepted: experiment 003, shown 1 of 16")
    assert (tmp_path / "judgments" / "003.json").exists()
    assert "reference" not in [t for t in dir(s) if t.startswith("get_")]


def test_summary_section(tmp_path):
    from plr_cmm_mcp.server import summary_section
    top = tmp_path / "text" / "top"; top.mkdir(parents=True)
    (top / "002_実験一覧.xlsx.txt").write_text(
        "--- sheet 一覧表 ---\n001 | PLR | カタログ | a\n005 | PLR | カテゴリB | b\n"
        "--- sheet 001 ---\nx | y\n--- sheet 005 ---\n行の例 1\n行 2\n--- sheet 006 ---\nz\n",
        encoding="utf-8")
    t = summary_section("005", tmp_path)
    assert t == "005 | PLR | カテゴリB | b"
    assert summary_section("007", tmp_path) == ""
