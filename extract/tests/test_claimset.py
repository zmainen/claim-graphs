"""The interchange form's Python side: validate, and the reference checks a schema cannot make.

What is pinned here is the division of labour. JSON Schema catches shape — a missing `uuid`, a
relation outside the vocabulary. It has no way to say "this string is a key elsewhere in the
document", so it cannot catch a dangling edge, which is the defect this corpus actually had
(eleven of them in the reference corpus, and six more of a second kind nothing was checking).

No network, no corpus. Runs under pytest or standalone.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claim_graphs.claimset import edges_of, unaccounted, validate

UUID = "0b3d5a4e-1c2b-4d3e-8f90-1a2b3c4d5e6f"


def _set(**over) -> dict:
    base = {
        "schemaVersion": "0",
        "document": {"id": "d"},
        "questions": [{"id": "q1", "text": "Does it?"}],
        "claims": [
            {"id": "h", "uuid": UUID, "text": "A hypothesis.", "type": "hypothesis",
             "addresses": ["q1"], "assertions": [{"document": "d", "stance": "asserts"}]},
            {"id": "r", "uuid": UUID.replace("0b", "1c"), "text": "A result.",
             "type": "empirical", "assertions": [{"document": "d", "stance": "asserts"}]},
        ],
        "edges": [{"from": "h", "rel": "entails", "to": "r"}],
    }
    return {**base, **over}


def test_a_well_formed_set_is_valid():
    assert validate(_set()) == []


def test_an_edge_naming_nothing_is_caught():
    """The reference check that JSON Schema cannot make, and the one the corpus needed."""
    msgs = validate(_set(edges=[{"from": "h", "rel": "supports", "to": "absent"}]))
    assert any("to 'absent' is not a claim in this set" in m for m in msgs)


def test_addresses_is_checked_too():
    """#157: six claims addressed questions their index no longer declared, and nothing looked.
    `addresses` is not a relation, so every relation checker was blind to it."""
    msgs = validate(_set(questions=[]))
    assert any("addresses 'q1'" in m for m in msgs)


def test_only_scopes_may_target_the_whole_set():
    assert validate(_set(edges=[{"from": "h", "rel": "scopes", "to": "*"}])) == []
    msgs = validate(_set(edges=[{"from": "h", "rel": "requires", "to": "*"}]))
    assert any("only `scopes` may target" in m for m in msgs)


def test_a_duplicate_edge_is_reported_once_as_a_duplicate():
    e = {"from": "h", "rel": "entails", "to": "r"}
    msgs = validate(_set(edges=[e, dict(e)]))
    assert sum("declared twice" in m for m in msgs) == 1


def test_a_relation_outside_the_vocabulary_fails_the_shape_check():
    msgs = validate(_set(edges=[{"from": "h", "rel": "encourages", "to": "r"}]))
    assert msgs, "the schema's relation enum should refuse an invented relation"


def test_validate_returns_every_problem_rather_than_the_first():
    """A whole-corpus gate wants one pass. `9 errors across 12 papers` is a measurement; a
    traceback is not."""
    msgs = validate(_set(questions=[], edges=[{"from": "h", "rel": "supports", "to": "absent"}]))
    assert len(msgs) >= 2


def test_strict_refs_off_keeps_the_shape_checks():
    """For a set being assembled a claim at a time, where the targets do not exist yet."""
    s = _set(edges=[{"from": "h", "rel": "supports", "to": "absent"}])
    assert validate(s, strict_refs=False) == []
    assert validate(s, strict_refs=False) != validate(s)


def test_edges_of_reaches_both_directions():
    s = _set()
    assert len(edges_of(s, "h")) == 1
    assert len(edges_of(s, "r")) == 1


def test_unaccounted_is_the_coverage_denominator():
    s = _set()
    assert unaccounted(s, set()) == ["h", "r"]
    assert unaccounted(s, {"h"}) == ["r"]
    assert unaccounted(s, {"h", "r"}) == []


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t(); print(f"PASS  {t.__name__}"); passed += 1
        except Exception:
            print(f"FAIL  {t.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
