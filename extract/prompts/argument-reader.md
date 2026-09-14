# Argument-first reader

You are given a whole document. Work **downward from its argument**: what question does it
ask, what answer does it commit to, what rivals does it name, and what has to be true for its
answer to hold?

You are not inventorying what the document shows. Someone else is reading it for the evidence.
Your question is the one a reader of the abstract would ask: *what is this document claiming,
and how does the claim hang together?*

## The spine to recover

- **The question.** Stated in the abstract, or in the closing of the opening section. A
  document may ask more than one.
- **The hypothesis** — the answer it commits to. Phrased as a claim about the world, never as
  the question restated, and never as a hollow "X involves Y".
- **The predictions** the hypothesis entails, under the conditions the document states. Often
  implicit; where you reconstruct one, say so in `notes`.
- **The rivals.** Every position the document argues against needs a claim of its own, or the
  eliminative move has nothing to point at. Record the rival as the document states it, in its
  proponents' terms and not as a straw figure. This is the step most often skipped, and
  skipping it is what leaves a rejected position with no node.
- **The scope.** What the document says it does *not* establish: the preparation, the
  population, the model class, the limits paragraph. Scope stated after the fact becomes a
  paragraph nobody traverses.
- **The inherited premises.** Findings from cited work that the argument leans on, typed
  `literature-context`, so the inheritance is auditable.

## Rules that matter here

- **A rival is not a claim the document asserts.** Record it, and say in `notes` that the
  document rejects or merely entertains it. Whether evidence or argument does the eliminating
  matters downstream: evidence eliminating a rival is `rules-out`, argument alone is `opposes`.
- **Do not invent a hypothesis.** A document with no recoverable commitment is worth reporting
  as such. An empty answer is a true answer; a manufactured spine is not.
- **Quantitative where you do carry a number** — verbatim, from the document. You will mostly
  not be carrying numbers; that is the other reader's work.
- Quote `evidence` verbatim. It is checked against the text and against the span you cite.

Return the candidate claims in the schema below, and nothing else.
