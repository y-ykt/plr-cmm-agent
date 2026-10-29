"""MCP server for the PLR-CMM assessment agent.

Tools      : get_procedure, get_capabilities, get_levels, list_experiments, get_notes,
             get_premise, judgment_schema, submit_judgment
             (reading a new experiment) inventory_experiment, extract_experiment,
             list_texts, get_text, notes_schema, submit_notes, render_judgment
Resources  : plr-cmm://capabilities, plr-cmm://levels, plr-cmm://procedure
Prompts    : ingest_experiment (reading), judge_experiment (judging), report_experiment (reporting)

Environment:
  PLR_CMM_ROOT       repository directory (default: parent of this package)
  PLR_CMM_RUN        run directory where notes are read and judgments are written
  PLR_CMM_CONDITION  "full" (procedure + definitions) or "names" (capability names only)
  PLR_CMM_WORK       work directory holding the extracted text (work/text/<experiment>/)
  PLR_CMM_CONFIG     config.yaml with the input location, the inventory rules and the judgment vocabulary

"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from . import config
from .judge import CAPABILITIES, JSON_SCHEMA, SHOWN, premise_capabilities, validate
from .notes import NOTES_SCHEMA, topic_en, validate_notes
from .ids import check_study_id, is_study_id
from .inventory import Rules, find_experiment_dir, inventory_experiment_dir
from .extract import extract_inventory

ROOT = config.root()
CONFIG = config.config_path()
RUN = Path(os.environ.get("PLR_CMM_RUN", ROOT / "runs" / "dev"))
CONDITION = os.environ.get("PLR_CMM_CONDITION", "full")
WORK = Path(os.environ.get("PLR_CMM_WORK", ROOT / "work"))
RES = ROOT / "resources"
SUMMARY_MAX_CHARS = 6000
_CFG = config.load()
SUMMARY_FILE_GLOB = _CFG.get("summary_file_glob", "")   # extracted text of the summary workbook
SUMMARY_SHEET = _CFG.get("summary_sheet", "")           # the sheet with one row per experiment
TEXT_CHUNK_CHARS = 20_000

# Usage guidance handed to the client when it connects (MCP "instructions"), so that a user can ask in
# plain words ("judge study 003") and the client's agent follows the right prompt without naming tools.
INSTRUCTIONS = (ROOT / "agents" / "prompts" / "instructions.md").read_text(encoding="utf-8")

mcp = MCPServer("plr-cmm", instructions=INSTRUCTIONS)


def _read(name: str) -> str:
    return (RES / name).read_text(encoding="utf-8")


def _capability_names_only() -> str:
    text = _read("capabilities.md")
    heads = re.findall(r"^###? (C\d-\d) (.+)$", text, re.M)
    lines = ["# The 16 PLR-CMM capabilities (names only)", ""]
    lines += [f"- {cid} {name}" for cid, name in heads]
    return "\n".join(lines)


@mcp.tool()
def get_procedure() -> str:
    """Return the judging procedure. Under the condition names, no procedure is given."""
    if CONDITION == "names":
        return ("There is no procedure under this condition. From the capability names and the notes of the "
                "records, decide achieved / partial / none for each capability, attach the file name and "
                "quote of the evidence, and pass the judgment to submit_judgment.")
    return _read("procedure.md")


@mcp.tool()
def get_capabilities() -> str:
    """Return the capability definitions (condition full) or the capability names only (condition names)."""
    if CONDITION == "names":
        return _capability_names_only()
    return _read("capabilities.md")


@mcp.tool()
def get_levels() -> str:
    """Return the PLR-CMM level table."""
    if CONDITION == "names":
        return "The level table is not given under this condition."
    return _read("levels.md")


@mcp.tool()
def list_experiments() -> list[str]:
    """The identifiers of the studies whose notes are available (the names of their records folders)."""
    d = RUN / "notes"
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir() and is_study_id(p.name))


def summary_section(experiment: str, work: Path = WORK,
                    file_glob: str = SUMMARY_FILE_GLOB, sheet: str = SUMMARY_SHEET) -> str:
    """The study's rows of the summary sheet of the summary workbook (raw extracted text, already
    masked). The workbook and the sheet are named in config.yaml (summary_file_glob, summary_sheet);
    other sheets are not used. Rows begin with the study's number, so only a study whose identifier
    begins with digits has rows; for any other study the result is empty."""
    m = re.match(r"\d+", experiment or "")
    top = work / "text" / "top"
    files = sorted(top.glob(file_glob)) if m and file_glob and sheet and top.exists() else []
    if not files:
        return ""
    number = m.group(0)
    rows, in_summary = [], False
    for ln in files[0].read_text(encoding="utf-8").split("\n"):
        if ln.startswith("--- sheet "):
            in_summary = sheet in ln
            continue
        if in_summary and ln.startswith(f"{number} |"):
            rows.append(ln)
    text = "\n".join(rows)
    if len(text) > SUMMARY_MAX_CHARS:
        text = text[:SUMMARY_MAX_CHARS] + "\n[truncated]"
    return text


@mcp.tool()
def get_notes(experiment: str) -> str:
    """Return the notes (facts with quotes) written from the study's records, file by file, with the study's rows of the summary sheet at the end."""
    try:
        experiment = _experiment_id(experiment)
    except ValueError as ex:
        return f"rejected: {ex}"
    d = RUN / "notes" / experiment
    if not d.exists():
        return f"There are no notes for study {experiment}."
    parts = [f"# Notes from the records of study {experiment}", "",
             "Facts may be in English or Japanese; quotes are verbatim from the records (Japanese).", ""]
    for p in sorted(d.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        parts.append(f"## File: {obj.get('file', p.stem)} ({obj.get('kind', '')})")
        notes = obj.get("notes")
        for n in (notes if isinstance(notes, list) else []):
            if not isinstance(n, dict):
                continue
            parts.append(f"- [{topic_en(str(n.get('topic', '')))}] {n.get('fact', '')}")
            if n.get("quote"):
                parts.append(f"  Quote: {n['quote']}")
        parts.append("")
    summ = summary_section(experiment)
    if summ:
        parts += ["## The study's rows of the summary sheet (from the summary workbook, verbatim)", "", summ, ""]
    return "\n".join(parts)


# ---------------------------------------------------------------- reading a new experiment


def _locate(experiment: str) -> tuple[str, Path, Rules]:
    rules = Rules.load(CONFIG)
    eid, dp = find_experiment_dir(rules, experiment)
    return eid, dp, rules


@mcp.tool()
def inventory_experiment(experiment: str) -> dict:
    """Apply the inventory rules (config.yaml) to the records folder of a study (its name under the experiments folder, or a path) and return the study identifier and, by file name only, the files to use and the files to exclude (with reasons). No file is opened."""
    try:
        eid, dp, rules = _locate(experiment)
    except (ValueError, FileNotFoundError) as ex:
        return {"error": str(ex)}
    inv = inventory_experiment_dir(dp, eid, rules)
    return {"experiment": eid, "folder": str(dp),
            "used": [e.relpath for e in inv.used],
            "excluded": [{"file": e.relpath, "reason": e.reason} for e in inv.excluded],
            "counts": {"used": len(inv.used), "excluded": len(inv.excluded)}}


@mcp.tool()
def extract_experiment(experiment: str) -> dict:
    """Extract the text of the files the inventory marked as used, mask contact details, and store it under work/text/<study>/. Returns the list of files with character counts and states; not the text itself."""
    try:
        eid, dp, rules = _locate(experiment)
    except (ValueError, FileNotFoundError) as ex:
        return {"error": str(ex)}
    inv = inventory_experiment_dir(dp, eid, rules)
    log = extract_inventory(inv, WORK, log_name=f"extract_log_{eid}.json")
    return {"experiment": eid, "summary": log.summary(),
            "files": [{"file": Path(r.out_file).name if r.out_file else r.relpath,
                       "status": r.status, "chars": r.chars, "detail": r.detail} for r in log.records]}

def _experiment_id(experiment: str) -> str:
    """The study identifier as used in paths: the name of its records folder (see ids.py).
    Anything that is not a plain folder name, such as a path fragment, is refused before it reaches
    the file system."""
    return check_study_id(experiment)


def _text_dir(experiment: str) -> Path:
    return WORK / "text" / _experiment_id(experiment)


@mcp.tool()
def list_texts(experiment: str) -> list[dict]:
    """List the extracted text files (name and character count) and whether notes have been submitted for each."""
    try:
        d = _text_dir(experiment)
    except ValueError:
        return []
    if not d.exists():
        return []
    notes_dir = RUN / "notes" / experiment
    out = []
    for p in sorted(d.glob("*.txt")):
        out.append({"file": p.name, "chars": len(p.read_text(encoding="utf-8")),
                    "notes_done": (notes_dir / (p.stem + ".json")).exists()})
    return out


@mcp.tool()
def get_text(experiment: str, file: str, offset: int = 0) -> str:
    """Return the extracted text of one file. Long files come in chunks of TEXT_CHUNK_CHARS characters; use offset for the continuation."""
    try:
        d = _text_dir(experiment)
    except ValueError as ex:
        return f"rejected: {ex}"
    # a plain file name inside the experiment's text directory, nothing else
    if not isinstance(file, str) or not file or Path(file).name != file or file.startswith("."):
        return "rejected: bad file name"
    p = d / file
    if not p.resolve().is_relative_to(d.resolve()) or not p.is_file():
        return f"rejected: no such file {file} in experiment {experiment}"
    offset = max(0, int(offset))
    text = p.read_text(encoding="utf-8")
    chunk = text[offset:offset + TEXT_CHUNK_CHARS]
    head = f"# {file} ({len(text):,} characters, from character {offset:,})\n\n"
    tail = "" if offset + TEXT_CHUNK_CHARS >= len(text) else \
        f"\n\n[continued: offset={offset + TEXT_CHUNK_CHARS}]"
    return head + chunk + tail


@mcp.tool()
def notes_schema() -> dict:
    """The JSON schema of the notes passed to submit_notes."""
    return NOTES_SCHEMA


@mcp.tool()
def submit_notes(notes: dict) -> str:
    """Validate the notes of one file; if they pass, save them and return 'accepted', otherwise return the list of problems."""
    errs = validate_notes(notes)
    if not errs:
        d = _text_dir(notes["experiment"])
        if not (d / notes["file"]).exists():
            errs.append(f"no extracted text named {notes['file']} in experiment {notes['experiment']}")
    if errs:
        return "rejected:\n- " + "\n- ".join(errs)
    out = RUN / "notes" / notes["experiment"]
    out.mkdir(parents=True, exist_ok=True)
    stem = notes["file"][:-len(".txt")]
    body = {"file": notes["file"], "kind": notes["kind"], "notes": notes["notes"]}
    (out / f"{stem}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"accepted: experiment {notes['experiment']}, {notes['file']}, {len(notes['notes'])} notes"


@mcp.tool()
def judgment_schema() -> dict:
    """The JSON schema of the judgment passed to submit_judgment."""
    return JSON_SCHEMA


@mcp.tool()
def submit_judgment(judgment: dict) -> str:
    """Validate a judgment; if it passes, save it and return 'accepted', otherwise return the list of problems."""
    exp = str(judgment.get("experiment", "")) if isinstance(judgment, dict) else ""
    premise = _premise(exp)["premise"] if exp else []
    errs = validate(judgment, premise)
    if errs:
        return "rejected:\n- " + "\n- ".join(errs)
    out = RUN / "judgments"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{exp}.json").write_text(json.dumps(judgment, ensure_ascii=False, indent=1), encoding="utf-8")
    shown = [c["capability"] for c in judgment["capabilities"] if c["status"] in SHOWN]
    msg = f"accepted: experiment {exp}, shown {len(shown)} of {len(CAPABILITIES)} capabilities"
    if premise:
        msg += f", {len(premise)} premise"
    return msg


def _overview_fields(experiment: str) -> dict[str, str]:
    """Organization, level, name and period from the overview sheet (resources/record_template.md),
    if the records have one. English and Japanese field names are accepted; template placeholders
    (starting with a parenthesis) are ignored."""
    keys = {"organization": "organization", "organisation": "organization", "level": "level",
            "name": "name", "period": "period",
            "組織": "organization", "レベル": "level", "名前": "name", "時期": "period"}
    out: dict[str, str] = {}
    try:
        d = _text_dir(experiment)
    except ValueError:
        return out
    files = sorted(p for p in d.glob("*.txt") if "概要" in p.name or "overview" in p.name.lower()) \
        if d.exists() else []
    for p in files:
        for line in p.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*(Organi[sz]ation|Level|Name|Period|組織|レベル|名前|時期)\s*[：:]\s*(.+?)\s*$", line, re.I)
            if m and not m.group(2).startswith(("（", "(")):
                k = keys[m.group(1).lower()]
                out.setdefault(k, m.group(2))
    return out


def _premise(experiment: str) -> dict:
    ov = _overview_fields(experiment)
    level = ov.get("level", "none")
    if level not in ("L1", "L2", "L3", "L4", "L5"):
        level = "none"
    return {"experiment": experiment, "organization": ov.get("organization", "(not in the overview)"),
            "level": level, "premise": premise_capabilities(level)}


@mcp.tool()
def get_premise(experiment: str) -> dict:
    """Return the organization's name and current level (from the overview sheet of the records) and the list of capabilities to treat as premises. Capabilities in the list are not judged from the records and are marked premise. Without an overview sheet the level is none and the list is empty."""
    r = _premise(experiment)
    r["note"] = ("Capabilities at or below the level were acquired in the organization's earlier studies; treat them as "
                 "premises and do not judge them from this study's records."
                 if r["premise"] else "The overview gives no level, so all 16 capabilities are judged from the records.")
    return r


@mcp.tool()
def render_judgment(experiment: str) -> str:
    """Return the accepted judgment as one row of a capability table (No., Study, Period, Capability ID, PDT variable), with the evidence for each capability."""
    try:
        experiment = _experiment_id(experiment)
    except ValueError as ex:
        return f"rejected: {ex}"
    p = RUN / "judgments" / f"{experiment}.json"
    if not p.exists():
        return f"There is no accepted judgment for study {experiment}."
    j = json.loads(p.read_text(encoding="utf-8"))
    shown = [c for c in j["capabilities"] if c["status"] in SHOWN]
    premise = [c["capability"] for c in j["capabilities"] if c["status"] == "premise"]
    cells = [c["capability"] if c["status"] == "achieved" else f"({c['capability']})" for c in shown]
    ov = _overview_fields(experiment)
    pr = _premise(experiment)
    row = (f"| {experiment} | {ov.get('name', '(name)')} | {ov.get('period', '(period)')} | "
           f"{', '.join(cells) or 'none'} | {'/'.join(j.get('variables', [])) or 'none'} |")
    out = [f"# Judgment of study {experiment}", "",
           f"Organization: {pr['organization']}; level taken as premise: {pr['level']}"
           + (f" (not judged from the records: {', '.join(premise)})" if premise else " (all 16 capabilities judged from the records)"), "",
           "| No. | Study | Period | Capability ID | PDT variable |", "|---|---|---|---|---|", row, "",
           "Parentheses mark partial. Name and period are taken from the overview sheet of the records when there is one; otherwise a person fills them in."
           + (" The row lists only the capabilities above the premise level that this study demonstrated." if premise else ""), ""]
    if j.get("summary"):
        out += ["## Summary of the study (written by the judging agent)", "", j["summary"], ""]
    out += ["## Evidence by capability", ""]
    for c in shown:
        out.append(f"### {c['capability']} ({c['status']})")
        if c.get("reason"):
            out.append(f"Reason: {c['reason']}")
        for e in c.get("evidence", []):
            out.append(f"- {e['file']}: {e['quote']}")
        out.append("")
    return "\n".join(out)


@mcp.resource("plr-cmm://capabilities")
def res_capabilities() -> str:
    return get_capabilities()


@mcp.resource("plr-cmm://levels")
def res_levels() -> str:
    return get_levels()


@mcp.resource("plr-cmm://procedure")
def res_procedure() -> str:
    return get_procedure()


@mcp.prompt()
def judge_experiment(experiment: str) -> str:
    """The instruction for judging one study."""
    text = (ROOT / "agents" / "prompts" / "judge.md").read_text(encoding="utf-8")
    return text + f"\n\nStudy to judge: {experiment}\n"


@mcp.prompt()
def report_experiment(experiment: str) -> str:
    """The instruction for showing the accepted judgment of one study (the report)."""
    text = (ROOT / "agents" / "prompts" / "report.md").read_text(encoding="utf-8")
    return text + f"\n\nStudy to report: {experiment}\n"


@mcp.prompt()
def ingest_experiment(experiment: str) -> str:
    """The instruction for ingesting the records of a new study (inventory, extraction, reading). No judging."""
    text = (ROOT / "agents" / "prompts" / "ingest.md").read_text(encoding="utf-8")
    reader = (ROOT / "agents" / "prompts" / "reader.md").read_text(encoding="utf-8")
    m = re.search(r"^## Rules\n.*", reader, re.S | re.M)
    rules = m.group(0).strip() if m else ""
    return text + "\n\n" + rules + f"\n\nStudy to ingest: {experiment}\n"


if __name__ == "__main__":
    mcp.run()
