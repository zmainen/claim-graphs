"""A claim approval is granted to what the claim says, not to a version of a run.

A layer approval names a version and is superseded by a re-run, which is right for an output
and wrong for a proposition: someone who has checked that a paper reports what a claim says has
judged the claim, and re-running the extraction chain does not undo that. What must undo it is
the claim changing.

The whole design rests on what goes into the hash. These tests pin that, because every field
wrongly included would void real judgements for reasons that have nothing to do with them —
`warrant` alone is recomputed for the entire corpus whenever the warrant layer runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claim_graphs.claim_approval import (  # noqa: E402
    HASHED_FIELDS, content, content_hash,
)

CLAIM = {
    "uuid": "c9c60ea3-aab4-4225-b151-17d106195f8d",
    "slug": "anterior-insula-neural-substrate-guilt",
    "claim": "The anterior insula is the neural substrate of the guilt effect.",
    "claim-type": "hypothesis",
    "role": "hypothesis",
    "epistemic": "hypothesis",
    "warrant": "strong",
    "warrant_why": "its prediction is confirmed",
    "warrant_from": ["predictions"],
    "check_verification": "unrecorded",
    "priority": "2026-09-13",
    "entails": ["anterior-insula-tracks-guilt-insula"],
    "reproductions": [],
    "assertions": [{"paper-slug": "gadeke-2026-guilt-insula", "doi": "10.7554/eLife.105391",
                    "panel": "fig3a", "readers": "single-source"}],
}


def _with(**over):
    d = dict(CLAIM)
    d.update(over)
    return d


def test_a_layer_recomputing_its_output_does_not_lapse_an_approval():
    """The property the whole design exists for.

    `warrant`, `check_verification` and `priority` are written by layers across the corpus. If
    any were hashed, one warrant run would void every claim approval anyone had ever granted.
    """
    base = content_hash(CLAIM)
    assert content_hash(_with(warrant="weak")) == base
    assert content_hash(_with(warrant_why="something else entirely")) == base
    assert content_hash(_with(warrant_from=[])) == base
    assert content_hash(_with(check_verification="reproduced")) == base
    assert content_hash(_with(priority="2026-12-01")) == base


def test_evidence_about_a_claim_is_not_a_change_to_it():
    assert content_hash(_with(reproductions=[{"status": "verified"}])) == content_hash(CLAIM)


def test_rewiring_the_argument_does_not_lapse_a_claim_approval():
    """Relations are what a claim-tree approval is for.

    Holding the two apart is the point: a proposition can be true of the paper while its edges
    are wrong, and collapsing the grains would make it impossible to say so.
    """
    assert content_hash(_with(entails=["something-else"])) == content_hash(CLAIM)
    assert content_hash(_with(entails=[])) == content_hash(CLAIM)


def test_changing_what_the_claim_says_lapses_it():
    assert content_hash(_with(claim="The anterior insula may be the substrate.")) != content_hash(CLAIM)
    assert content_hash(_with(role="empirical")) != content_hash(CLAIM)
    assert content_hash(_with(**{"claim-type": "empirical"})) != content_hash(CLAIM)
    assert content_hash(_with(epistemic="established")) != content_hash(CLAIM)


def test_what_it_is_asserted_about_is_part_of_the_claim():
    """Same sentence, different panel, is a different thing to have checked."""
    moved = [dict(CLAIM["assertions"][0], panel="fig5c")]
    assert content_hash(_with(assertions=moved)) != content_hash(CLAIM)
    # ...but who read it is not.
    other = [dict(CLAIM["assertions"][0], readers="three-reader")]
    assert content_hash(_with(assertions=other)) == content_hash(CLAIM)


def test_identity_is_not_content():
    assert content_hash(_with(uuid="00000000-0000-0000-0000-000000000000")) == content_hash(CLAIM)
    assert content_hash(_with(slug="renamed")) == content_hash(CLAIM)


def test_reordering_the_front_matter_does_not_lapse_an_approval():
    """The canonical form sorts keys, so a formatter cannot void a judgement."""
    reversed_order = {k: CLAIM[k] for k in reversed(list(CLAIM))}
    assert content_hash(reversed_order) == content_hash(CLAIM)


def test_the_hashed_set_is_what_is_documented():
    """A field added to the hash silently is a field that starts voiding approvals silently."""
    assert set(content(CLAIM)) == set(HASHED_FIELDS) | {"assertions"}
    assert HASHED_FIELDS == ("claim", "claim-type", "role", "epistemic")


def test_a_missing_field_is_not_an_error():
    """Claim files in the wild do not all carry every field."""
    assert content_hash({"claim": "x"})


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
