"""Inventory of input records: decide by names only which files are read.

Implements the file classification described in README (Input) and config.yaml. Files are never
opened here. macOS stores file names in NFD, so every name is normalized to NFC
before matching.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Iterable

import yaml

from .ids import check_study_id, nfc


@dataclass
class Rules:
    input_root: str
    experiments_dir: str
    top_files: list[str]
    use_subfolders: list[str]
    exclude_subfolders: dict[str, str]
    exclude_experiment_dirs: list[str]
    exclude_name_fragments: list[str]
    use_extensions: list[str]
    work_dir: str = "work"
    runs_dir: str = "runs"

    @classmethod
    def load(cls, path: str | os.PathLike) -> "Rules":
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        known = {k: raw[k] for k in cls.__dataclass_fields__ if k in raw}
        rules = cls(**known)
        rules.top_files = [nfc(x) for x in rules.top_files]
        rules.use_subfolders = [nfc(x) for x in rules.use_subfolders]
        rules.exclude_subfolders = {nfc(k): v for k, v in rules.exclude_subfolders.items()}
        rules.exclude_experiment_dirs = [nfc(x) for x in rules.exclude_experiment_dirs]
        rules.exclude_name_fragments = [nfc(x) for x in rules.exclude_name_fragments]
        rules.use_extensions = [x.lower() for x in rules.use_extensions]
        return rules


@dataclass
class Entry:
    experiment: str          # the study identifier (the name of its records folder), or "top" for the summary files
    path: str                # absolute path
    relpath: str             # path relative to the experiment folder (NFC)
    use: bool
    reason: str              # why it is used or excluded


@dataclass
class Inventory:
    entries: list[Entry] = field(default_factory=list)

    @property
    def used(self) -> list[Entry]:
        return [e for e in self.entries if e.use]

    @property
    def excluded(self) -> list[Entry]:
        return [e for e in self.entries if not e.use]

    def counts_by_reason(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.excluded:
            out[e.reason] = out.get(e.reason, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def counts_by_experiment(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.used:
            out[e.experiment] = out.get(e.experiment, 0) + 1
        return dict(sorted(out.items()))

    def to_json(self, path: str | os.PathLike) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"entries": [asdict(e) for e in self.entries],
                       "used": len(self.used), "excluded": len(self.excluded),
                       "by_reason": self.counts_by_reason(),
                       "by_experiment": self.counts_by_experiment()},
                      f, ensure_ascii=False, indent=1)

    def used_names(self) -> list[str]:
        """The list shown to the user for confirmation before any file is opened."""
        return [f"{e.experiment}\t{e.relpath}" for e in self.used]


def _iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()                      # deterministic order on every file system
        for name in sorted(filenames):
            if name.startswith(".") or name.startswith("~$"):
                continue
            yield Path(dirpath) / name


def classify(relpath: str, rules: Rules) -> tuple[bool, str]:
    """Classify one file of an experiment folder by its relative path (NFC)."""
    rel = nfc(relpath)
    for prefix, why in rules.exclude_subfolders.items():
        if rel.startswith(prefix):
            return False, f"folder excluded: {prefix} ({why})"
    if not any(rel.startswith(p) for p in rules.use_subfolders):
        return False, "folder not in use list: " + rel.split("/")[0]
    ext = os.path.splitext(rel)[1].lower()
    if ext not in rules.use_extensions:
        return False, "extension: " + (ext or "(none)")
    for frag in rules.exclude_name_fragments:
        if frag in rel:
            return False, "name contains: " + frag
    return True, "document in a used folder"


def experiment_id(dirname: str) -> str:
    """The identifier of a study is the name of its records folder (NFC)."""
    return nfc(dirname)


def inventory_experiment_dir(dp: Path, eid: str, rules: Rules) -> Inventory:
    """Inventory of one experiment folder (files are classified by name only)."""
    inv = Inventory()
    for p in _iter_files(dp):
        rel = nfc(str(p.relative_to(dp)))
        use, why = classify(rel, rules)
        inv.entries.append(Entry(eid, str(p), rel, use, why))
    return inv


def find_experiment_dir(rules: Rules, experiment: str) -> tuple[str, Path]:
    """Resolve the records folder of one study to (identifier, folder).

    experiment names the folder: its name when it lies directly under <input_root>/<experiments_dir>,
    or a path (absolute, or relative to that folder or to input_root). The folder must exist and lie
    inside input_root, and its name is the study's identifier."""
    if not isinstance(experiment, str) or not experiment.strip():
        raise ValueError("the records folder of the study must be given")
    root = Path(rules.input_root).expanduser().resolve()
    exp_root = (root / rules.experiments_dir).resolve()
    cand = Path(experiment).expanduser()
    tries = [cand] if cand.is_absolute() else [exp_root / cand, root / cand]
    dp = None
    for t in tries:
        try:
            if t.is_dir():
                dp = t.resolve()
                break
        except (OSError, ValueError):
            continue
    if dp is None:
        raise ValueError(f"no records folder {experiment!r} under {exp_root}")
    if root not in dp.parents or dp == exp_root:
        raise ValueError(f"the records folder must be a folder inside {root} (not the input or experiments folder itself)")
    excluded = [nfc(p) for p in dp.relative_to(root).parts if nfc(p) in rules.exclude_experiment_dirs]
    if excluded:
        raise ValueError(f"folder {excluded[0]} is excluded by config.yaml (exclude_experiment_dirs)")
    return check_study_id(dp.name), dp


def build_inventory(rules: Rules) -> Inventory:
    inv = Inventory()
    root = Path(rules.input_root)
    exp_root = root / rules.experiments_dir
    for d in sorted(os.listdir(exp_root)):
        dp = exp_root / d
        if not dp.is_dir():
            continue
        if nfc(d) in rules.exclude_experiment_dirs:
            for p in _iter_files(dp):
                inv.entries.append(Entry("-", str(p), nfc(str(p.relative_to(exp_root))), False,
                                         "experiment dir excluded: " + nfc(d)))
            continue
        inv.entries.extend(inventory_experiment_dir(dp, experiment_id(d), rules).entries)
    for name in sorted(os.listdir(root)):
        p = root / name
        if p.is_file() and not name.startswith("."):
            if nfc(name) in rules.top_files:
                inv.entries.append(Entry("top", str(p), nfc(name), True, "summary file"))
            else:
                inv.entries.append(Entry("top", str(p), nfc(name), False, "top-level file not in use list"))
        elif p.is_dir() and nfc(name) in rules.exclude_experiment_dirs:
            for q in _iter_files(p):
                inv.entries.append(Entry("-", str(q), nfc(str(q.relative_to(root))), False,
                                         "experiment dir excluded: " + nfc(name)))
    return inv


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="List input records by name; nothing is opened.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", help="write the inventory JSON here")
    ap.add_argument("--names", action="store_true", help="print the names of files to be read")
    a = ap.parse_args(argv)
    rules = Rules.load(a.config)
    inv = build_inventory(rules)
    print(f"used {len(inv.used)}  excluded {len(inv.excluded)}")
    for k, v in inv.counts_by_reason().items():
        print(f"  {v:5d}  {k}")
    print("by experiment:", inv.counts_by_experiment())
    if a.names:
        print("\n".join(inv.used_names()))
    if a.out:
        inv.to_json(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
