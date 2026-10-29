"""Notes written for one extracted file: schema and validation.

The reading step writes, for each extracted text file, a JSON object
{file, kind, notes: [{topic, fact, quote}]}.  The batch reader (agents/orchestrator.py)
saves these directly; the interactive path submits them through the MCP tool
submit_notes, which validates with the same rules as agents/prompts/reader.md.

Topics are English. The Japanese topic names of the earlier reading instructions are
still accepted (notes written with them exist) and are mapped to English on output.
"""
from __future__ import annotations


from . import config
from .extract import scan_personal
from .ids import is_study_id

# The topics are read from the "notes" section of config.yaml.
_VOCAB = config.load()["notes"]
TOPICS = tuple(_VOCAB["topics"])            # the nine topics, in English
TOPICS_JA = dict(_VOCAB["topics_ja"])       # earlier Japanese topic name -> English


def topic_en(topic: str) -> str:
    """The English topic name, for a topic given in English or in the earlier Japanese form."""
    return TOPICS_JA.get(topic, topic)


MAX_NOTES_PER_FILE = 12
MAX_NOTE_QUOTE = 200

NOTES_SCHEMA = {
    "type": "object",
    "required": ["experiment", "file", "kind", "notes"],
    "properties": {
        "experiment": {"type": "string", "description": "the study identifier: the name of its records folder, exactly as inventory_experiment returned it"},
        "file": {"type": "string", "description": "name of the extracted text file, exactly as list_texts gives it, including .txt"},
        "kind": {"type": "string", "description": "what the file is, in one or two words (plan, procedure, catalog, review record, result summary, draft e-mail, specification, other)"},
        "notes": {
            "type": "array",
            "maxItems": MAX_NOTES_PER_FILE,
            "items": {
                "type": "object",
                "required": ["topic", "fact", "quote"],
                "properties": {
                    "topic": {"type": "string", "enum": list(TOPICS), "description": "one of the nine topics"},
                    "fact": {"type": "string", "description": "one sentence, in English, stating a fact written in the record"},
                    "quote": {"type": "string", "maxLength": MAX_NOTE_QUOTE,
                              "description": "the passage where the fact is written, copied verbatim in the original language"},
                },
            },
        },
    },
}


def validate_notes(obj: dict) -> list[str]:
    """Return a list of problems; empty means the notes are acceptable."""
    errs: list[str] = []
    if not isinstance(obj, dict):
        return ["notes must be an object"]
    if not is_study_id(obj.get("experiment")):
        errs.append("experiment must be the study identifier (the name of its records folder)")
    f = obj.get("file", "")
    if not isinstance(f, str) or not f.endswith(".txt") or "/" in f or f.startswith("."):
        errs.append("file must be the name of an extracted text file (….txt)")
    if not isinstance(obj.get("kind"), str) or not obj.get("kind"):
        errs.append("kind must be a short description of the file")
    notes = obj.get("notes")
    if not isinstance(notes, list):
        return errs + ["notes must be a list"]
    if len(notes) > MAX_NOTES_PER_FILE:
        errs.append(f"more than {MAX_NOTES_PER_FILE} notes")
    for i, n in enumerate(notes, 1):
        if not isinstance(n, dict):
            errs.append(f"note {i}: must be an object")
            continue
        if topic_en(n.get("topic")) not in TOPICS:
            errs.append(f"note {i}: unknown topic {n.get('topic')!r}")
        fact, quote = n.get("fact", ""), n.get("quote", "")
        if not isinstance(fact, str) or not fact.strip():
            errs.append(f"note {i}: fact is empty")
        if not isinstance(quote, str) or not quote.strip():
            errs.append(f"note {i}: quote is empty")
            continue
        if len(quote) > MAX_NOTE_QUOTE:
            errs.append(f"note {i}: quote longer than {MAX_NOTE_QUOTE}")
        for label, text in (("fact", fact), ("quote", quote)):
            if isinstance(text, str) and scan_personal(text):
                errs.append(f"note {i}: {label} contains personal-data pattern")
    return errs
