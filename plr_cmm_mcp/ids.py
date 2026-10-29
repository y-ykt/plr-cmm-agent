"""The identifier of a study: the name of its records folder.

The identifier names the folders where the extracted text, the notes and the judgment of the study
are kept (work/text/<id>/, runs/<run>/notes/<id>/, runs/<run>/judgments/<id>.json). It therefore
has to be a plain folder name: no path separator, not "." or "..", not hidden, no control
characters, no surrounding blanks, and not "top", which names the folder of the top-level files.
Names are normalized to NFC (macOS stores them in NFD).
"""
from __future__ import annotations

import re
import unicodedata

RESERVED = {"top"}
MAX_BYTES = 200                                   # well inside the limit of common file systems
_BAD = re.compile(r"[\x00-\x1f\x7f/\\]")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def check_study_id(s: object) -> str:
    """Return the identifier (NFC), or raise ValueError when it is not a plain folder name."""
    if not isinstance(s, str) or not s.strip():
        raise ValueError("the study identifier must be the name of its records folder")
    s = nfc(s)
    if (s in (".", "..") or s.startswith(".") or s in RESERVED or _BAD.search(s)
            or s != s.strip() or len(s.encode("utf-8")) > MAX_BYTES):
        raise ValueError(f"the study identifier must be a plain folder name, not {s!r}")
    return s


def is_study_id(s: object) -> bool:
    try:
        check_study_id(s)
        return True
    except ValueError:
        return False
