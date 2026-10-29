"""Judgment output: the fixed shape every judging run must produce, and its validation."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

from . import config
from .extract import scan_personal
from .ids import is_study_id

# The vocabulary of a judgment is read from the "judgment" section of config.yaml.
_VOCAB = config.load()["judgment"]
CAPABILITIES = list(_VOCAB["capabilities"])   # the 16 capability IDs, in order
STATUSES = tuple(_VOCAB["statuses"])
SHOWN = tuple(_VOCAB["shown"])                # statuses that count as "shown by this experiment"
LEVELS = tuple(_VOCAB["levels"])
VARIABLES = tuple(_VOCAB["variables"])
MAX_QUOTE = 300

JSON_SCHEMA = {
    "type": "object",
    "required": ["experiment", "capabilities", "variables"],
    "properties": {
        "experiment": {"type": "string", "description": "the study identifier: the name of its records folder, exactly as get_notes and get_premise were called with"},
        "summary": {"type": "string", "description": "the summary of the study written in step 1 of the procedure, in English"},
        "capabilities": {
            "type": "array",
            "description": "one item for each of the 16 capabilities",
            "items": {
                "type": "object",
                "required": ["capability", "status", "evidence", "reason"],
                "properties": {
                    "capability": {"type": "string", "enum": CAPABILITIES},
                    "status": {"type": "string", "enum": list(STATUSES),
                               "description": "premise only for capabilities at or below the organization's current level (the list from get_premise)"},
                    "evidence": {
                        "type": "array",
                        "items": {"type": "object", "required": ["file", "quote"],
                                  "properties": {"file": {"type": "string"},
                                                 "quote": {"type": "string", "maxLength": MAX_QUOTE}}},
                    },
                    "reason": {"type": "string", "description": "which part of the definition the records meet and which part they do not, in English"},
                },
            },
        },
        "variables": {"type": "array", "items": {"type": "string", "enum": list(VARIABLES)}},
    },
}


@dataclass
class Evidence:
    file: str
    quote: str


@dataclass
class CapabilityJudgment:
    capability: str
    status: str
    evidence: list[Evidence] = field(default_factory=list)
    reason: str = ""


@dataclass
class Judgment:
    experiment: str
    capabilities: list[CapabilityJudgment]
    variables: list[str] = field(default_factory=list)
    summary: str = ""

    def status_of(self, cap: str) -> str:
        for c in self.capabilities:
            if c.capability == cap:
                return c.status
        return "none"

    def to_dict(self) -> dict:
        return asdict(self)


def parse(obj: dict) -> Judgment:
    caps = [CapabilityJudgment(c["capability"], c["status"],
                               [Evidence(e["file"], e["quote"]) for e in c.get("evidence", [])],
                               c.get("reason", ""))
            for c in obj.get("capabilities", [])]
    return Judgment(str(obj.get("experiment", "")), caps, list(obj.get("variables", [])),
                    obj.get("summary", ""))


def premise_capabilities(level: str | None) -> list[str]:
    """Capabilities at or below the organization's current level (L3 -> C1-1 .. C3-3).

    These are treated as premises of a new experiment and are not judged from its records.
    Anything other than L1..L5 (none, "なし", a template placeholder) means no premise."""
    if level not in LEVELS:
        return []
    k = int(level[1])
    return [c for c in CAPABILITIES if int(c[1]) <= k]


def validate(obj: dict, premise: list[str] | None = None) -> list[str]:
    """Return a list of problems; empty means the judgment is acceptable.

    premise: capabilities that must be marked premise (and the only ones that may be)."""
    errs: list[str] = []
    premise = list(premise or [])
    if not isinstance(obj, dict):
        return ["judgment must be an object"]
    if not is_study_id(obj.get("experiment")):
        errs.append("experiment must be the study identifier (the name of its records folder)")
    caps = obj.get("capabilities")
    if not isinstance(caps, list):
        return errs + ["capabilities must be a list"]
    seen: set[str] = set()
    for i, c in enumerate(caps, 1):
        if not isinstance(c, dict):
            errs.append(f"capability item {i}: must be an object")
            continue
        cid = c.get("capability")
        if cid not in CAPABILITIES:
            errs.append(f"unknown capability: {cid}")
            continue
        if cid in seen:
            errs.append(f"duplicate capability: {cid}")
        seen.add(cid)
        st = c.get("status")
        if st not in STATUSES:
            errs.append(f"{cid}: bad status {st!r}")
        if cid in premise and st != "premise":
            errs.append(f"{cid}: is a premise of the organization's level; status must be premise")
        if cid not in premise and st == "premise":
            errs.append(f"{cid}: premise is only for capabilities at or below the organization's level")
        ev = c.get("evidence", [])
        if not isinstance(ev, list):
            errs.append(f"{cid}: evidence must be a list")
            continue
        if st in ("achieved", "partial") and not ev:
            errs.append(f"{cid}: {st} without evidence")
        for e in ev:
            if not isinstance(e, dict):
                errs.append(f"{cid}: evidence item must be an object")
                continue
            q = e.get("quote", "")
            if not isinstance(q, str):
                errs.append(f"{cid}: quote must be a string")
                continue
            if not e.get("file"):
                errs.append(f"{cid}: evidence without file")
            if len(q) > MAX_QUOTE:
                errs.append(f"{cid}: quote longer than {MAX_QUOTE}")
            if scan_personal(q):
                errs.append(f"{cid}: quote contains personal-data pattern")
    missing = [c for c in CAPABILITIES if c not in seen]
    if missing:
        errs.append("missing capabilities: " + ", ".join(missing))
    for v in obj.get("variables", []):
        if v not in VARIABLES:
            errs.append(f"unknown variable: {v}")
    return errs


def load_json_text(text: str) -> dict:
    """Parse a JSON object from model output: the text between the first "{" and the last "}".
    A ```json fence around it is thereby ignored without a regular expression."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in text")
    return json.loads(text[start:end + 1], strict=False)
