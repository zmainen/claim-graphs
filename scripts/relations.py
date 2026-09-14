"""The relation vocabulary — a thin view over the canon.

A relation is a proposition about logical structure between two claims. Which relations exist,
and which of them are oppositions, was the question that lived in four places at once —
`corpus_facts.py`, `export_mira.py`, `formats_report.py` and `check_relations.py` each wrote the
vocabulary down and the four lists disagreed. That was ended by declaring the vocabulary once and
importing it; it now lives one level further in, in `canon/vocab.py`, alongside every other
concept the system has, and this module re-exports it so that `from relations import EDGE_KEYS`
and `rel.DESCRIPTIONS` keep meaning what they meant. Edit the data in the canon, not here.

Loaded by path from the machinery — `contract.py`, `skill.py`, `to_claim_set.py` and
`check_relations.py` all read it as a script's module rather than a package's — so it finds the
canon by path relative to itself, the same idiom those callers use to find this file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "canon_vocab", Path(__file__).resolve().parents[1] / "canon" / "vocab.py")
_vocab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vocab)  # type: ignore[union-attr]

_SUPPORTS = _vocab._SUPPORTS
_OPPOSES = _vocab._OPPOSES
GAPS = _vocab.GAPS
SUPPORTS = _vocab.SUPPORTS
OPPOSES = _vocab.OPPOSES
EDGE_KEYS = _vocab.EDGE_KEYS
DESCRIPTIONS = _vocab.DESCRIPTIONS
DIRECTION = _vocab.DIRECTION
EXAMPLE = _vocab.EXAMPLE
CONFUSABLE = _vocab.CONFUSABLE
CONTRARY = _vocab.CONTRARY
REFUTES_OWN = _vocab.REFUTES_OWN
OUTCOME = _vocab.OUTCOME
NEUTRAL_TEST = _vocab.NEUTRAL_TEST
STANCES = _vocab.STANCES


def relations(claim):
    """Every relation this claim declares, as relation names, one per target.

    Two shapes carry them: a top-level YAML key whose value is a list of target slugs, and the
    `belongings` list of `{relation, target}` objects. Both are the schema; a count that reads
    only one of them is wrong by however much the other holds.
    """
    for key in sorted(EDGE_KEYS):
        for target in (claim.get(key) or []):
            if isinstance(target, str):
                yield key
    for item in (claim.get("belongings") or []):
        if isinstance(item, dict) and item.get("relation"):
            yield item["relation"]
