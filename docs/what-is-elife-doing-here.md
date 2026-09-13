# Why eLife appears in a generic repository

This repository is machinery: a claim-graph format, a schema, a pipeline, exporters. It was
developed against one corpus — ten neuroscience papers from eLife — and split out of the
repository that holds that corpus. The split is meant to leave nothing eLife-specific behind, and
two things are deliberate exceptions. They are written down here so that an audit finds the reason
beside the finding, rather than re-raising them every time someone reads the tree.

Everything else eLife-specific was removed before this repository was published: the collaboration
record, the documents addressed to named eLife staff, the per-paper quality judgements, the
eLife-branded identifiers in exports and package metadata. If you find more, it is a bug — the two
exceptions below are the whole list.

## 1. `ElifeSource`, in `extract/claim_graphs/sources.py`

A `Source` resolves a document reference to a local file and says what format it is in. The
protocol is the point of the design: publishers differ, and the machinery should not care. But a
protocol with no implementation is a claim rather than a seam, so two ship as built-ins —
`FileSource`, which reads a local PDF or XML, and `ElifeSource`, which knows that a
`10.7554/eLife.NNNNN` DOI has JATS at a particular CDN URL.

`ElifeSource` stays because it is the working proof that the protocol carries a real publisher, and
because it is useful: eLife's whole corpus is open access, so it is the one publisher anyone can
point this at without credentials. Others register through the `claim_graphs.sources` entry point
group and need not live here.

The boundary is enforced, not just asserted: `extract/tests/test_sources.py` tokenises
`prepare.py` and fails if a publisher name appears anywhere in its code, docstrings excluded. eLife
lives in `sources.py` and nowhere else in the reading path.

## 2. The worked examples, in `scripts/relations.py` and `extract/claim_graphs/vocabulary.py`

The prompts teach each relation, each confusable pair of roles, and each kind of non-claim by
showing one. Those examples are real claims from real papers, and the papers are eLife's.

They are real on purpose. A relation vocabulary is learned from instances, and an invented instance
teaches the shape of the invention rather than the shape of the distinction — the difference between
`requires` and `supports`, or between a control and a finding, is exactly the kind of judgement that
a plausible fabrication makes look easier than it is. The papers are CC-BY, the claims are public,
and the examples cite their source.

What follows from keeping them, and is not hidden: building or checking the prompt contract reads
claim files, so it needs a corpus. `CLAIM_GRAPHS_CORPUS_DIR` points at one, and the tests that need
it skip with a reason when it is absent. A published release ships the *rendered* contract, so
running the pipeline needs no corpus — only regenerating the contract does.

Whether these should eventually become a small curated example set, reviewed once and owned by this
repository rather than borrowed from a corpus, is open. The argument for it is that the corpus can
rename a claim out from under an example, and has: one relation lost its example that way and the
prompt now reads "no use in the corpus yet" for four of twenty-one. The argument against is that a
curated set is a second place the vocabulary lives, which is the failure this project has watched
four times.
