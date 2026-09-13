"""Edge recovery is judged up to grain, and reported per relation.

Two extractions of one paper choose different grains: a curated tree folds components into the
whole, a chain returns each comparison as the prose states it. An edge the reference drew to
the whole is then drawn in the CLI tree to a component, and scoring those as different edges
measures the split rather than the argument.

Measured on `wengert-2026-kcnc1`, the correction is worth about one point (21/105 strict,
22/105 up to grain) — which is the finding: the gap is not the grain. What the per-relation
breakdown then shows is where it is: `tests` at 36%, `scopes` at 0 of 17, because the
reference bounds the whole paper from one envelope claim and the chain bounds each result
locally. One number could not say that.

No LLM and no network. Runs under pytest or standalone.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claim_graphs.evaluate import _bounded_claims, _part_families, _score_edges


class _C:
    def __init__(self, slug, role="empirical"): self.slug, self.role = slug, role


def _matched(*pairs):
    return [{"ref_slug": r, "cli_slug": c, "match_quality": "exact"} for r, c in pairs]


def test_a_family_is_the_transitive_closure_of_part_of():
    edges = [("leaf", "mid", "part-of"), ("mid", "whole", "part-of"), ("x", "y", "supports")]
    fam = _part_families(edges)
    assert fam["leaf"] == fam["whole"] == frozenset({"leaf", "mid", "whole"}), (
        "a component reaches the whole through any number of hops, and back")
    assert "x" not in fam, "only part-of builds a family"


def test_an_edge_to_a_component_recovers_the_edge_to_the_whole(tmp_path=None):
    """The case the correction exists for."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ref, cli = Path(d) / "ref", Path(d) / "cli"
        ref.mkdir(); cli.mkdir()
        # Reference: one whole result, supporting a synthesis.
        (ref / "whole.md").write_text(
            "---\nslug: whole\nsupports: [syn]\n---\n", encoding="utf-8")
        (ref / "syn.md").write_text("---\nslug: syn\n---\n", encoding="utf-8")
        # CLI: the same result split in two, and the *component* carries the support edge.
        (cli / "c-whole.md").write_text("---\nslug: c-whole\n---\n", encoding="utf-8")
        (cli / "c-part.md").write_text(
            "---\nslug: c-part\npart-of: [c-whole]\nsupports: [c-syn]\n---\n", encoding="utf-8")
        (cli / "c-syn.md").write_text("---\nslug: c-syn\n---\n", encoding="utf-8")

        total, rec, extra, by_rel = _score_edges(
            _matched(("whole", "c-whole"), ("syn", "c-syn")),
            [_C("whole"), _C("syn")], [_C("c-whole"), _C("c-part"), _C("c-syn")], ref, cli)

        assert total == 1
        assert rec == 1, "the edge is on the component; the family is what makes it the same edge"
        assert by_rel == {"supports": (1, 1)}


def test_recovery_is_reported_per_relation():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ref, cli = Path(d) / "ref", Path(d) / "cli"
        ref.mkdir(); cli.mkdir()
        (ref / "a.md").write_text(
            "---\nslug: a\ntests: [b]\nscopes: [b]\n---\n", encoding="utf-8")
        (ref / "b.md").write_text("---\nslug: b\n---\n", encoding="utf-8")
        (cli / "x.md").write_text("---\nslug: x\ntests: [y]\n---\n", encoding="utf-8")
        (cli / "y.md").write_text("---\nslug: y\n---\n", encoding="utf-8")

        total, rec, extra, by_rel = _score_edges(
            _matched(("a", "x"), ("b", "y")), [_C("a"), _C("b")], [_C("x"), _C("y")], ref, cli)

        assert total == 2 and rec == 1
        assert by_rel == {"tests": (1, 1), "scopes": (0, 1)}, (
            "the spine surviving while scope does not is the distinction worth having")


def test_a_star_scope_bounds_every_eligible_claim():
    claims = [_C("r1"), _C("r2"), _C("ctl", "control"),
              _C("s", "scope"), _C("m", "methodological")]
    edges = [("s", "*", "scopes")]
    assert _bounded_claims(edges, claims) == {"r1", "r2", "ctl"}, (
        "`*` reaches the results, controls, syntheses and interpretations — not the scope "
        "and methodological claims, which are not what a scope bounds")


def test_an_enumeration_and_a_star_are_the_same_assertion():
    """The case the ruling in #37 is about: two trees bounding the same work, written differently."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ref, cli = Path(d) / "ref", Path(d) / "cli"
        ref.mkdir(); cli.mkdir()
        # Reference: an envelope written out by hand.
        (ref / "sc.md").write_text(
            "---\nslug: sc\nrole: scope\nscopes: [a, b]\n---\n", encoding="utf-8")
        (ref / "a.md").write_text("---\nslug: a\nrole: empirical\n---\n", encoding="utf-8")
        (ref / "b.md").write_text("---\nslug: b\nrole: empirical\n---\n", encoding="utf-8")
        # CLI: the same assertion as a wildcard, from a differently-named scope claim.
        (cli / "x-sc.md").write_text(
            "---\nslug: x-sc\nrole: scope\nscopes: [\"*\"]\n---\n", encoding="utf-8")
        (cli / "x-a.md").write_text("---\nslug: x-a\nrole: empirical\n---\n", encoding="utf-8")
        (cli / "x-b.md").write_text("---\nslug: x-b\nrole: empirical\n---\n", encoding="utf-8")

        total, rec, extra, by_rel = _score_edges(
            _matched(("a", "x-a"), ("b", "x-b")),
            [_C("sc", "scope"), _C("a"), _C("b")],
            [_C("x-sc", "scope"), _C("x-a"), _C("x-b")], ref, cli)

        assert by_rel["scopes"] == (2, 2), (
            "both claims are bounded on both sides; that the bound is carried by a differently "
            "named claim, and written as a wildcard, is not a disagreement")
        assert total == 2, "scope counts one per bounded claim, not one per enumerated edge"
        assert rec == 2


def test_scope_counts_once_per_bounded_claim_not_once_per_edge():
    """An envelope of 2 edges and a `*` of 1 edge must not give different denominators."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ref, cli = Path(d) / "ref", Path(d) / "cli"
        ref.mkdir(); cli.mkdir()
        (ref / "sc.md").write_text(
            "---\nslug: sc\nrole: scope\nscopes: [a, b]\n---\n", encoding="utf-8")
        (ref / "a.md").write_text("---\nslug: a\nrole: empirical\n---\n", encoding="utf-8")
        (ref / "b.md").write_text("---\nslug: b\nrole: empirical\n---\n", encoding="utf-8")
        # CLI bounds one of the two.
        (cli / "x-sc.md").write_text(
            "---\nslug: x-sc\nrole: scope\nscopes: [x-a]\n---\n", encoding="utf-8")
        (cli / "x-a.md").write_text("---\nslug: x-a\nrole: empirical\n---\n", encoding="utf-8")
        (cli / "x-b.md").write_text("---\nslug: x-b\nrole: empirical\n---\n", encoding="utf-8")

        total, rec, extra, by_rel = _score_edges(
            _matched(("a", "x-a"), ("b", "x-b")),
            [_C("sc", "scope"), _C("a"), _C("b")],
            [_C("x-sc", "scope"), _C("x-a"), _C("x-b")], ref, cli)
        assert by_rel["scopes"] == (1, 2), "one of the two bounded claims is bounded in the CLI tree"


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t(); print(f"ok   {t.__name__}"); passed += 1
        except Exception:
            print(f"FAIL {t.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
