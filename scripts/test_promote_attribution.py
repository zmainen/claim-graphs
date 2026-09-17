"""An approval must name whoever granted it, or refuse to exist.

Five gap-claim decisions on file are signed `unnamed`, and the layer approval they justified
inherited it — a record that looks signed and is not. The review endpoint requires a name now,
so the remaining way to produce one is this path, which used to fall back to "unknown".
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promote import UNSIGNED, signed_by  # noqa: E402


def _d(by):
    return {"by": by, "decision": "accept"}


def test_a_signed_batch_names_the_signer():
    assert signed_by([_d("Zach Mainen"), _d("Zach Mainen")], "p") == "Zach Mainen"


def test_every_sentinel_is_refused():
    for sentinel in UNSIGNED:
        try:
            signed_by([_d(sentinel)], "p")
        except SystemExit as exc:
            assert "cannot be attributed" in str(exc)
        else:
            raise AssertionError(f"{sentinel!r} was accepted as a signature")


def test_case_and_whitespace_do_not_smuggle_a_sentinel_through():
    for sentinel in ("  unnamed ", "Unknown", "UNNAMED"):
        try:
            signed_by([_d(sentinel)], "p")
        except SystemExit:
            pass
        else:
            raise AssertionError(f"{sentinel!r} was accepted as a signature")


def test_missing_absent_and_empty_are_refused():
    for ds in ([], [{}], [{"by": None}], [{"by": "   "}], [{"by": 7}]):
        try:
            signed_by(ds, "p")
        except SystemExit:
            pass
        else:
            raise AssertionError(f"{ds!r} was accepted")


def test_a_real_signature_survives_beside_a_sentinel():
    """One unsigned record in a batch should not lose the person who signed the rest."""
    assert signed_by([_d("unnamed"), _d("Zach Mainen")], "p") == "Zach Mainen"


def test_two_reviewers_are_both_named():
    """The approval is for the batch, so it does not pick one and drop the other."""
    assert signed_by([_d("B Lindqvist"), _d("A Okonkwo")], "p") == "A Okonkwo, B Lindqvist"


def test_the_refusal_says_where_to_fix_it():
    try:
        signed_by([_d("unnamed")], "gadeke-2026-guilt-insula")
    except SystemExit as exc:
        msg = str(exc)
        assert "gadeke-2026-guilt-insula" in msg
        assert "gap-claim-decisions.jsonl" in msg


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
