"""Two readings of one whole document, and what the vocabulary had to grow to hold them.

The three slice readers cut an IMRaD paper three ways, and `reconcile` grades a claim by how
many of them surfaced it. That grade measures the chance one proposition landed in two of the
cuts: 36% on the one eLife paper whose artifacts survive, 5% on a review, and structurally 0%
on a document with no captions and no methods. The perspective readers read the same whole
document from opposite ends instead, so convergence cannot be an artifact of where the cuts
fell — and the side a claim came from names a defect rather than a missing slice.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claim_graphs.agents import raw_slice_for_agent, slice_for_agent  # noqa: E402
from claim_graphs.edges import _SOURCE_ROLE  # noqa: E402
from claim_graphs.overlap import pair_up, same, similarity  # noqa: E402
from claim_graphs.prepare import parse_jats  # noqa: E402
from claim_graphs.prompts import ROLES, files  # noqa: E402
from claim_graphs.schema import ConvergedClaim, ReconciledClaim  # noqa: E402

REVIEW = """<article>
  <front><article-meta>
    <title-group><article-title>The legible body</article-title></title-group>
    <abstract><p>Movement carries the variables the brain computes.</p></abstract>
  </article-meta></front>
  <body>
    <sec id="a"><title>The disembodied assumption</title>
      <p>Cognition was treated as the remainder after motor variables are removed.</p></sec>
    <sec id="b"><title>Movement is computation</title>
      <p>Spontaneous movement explains more variance than the task does.</p></sec>
    <sec id="figure-1"><title>Figure 1</title>
      <p>One loop, two views. (a) The intracranial view. (b) The embodied view.</p></sec>
  </body>
</article>"""


def _paper():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "review.xml"
        p.write_text(REVIEW, encoding="utf-8")
        return parse_jats(p, doi="sources/review.xml")


def test_both_readers_are_given_the_whole_document():
    """Not a slice each. That is the entire mechanism — see the module docstring."""
    paper = _paper()
    for agent in ("evidence", "argument"):
        s = slice_for_agent(agent, paper)
        assert "Movement carries the variables" in s, f"{agent} lost the abstract"
        assert "Spontaneous movement explains" in s, f"{agent} lost the body"
        assert "One loop, two views" in s, f"{agent} lost the captions"
        raw = raw_slice_for_agent(agent, paper)
        assert "Spontaneous movement explains" in raw, f"{agent} raw slice lost the body"


def test_only_the_evidence_reader_is_given_the_part_inventory():
    """The argument reader is asked how claims connect; a list of panels invites anchoring."""
    paper = _paper()
    assert "# The parts of this document" in slice_for_agent("evidence", paper)
    assert "# The parts of this document" not in slice_for_agent("argument", paper)


def test_the_inventory_survives_a_document_with_no_floats():
    """A grant or a preprint has parts too; they are just not figures."""
    paper = _paper()
    paper.figure_captions = []
    paper.tables = []
    inv = paper.part_inventory()
    assert "Text the document has" in inv and "abstract" in inv


def test_each_reader_has_its_own_task_and_the_shared_contract():
    for role in ("evidence-reader", "argument-reader"):
        assert role in ROLES
        task, *contract = files(role)
        assert task == f"{role}.md"
        assert any("schema-candidate" in c for c in contract), "readers return candidate claims"
    assert any("schema-draft" in c for c in files("converge")), "converge returns a table"


def test_origin_is_on_the_converged_claim_and_not_on_the_reconciled_one():
    """A field on the shared model would put `"origin": null` into every corpus's reconcile
    output and move a hash the ledger reads, for a value the slice readers cannot produce."""
    assert "origin" in ConvergedClaim.model_fields
    assert "origin" not in ReconciledClaim.model_fields


def test_inherited_evidence_may_eliminate_a_rival():
    """A review owns no experiment, so every elimination it makes runs on a cited result."""
    assert "literature-context" in _SOURCE_ROLE["rules-out"]
    # and argument-carried elimination stays unrestricted, which is the line between the two
    assert "opposes" not in _SOURCE_ROLE


def test_the_matcher_refuses_a_claim_and_its_negation():
    a = {"claim": "movement is part of the computation"}
    b = {"claim": "movement is not part of the computation"}
    assert similarity(a, b) > 0.6, "overlap alone would merge them — that is the point"
    assert not same(a, b)
    pairs, _, _ = pair_up([a], [b])
    assert pairs == []


def test_the_matcher_survives_paraphrase_within_one_reader():
    """What it is for: repeated runs of one reader, which re-word rather than re-think."""
    a = {"claim": "the face reports decision variables"}
    b = {"claim": "decision variables are reported by the face"}
    assert same(a, b)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
