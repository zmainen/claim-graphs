# Analyze a paper into claims

{{generated-note}}

Reverse construction: a finished argument in prose goes in, a claim graph comes out. You are
recovering a structure the authors had and did not write down.

Expect 15–40 claims for a full-length primary research paper, plus components. A graph with six
claims has collapsed the argument; one with a hundred has decomposed results into statistics.

**This workflow has a runner, and you should use it.** Everything below the runbook is for
judging what comes back, for a document the pipeline cannot fetch, or for working without a
checkout. It is not an alternative procedure: reproducing a layer from memory when the layer
exists is how the two paths drift.

## The runbook

{{agent-runbook}}

## Reading what comes back

The layers do the extracting. These are the judgements they get wrong, in the order they cost
the most.

**Check the slices before anything else.** `prepare` reports the size of each slice it cut. A
results slice of a few hundred characters means section detection failed, all three readers read
the wrong text, and every claim below them is wrong for that one reason. This is a fault in
intake that presents as a fault in reading, so it is worth the ten seconds before three model
calls.

**JATS over PDF, always.** From JATS a `panel` field is the publisher's own element id; from a
PDF it is an inference about a label in running text. Section boundaries are tagged rather than
guessed, captions are one element each, and reading order is explicit. Which path was taken is
recorded in the output because it bounds what the readers can possibly extract.

**The spine is not in the results.** The readers recover the empirical layer well and the spine
badly, which is what `external-review` exists to repair. Check it recovered:

- **Hypotheses** — the introduction's closing paragraph, the abstract's "we sought to test".
  A paper with results and no recoverable hypothesis is worth noting rather than inventing one.
- **Predictions** — sometimes explicit, more often implicit in how a result is framed as
  confirming or disconfirming. Where implicit, write the prediction that makes the test
  intelligible and say in the body that it is reconstructed.
- **Controls and their alternatives** — "to rule out", "no effect of", "we verified that". For
  each, the alternative it eliminates needs its own claim with stance `entertains` or `rejects`.
  This is the step most often skipped, and skipping it leaves the control's edge pointing at
  whatever asserted claim is nearest — which the gate then rejects, correctly.
- **Scope** — "all results come from", "the model assumes", "restricted to", and the limits
  paragraph of the discussion, where scope claims hide in finished papers.
- **Literature-context** — prior results the argument inherits as premises. If the paper rules
  out "gain control", gain control needs a node or the eliminative move has no referent.

**Panel grounding is the weak measurement.** Recorded agreement on role runs far ahead of
agreement on panel. Where a claim's panel matters — anything a reproduction would have to
locate — check it against the figure rather than trusting it.

## Failure modes

**Quantitative hallucination.** A number that is plausible, absent from the paper, and
uncatchable by a reader. Take every value verbatim; leave the field out if you cannot.

**Panel inflation.** One claim per statistic yields a graph that mirrors the figures and
explains nothing. The unit is a proposition, not a p-value. Where a claim states a whole that
several comparisons each partly establish, write the whole and attach the components with
`part-of` rather than inflating the count with near-duplicates.

**Reading the discussion as results.** A reframing through outside theory is
`role: interpretation`, not an empirical claim, however confidently the discussion states it.

**Manufactured agreement.** Answering the three readers in one context, so `reconcile` grades
claims by an agreement you produced rather than found. See the runbook.

**Silent edge repair.** When `rules-out` has no legal target, the fix is a new alternative node,
never a redirect to the nearest asserted claim.

## Then

Run `modules`, read its `loose` list, and add the edge each loose claim names before handing
over — a synthesis that points at nothing, a result wired to no finding, an apparatus claim with
no `requires` is a gap in the argument the layer has found for you, not a property of the paper.

Run [../references/checks.md](../references/checks.md) — the gate, then coverage, then the
reconstruction test. Report what you could not settle. If the handoff is for a person to read
rather than for a corpus to hold, build it as an overlay on the paper's own text
([../references/presentation.md](../references/presentation.md)).
