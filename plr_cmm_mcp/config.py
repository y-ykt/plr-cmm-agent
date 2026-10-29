"""Where the repository and its config.yaml are, and how the configuration is read.

Environment (read each time, so that a module reloaded under a changed environment sees the change):
  PLR_CMM_ROOT     repository directory (default: parent of this package)
  PLR_CMM_CONFIG   config.yaml with the input location, the inventory rules and the judgment vocabulary
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml


def root() -> Path:
    return Path(os.environ.get("PLR_CMM_ROOT", Path(__file__).resolve().parent.parent))


def config_path() -> Path:
    return Path(os.environ.get("PLR_CMM_CONFIG", root() / "config.yaml"))


def load(path: str | os.PathLike | None = None) -> dict:
    with open(path or config_path(), encoding="utf-8") as f:
        return yaml.safe_load(f)
