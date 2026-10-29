"""Tests for the judgment shape and its validation."""
import json

from plr_cmm_mcp.judge import CAPABILITIES, validate, parse, load_json_text


def full_judgment(exp="005", **statuses):
    caps = []
    for c in CAPABILITIES:
        st = statuses.get(c, "none")
        ev = [{"file": "1．計画/x.docx", "quote": "記録の文"}] if st != "none" else []
        caps.append({"capability": c, "status": st, "evidence": ev, "reason": "r"})
    return {"experiment": exp, "capabilities": caps, "variables": ["Trust"]}


def test_vocabulary_matches_resources():
    """config.yaml lists the same capabilities and levels, in the same order, as the paper's definitions."""
    import re
    from pathlib import Path
    from plr_cmm_mcp.judge import LEVELS, VARIABLES
    res = Path(__file__).resolve().parent.parent / "resources"
    caps = re.findall(r"^### (C\d-\d) ", res.joinpath("capabilities.md").read_text(encoding="utf-8"), re.M)
    assert caps == CAPABILITIES and len(caps) == 16
    levels_md = res.joinpath("levels.md").read_text(encoding="utf-8")
    assert re.findall(r"^\| (L\d) \|", levels_md, re.M) == list(LEVELS)
    assert all(v in levels_md.splitlines()[4] for v in VARIABLES)      # the header row of Table I


def test_validate_ok():
    assert validate(full_judgment(**{"C1-2": "achieved", "C4-3": "partial"})) == []


def test_premise_level_and_validation():
    from plr_cmm_mcp.judge import premise_capabilities
    assert premise_capabilities("L3") == ["C1-1", "C1-2", "C1-3", "C2-1", "C2-2", "C2-3", "C3-1", "C3-2", "C3-3"]
    assert premise_capabilities("L1") == ["C1-1", "C1-2", "C1-3"]
    assert premise_capabilities("なし") == [] and premise_capabilities(None) == [] and premise_capabilities("（L3）") == []
    pre = premise_capabilities("L3")
    pj = {c: "premise" for c in pre}
    # premise capabilities carry no evidence and are accepted only when the level says so
    j = full_judgment(**pj, **{"C4-1": "achieved"})
    assert validate(j, pre) == []
    assert any("premise is only for" in e for e in validate(j))              # no level: premise not allowed
    j2 = full_judgment(**{**pj, "C2-3": "partial"}, **{"C4-1": "achieved"})
    assert any("must be premise" in e for e in validate(j2, pre))            # C2-3 is below the level
    j3 = full_judgment(**pj, **{"C4-1": "premise"})
    assert any("premise is only for" in e for e in validate(j3, pre))        # C4-1 is above the level


def test_validate_errors():
    j = full_judgment(**{"C1-2": "achieved"})
    j["capabilities"][1]["evidence"] = []
    j["capabilities"].pop()                       # drop C5-4
    j["capabilities"][0]["status"] = "yes"
    j["variables"].append("Brand")
    errs = validate(j)
    assert any("C1-2: achieved without evidence" in e for e in errs)
    assert any("missing capabilities: C5-4" in e for e in errs)
    assert any("C1-1: bad status" in e for e in errs)
    assert any("unknown variable: Brand" in e for e in errs)


def test_validate_rejects_personal_quote():
    j = full_judgment(**{"C2-1": "achieved"})
    j["capabilities"][3]["evidence"][0]["quote"] = "担当 a@b.jp"
    assert any("personal-data" in e for e in validate(j))


def test_validate_rejects_malformed_items():
    """Malformed model output is reported as problems, not raised as an exception."""
    assert validate("not an object") == ["judgment must be an object"]
    j = full_judgment(**{"C2-2": "achieved"})
    j["capabilities"][0] = "C1-1"                                   # a string instead of an object
    assert "capability item 1: must be an object" in validate(j)
    j = full_judgment(**{"C2-2": "achieved"})
    j["capabilities"][3]["evidence"] = "記録の文"                   # not a list
    assert "C2-1: evidence must be a list" in validate(j)
    j = full_judgment(**{"C2-2": "achieved"})
    j["capabilities"][4]["evidence"] = ["記録の文"]                 # items not objects
    assert "C2-2: evidence item must be an object" in validate(j)
    j = full_judgment(**{"C2-2": "achieved"})
    j["capabilities"][4]["evidence"] = [{"file": "f", "quote": 12}]
    assert "C2-2: quote must be a string" in validate(j)


def test_load_json_text_nested_and_without_fence():
    txt = 'noise {"a": {"b": {"c": 1}}, "experiment": "005"} trailing'
    assert load_json_text(txt)["a"]["b"]["c"] == 1
    import pytest
    with pytest.raises(ValueError):
        load_json_text("no json here")


def test_load_json_text_with_fence():
    txt = "判定は次のとおり。\n```json\n" + json.dumps(full_judgment(), ensure_ascii=False) + "\n```\n以上"
    assert load_json_text(txt)["experiment"] == "005"


