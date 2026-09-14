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


def _entry_version(eid: str) -> str | None:
    e = entries().get(eid)
    if e is None:
        return None
    return hashlib.sha256(json.dumps(e, sort_keys=True, default=str).encode()).hexdigest()[:12]


def corpus_status(root=None) -> dict[str, str]:
    """Each concept's status, with `approve --declaration canon/<concept>` overlaid.

    Reads `runs/approvals.jsonl` in the graph root: a concept whose current entry version has an
    acceptance recorded reads `accepted`, whatever its static status. Used for display only — the
    static status in `entries()` (and so `canon_version`) is corpus-independent, so the page and
    `--check` stay stable whether or not a corpus is attached.
    """
    import os
    reg = entries()
    out = {eid: e["status"] for eid, e in reg.items()}
    root = root or os.environ.get("CLAIM_GRAPHS_ROOT")
    if not root:
        return out
    approvals = Path(root) / "runs" / "approvals.jsonl"
    if not approvals.is_file():
        return out
    accepted: dict[str, str] = {}
    for line in approvals.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        decl = rec.get("declaration", "")
        if decl.startswith("canon/"):
            accepted[decl[len("canon/"):]] = rec.get("version", "")
    for eid in out:
        if accepted.get(eid) == _entry_version(eid):
            out[eid] = "accepted"
    return out


def canon_version() -> str:
    """A content digest over the entries — the version every declaration has.

    Computed like `pipeline.declaration_version`: a sha256 over the entries serialised with
    sorted keys, truncated to twelve hex chars. It moves when any entry's definition, status or
    enforcement moves, which is what lets a ledger say which meaning of *warrant* a run was made
    under.
    """
    payload = json.dumps(entries(), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]
