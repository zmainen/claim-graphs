"""The claim vocabulary — a thin view over the canon.

Roles, claim types, questions, confidence and the reconciler's three-way test were written into
each prompt by hand and disagreed; declaring them once ended that. They now live one level
further in, in `canon/vocab.py`, beside the relation vocabulary and every other concept the
system has, and this module re-exports them so `vocabulary.ROLES` and `from . import vocabulary`
keep meaning what they meant. Edit the data in the canon, not here.

`contract.py` renders this into `extract/prompts/contract/vocabulary.md`, which every model call
receives; examples name a corpus claim by (paper, slug), quoted from the claim file, so an
example is a real claim or generation fails.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "canon_vocab", Path(__file__).resolve().parents[2] / "canon" / "vocab.py")
_vocab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vocab)  # type: ignore[union-attr]

QUESTIONS = _vocab.QUESTIONS
ROLES = _vocab.ROLES
ROLE_CONFUSABLE = _vocab.ROLE_CONFUSABLE
WARRANTS = _vocab.WARRANTS
NOT_CLAIMS = _vocab.NOT_CLAIMS
CLAIM_TYPES = _vocab.CLAIM_TYPES
ASSERTION_CONFIDENCE_NOTE = _vocab.ASSERTION_CONFIDENCE_NOTE
CONFIDENCE = _vocab.CONFIDENCE
READER_CONFIDENCE = _vocab.READER_CONFIDENCE
SAME_CLAIM = _vocab.SAME_CLAIM
