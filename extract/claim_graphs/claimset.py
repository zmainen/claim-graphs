"""Reading and checking a claim set — the interchange form.

`schema/claim-set-v0.schema.json` is the contract; this is the Python side of it. A consumer that
only wants to read a set needs neither: the file is JSON and the schema says what is in it. What
this adds is the part a schema cannot express — that every reference resolves — and one API for
both, so a producer has something to call before it writes.

`validate` returns a list of messages rather than raising on the first. A whole-corpus gate wants
to see every problem in one pass, and a list is what makes the count meaningful: "9 errors across
12 papers" is a measurement, and a traceback is not.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "claim-set-v0.schema.json"

# Only `scopes` may point at the whole set rather than at a claim.
WILDCARD = "*"


def schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def load(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)


def validate(claim_set: dict | str | Path, *, strict_refs: bool = True) -> list[str]:
    """Every way this claim set fails the contract, as a list of messages. Empty means valid.

    Two kinds of check, and the second is the one worth having. The schema catches shape: a
    missing `uuid`, a relation outside the vocabulary, a claim with no text. It cannot catch an
    edge naming a claim that is not there, because JSON Schema has no way to say "this string is
    a key elsewhere in the document" — and a dangling edge is the defect this corpus actually had
    (eleven of them in the corpus this was developed against).

    `strict_refs=False` keeps the shape checks and drops the reference ones, for a set being
    assembled a claim at a time where the targets do not exist yet.
    """
    if isinstance(claim_set, (str, Path)):
        claim_set = load(claim_set)
    out: list[str] = []

    try:
        import jsonschema
    except ImportError:
        out.append("jsonschema is not installed: shape not checked, only references")
    else:
        for e in sorted(jsonschema.Draft202012Validator(schema()).iter_errors(claim_set),
                        key=lambda e: list(e.absolute_path)):
            where = "/".join(str(p) for p in e.absolute_path) or "(root)"
            out.append(f"{where}: {e.message}")

    ids = {c["id"] for c in claim_set.get("claims") or [] if isinstance(c, dict) and "id" in c}
    questions = {q["id"] for q in claim_set.get("questions") or [] if isinstance(q, dict)}

    seen: set[tuple[str, str, str]] = set()
    for i, edge in enumerate(claim_set.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        src, rel, dst = edge.get("from"), edge.get("rel"), edge.get("to")
        key = (str(src), str(rel), str(dst))
        if key in seen:
            out.append(f"edges/{i}: {src} --{rel}--> {dst} is declared twice")
        seen.add(key)
        if strict_refs:
            if src not in ids and ":" not in str(src):
                out.append(f"edges/{i}: from {src!r} is not a claim in this set")
            if dst != WILDCARD and dst not in ids and ":" not in str(dst):
                out.append(f"edges/{i}: to {dst!r} is not a claim in this set")
            elif dst == WILDCARD and rel != "scopes":
                out.append(f"edges/{i}: only `scopes` may target {WILDCARD!r}, not {rel!r}")

    if strict_refs:
        for c in claim_set.get("claims") or []:
            if not isinstance(c, dict):
                continue
            for q in c.get("addresses") or []:
                if q not in questions:
                    out.append(f"claims/{c.get('id')}: addresses {q!r}, "
                               f"which is not a question in this set")
        for v in claim_set.get("views") or []:
            for r in (v.get("roots") or []):
                if r not in ids:
                    out.append(f"views/{v.get('id')}: root {r!r} is not a claim in this set")
    return out


def edges_of(claim_set: dict, key: str) -> list[dict]:
    """Every edge touching `key`, in either direction."""
    return [e for e in claim_set.get("edges") or []
            if e.get("from") == key or e.get("to") == key]


def unaccounted(claim_set: dict, asserted: set[str] | list[str]) -> list[str]:
    """Claim ids that nothing in `asserted` accounts for — the coverage denominator.

    A consumer marking up a document knows which claims its marks name; the set supplies what
    there was to name. Sorted, so a diff between two runs is readable.
    """
    asserted = set(asserted)
    return sorted(c["id"] for c in claim_set.get("claims") or []
                  if isinstance(c, dict) and c.get("id") not in asserted)
