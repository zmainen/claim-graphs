"""The canon: one declaration of every concept the system has, versioned and rendered.

`canon.vocab` holds the closed vocabularies as data; `canon.entries` wraps each concept with the
definition, distinctions, enforcement and toy example the design notes carried. `scripts/canon.py`
is the CLI (`--check`, and in PR 2 `--render`, `--version`).

    from canon import entries, canon_version, TOY_STUDY
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import vocab  # noqa: F401  (re-exported for `canon.vocab`)
from .entries import entries, FIELDS, ACCEPTED, PROPOSED  # noqa: F401

ROOT = Path(__file__).resolve().parent
TOY_STUDY = ROOT / "toy-study"
TOY_PAPER = "toy-widgets"


def canon_version() -> str:
    """A content digest over the entries — the version every declaration has.

    Computed like `pipeline.declaration_version`: a sha256 over the entries serialised with
    sorted keys, truncated to twelve hex chars. It moves when any entry's definition, status or
    enforcement moves, which is what lets a ledger say which meaning of *warrant* a run was made
    under.
    """
    payload = json.dumps(entries(), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]
