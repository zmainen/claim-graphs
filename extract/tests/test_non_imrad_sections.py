"""A paper that is not IMRaD: where its argument goes, and what still does not move.

The section vocabulary answers to `sec-type` and, failing that, to the words "result",
"method", "intro" and "discuss" in a section title. A review, a perspective or an opinion piece
has none of those: its sections are titled for what they argue. Every one of them fell through,
so the whole body was dropped and the three readers were handed the abstract alone — an intake
failure that presents downstream as a reading failure, and one the pipeline did not refuse.

Two invariants are load-bearing here and are asserted rather than described. The fallbacks fire
only where the marked-up form found nothing, so a publisher's JATS is byte-identical through
this change; and the back matter a converted manuscript carries as ordinary sections stays out
of the argument, or a reader is handed the bibliography as though the paper asserted it.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claim_graphs.agents import (  # noqa: E402
    NO_STRUCTURE, raw_slice_for_agent, slice_for_agent,
)
from claim_graphs.prepare import parse_jats  # noqa: E402

REVIEW = """<article>
  <front><article-meta>
    <title-group><article-title>The legible body</article-title></title-group>
    <abstract><p>Movement carries the variables the brain computes.</p></abstract>
  </article-meta></front>
  <body>
    <sec id="the-disembodied-assumption"><title>The disembodied assumption</title>
      <p>It is said that the brain exists to move the body.</p></sec>
    <sec id="movement-is-computation"><title>Movement is computation, not noise</title>
      <p>Spontaneous movement explains more variance than the task does.</p></sec>
    <sec id="figure-1"><title>Figure 1</title>
      <p>One loop, two views. (a) The intracranial view. (b) The embodied view.</p></sec>
    <sec id="acknowledgements"><title>Acknowledgements</title>
      <p>The author thanks the foundation.</p></sec>
    <sec id="references"><title>References and recommended reading</title>
      <p>1. Someone et al. A paper the review cites but does not assert.</p></sec>
  </body>
</article>"""

IMRAD = """<article>
  <front><article-meta>
    <title-group><article-title>Bursting sharpens tuning</article-title></title-group>
    <abstract><p>Tuning narrows by 31% during bursts.</p></abstract>
  </article-meta></front>
  <body>
    <sec sec-type="intro"><title>Introduction</title><p>Relay neurons fire two ways.</p></sec>
    <sec sec-type="results"><title>Results</title><p>Width fell from 42.1 to 29.0 degrees.</p></sec>
    <sec sec-type="results"><title>Bursts and contrast</title><p>The effect held at low contrast.</p></sec>
    <sec sec-type="discussion"><title>Discussion</title><p>Bursts may act as a gain control.</p></sec>
    <sec sec-type="methods"><title>Materials and methods</title><p>Recordings were made in vivo.</p></sec>
  </body>
</article>"""


def _paper(xml: str, name: str):
    """parse_jats wants a file; the suite runs as a script, so make one and drop it."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / name
        p.write_text(xml, encoding="utf-8")
        return parse_jats(p, doi=f"local:{name}")


def test_argument_sections_reach_the_reader():
    """The body of a review arrives, and arrives as `argument` rather than as `results`."""
    paper = _paper(REVIEW, "review.xml")
    assert paper.results_text == ""
    assert "disembodied assumption" in paper.argument_text
    assert "Spontaneous movement explains more variance" in paper.argument_text
    # The reader's slice is the point: before this, it held the abstract and nothing else.
    assert "Spontaneous movement" in raw_slice_for_agent("results", paper)
    assert "Spontaneous movement" in slice_for_agent("results", paper)


def test_back_matter_is_not_argument():
    """Acknowledgements and the bibliography are not propositions the paper asserts."""
    paper = _paper(REVIEW, "review.xml")
    assert "thanks the foundation" not in paper.argument_text
    assert "A paper the review cites" not in paper.argument_text


def test_figure_sections_become_captions():
    """A caption written as a headed section is a caption, panel labels included."""
    paper = _paper(REVIEW, "review.xml")
    assert [f.figure_num for f in paper.figure_captions] == ["1"]
    fig = paper.figure_captions[0]
    assert fig.panels == ["a", "b"]
    # A pandoc section id is a slug made from the heading, not a name the document gave the
    # figure, so the id is derived as it is from a PDF rather than inherited as `figure-1`.
    assert fig.base_id() == "fig1"
    assert "One loop, two views" not in paper.argument_text


def test_spans_carry_the_argument_section():
    """`argument` is in the section vocabulary, so the segmenter cuts it without being told."""
    paper = _paper(REVIEW, "review.xml")
    assert {s["section"] for s in paper.spans} >= {"abstract", "argument", "captions"}


def test_imrad_is_untouched():
    """The fallback does not fire where the IMRaD buckets found something."""
    paper = _paper(IMRAD, "imrad.xml")
    assert paper.argument_text == ""
    assert "argument" not in {s["section"] for s in paper.spans}


def test_every_results_section_is_kept():
    """Two sections of one type join. Returning the first lost the rest with nothing to say so."""
    paper = _paper(IMRAD, "imrad.xml")
    assert "42.1 to 29.0 degrees" in paper.results_text
    assert "held at low contrast" in paper.results_text


def test_an_absent_methods_section_says_so():
    """A review has no procedural sections, and the reader is told that rather than shown a
    heading with nothing under it — which reads as a section that exists and is empty."""
    paper = _paper(REVIEW, "review.xml")
    assert paper.methods_text == ""
    assert slice_for_agent("structure", paper) == NO_STRUCTURE


def test_a_paper_with_methods_is_unchanged():
    """The heading and its order are what the corpus's recorded runs were given."""
    paper = _paper(IMRAD, "imrad.xml")
    assert slice_for_agent("structure", paper).startswith("# Methods\n\n")
    assert "Recordings were made in vivo" in slice_for_agent("structure", paper)


def test_the_reviewer_is_shown_the_argument():
    """The external reviewer reads a paper block of its own, assembled from the IMRaD fields.

    It printed `## Introduction`, `## Results section` and `## Discussion` over nothing for a
    review, so the reviewer was shown a paper with no body and went looking for the source
    outside the prompt — grounding its answer in text the ledger never recorded as an input.
    """
    from claim_graphs.external_review import _format_paper_context

    review = _format_paper_context(_paper(REVIEW, "review.xml"))
    assert "## Argument" in review
    assert "Spontaneous movement explains more variance" in review
    for absent in ("## Introduction", "## Results section", "## Discussion"):
        assert absent not in review, f"{absent} rendered over an empty section"

    imrad = _format_paper_context(_paper(IMRAD, "imrad.xml"))
    assert "## Argument" not in imrad
    for head in ("## Introduction", "## Results section", "## Discussion"):
        assert head in imrad, f"{head} must still be rendered for an IMRaD paper"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
