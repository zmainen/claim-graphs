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

from claim_graphs.evaluate import _part_families, _score_edges


class _C:
    def __init__(self, slug): self.slug = slug


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
